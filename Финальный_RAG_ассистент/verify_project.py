"""Real local model acceptance checks. No API mocks or prepared answers.

Run: python verify_project.py --passes 2
Evidence is written into evidence/; test documents/runtime stay in runtime/verification/.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import argparse, json, platform, shutil, time
from settings import Config, ROOT
from rag_pipeline import RAGPipeline


def run_pass(number):
    work = ROOT/'runtime'/'verification'/f'pass_{number}_{time.time_ns()}'
    shutil.copytree(ROOT/'data',work/'data')
    config = replace(Config(),data_dir=work/'data',runtime_dir=work/'runtime')
    pipeline=RAGPipeline(config)
    results=[]
    checks=[]
    def check(name, condition):
        checks.append({'name':name,'passed':bool(condition)})
        if not condition:
            raise AssertionError(name)
    def ask(scenario,question):
        result=pipeline.query(question)
        results.append({'scenario':scenario,**result})
        print(f"{scenario}: {result['seconds']:.3f}s cache={result['from_cache']} | {result['answer']}",flush=True)
        return result
    try:
        a=ask('rag_first','Что такое RAG?')
        b=ask('rag_repeat','Что такое RAG?')
        check('first miss, repeat hit with identical answer and sources',not a['from_cache'] and b['from_cache'] and a['answer']==b['answer'] and a['sources']==b['sources'])
        a=ask('fact','В каком году представили архитектуру трансформеров?')
        check('document fact 2017', '2017' in a['answer'])
        ask('unknown','Какой телефон службы поддержки проекта?')
        question='Что такое векторная база данных?'
        a=ask('top_k_3',question)
        pipeline.set_top_k(7)
        b=ask('top_k_7',question)
        check('TOP_K changes context and cache namespace',not b['from_cache'] and len(a['sources'])==3 and len(b['sources'])==7)
        pipeline.set_source('python.txt')
        a=ask('python_filter','Кто создал Python и в каком году?')
        check('metadata filter and Python date',all(x['source']=='python.txt' for x in a['sources']) and '1991' in a['answer'])
        ask('filtered_unknown','Что такое RAG?')
        pipeline.set_source(None)
        pipeline.set_top_k(3)
        before=pipeline.provider.calls
        concurrency=[]
        for count in (10,50,200):
            started=time.perf_counter()
            with ThreadPoolExecutor(max_workers=min(count,32)) as executor:
                batch=list(executor.map(pipeline.query,['Что такое RAG?']*count))
            check(f'{count} cached requests',all(x['from_cache'] for x in batch) and pipeline.provider.calls==before)
            concurrency.append({'requests':count,'workers':min(count,32),'elapsed_seconds':time.perf_counter()-started,'generation_calls':pipeline.provider.calls-before})
        pipeline.clear_cache()
        check('cache cleared',pipeline.cache.count()==0)
        a=ask('after_clear','Что такое RAG?')
        check('clear causes new generation',not a['from_cache'] and pipeline.provider.calls==before+1)
        note=config.data_dir/'project_code.txt'
        note.write_text('Код проекта: СЕВЕР-42.',encoding='utf-8')
        check('index addition',pipeline.reindex())
        pipeline.set_source(note.name)
        a=ask('short_document','Какой код проекта?')
        check('short document retained','СЕВЕР-42' in a['answer'])
        note.write_text('Код проекта: ЮГ-73.',encoding='utf-8')
        check('index update',pipeline.reindex())
        b=ask('updated_document','Какой код проекта?')
        check('updated document invalidates cache',not b['from_cache'] and 'ЮГ-73' in b['answer'] and 'СЕВЕР-42' not in b['answer'])
        note.unlink()
        check('index deletion',pipeline.reindex())
        check('removed filter reset',pipeline.source is None)
        check('removed text absent',all(x['source']!=note.name for x in pipeline.vector_store.search('Какой код проекта?',10)))
        check('unchanged index is reused',not pipeline.reindex())
        stats=pipeline.stats()
        pipeline.close()
        # A fresh instance must detect source edits at startup, using the same on-disk runtime.
        note.write_text('Код при перезапуске: ВОСТОК-19.',encoding='utf-8')
        pipeline=RAGPipeline(config)
        check('startup detects changed corpus',pipeline.vector_store.version!=stats['corpus_version'] and note.name in pipeline.vector_store.source_names)
        check('startup document searchable',any('ВОСТОК-19' in x['text'] for x in pipeline.vector_store.search('Код при перезапуске',10)))
        return {'pass':number,'created_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'python':platform.python_version(),'platform':platform.platform(),'model':config.model,'backend':config.backend,'checks':checks,'answers':results,'cached_concurrency':concurrency,'generation_calls':stats['generation_calls']}
    finally:
        pipeline.close()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--passes',type=int,default=2)
    args=parser.parse_args()
    evidence=ROOT/'evidence'
    evidence.mkdir(exist_ok=True)
    for number in range(1,args.passes+1):
        result=run_pass(number)
        (evidence/f'pass_{number}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(f"PASS {number}: {len(result['checks'])} checks passed",flush=True)

if __name__=='__main__':
    main()

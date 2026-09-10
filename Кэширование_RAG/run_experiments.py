"""Run the homework twice from clean state, using the real local model."""
from pathlib import Path
import subprocess, sys, time, json, os, shutil, re
import httpx
ROOT=Path(__file__).resolve().parent
PYTHON=sys.executable
QUESTIONS=['Привет, что ты умеешь?', 'Что такое RAG?', 'Что такое ИИ?']
VECTOR='Что такое векторная база?'
PYTHON_QUESTION='Что такое Python и где он применяется?'

def configure(k, source=''):
    path=ROOT/'.env'
    data=path.read_text()
    for key,value in [('TOP_K',str(k)),('SOURCE_FILTER',source)]:
        data=re.sub(r'^'+key+r'=.*$',key+'='+value,data,flags=re.M)
    path.write_text(data)

def execute(folder,label,questions):
    print(f'RUN {folder.name}/{label}: python main.py',flush=True)
    env=os.environ.copy()
    env['RESULTS_FILE']=str(folder/'requests.jsonl')
    env['PYTHONUNBUFFERED']='1'
    env['PYTHONIOENCODING']='utf-8'
    # Values must be loaded from the edited .env on every restart.
    for key in ['TOP_K','SOURCE_FILTER']: env.pop(key,None)
    text='1\n'+'\n'.join(questions+['cache','exit'])+'\n'
    with (folder/(label+'.log')).open('w') as out:
        result=subprocess.run([PYTHON,'-u','main.py'],cwd=ROOT,env=env,input=text,text=True,stdout=out,stderr=subprocess.STDOUT,timeout=900)
    if result.returncode: raise RuntimeError(f'Failed {label}: {result.returncode}')
    records=[json.loads(s) for s in (folder/'requests.jsonl').read_text().splitlines()]
    print('DONE',label,'last seconds',records[-1]['seconds'],'cache',records[-1]['cache_hit'],flush=True)
    return records

def validate(records):
    assert len(records)==12,len(records)
    for a,b in zip(records[:3],records[3:6]):
        assert a['query']==b['query'] and a['answer']==b['answer']
        assert not a['cache_hit'] and b['cache_hit']
    assert records[5]['cache_records']==3
    assert [r['top_k'] for r in records[6:9]]==[3,7,7]
    assert [r['cache_hit'] for r in records[6:9]]==[False,False,True]
    assert len(records[6]['contexts'])==3 and len(records[7]['contexts'])==7
    assert records[6]['query']==records[7]['query']==VECTOR
    assert records[9]['query']==VECTOR and not records[9]['cache_hit']
    for row in records[9:11]:
        assert row['source_filter']=='Python' and row['contexts']
        assert all(c[1]=='Python' for c in row['contexts'])
    assert records[11]['cache_hit'] and records[10]['answer']==records[11]['answer']
    assert all(r['seconds']>0 for r in records)

server_log=(ROOT/'local_server.log').open('w')
server=subprocess.Popen([PYTHON,'-m','llama_cpp.server','--model',str(ROOT/'models/qwen/qwen2.5-3b-instruct-q4_k_m.gguf'),'--model_alias','qwen2.5-3b-instruct','--host','127.0.0.1','--port','8765','--n_ctx','8192','--n_threads','8','--n_threads_batch','8','--n_batch','512','--chat_format','chatml','--verbose','false'],stdout=server_log,stderr=subprocess.STDOUT)
try:
    with httpx.Client(trust_env=False,timeout=3) as client:
        for _ in range(90):
            if server.poll() is not None: raise RuntimeError('Local server exited; see local_server.log')
            try:
                if client.get('http://127.0.0.1:8765/v1/models').status_code==200: break
            except httpx.HTTPError: pass
            time.sleep(1)
        else: raise TimeoutError('Server startup')
    print('Local model ready',flush=True)
    for pass_number in [1,2]:
        folder=ROOT/'results'/f'pass_{pass_number}'
        folder.mkdir(parents=True,exist_ok=False)
        (ROOT/'cache.json').unlink(missing_ok=True)
        if (ROOT/'chroma_db').exists(): shutil.rmtree(ROOT/'chroma_db')
        configure(3)
        records=execute(folder,'01_cache',QUESTIONS+QUESTIONS)
        assert len(records)==6 and len(json.loads((ROOT/'cache.json').read_text()))==3
        shutil.copy2(ROOT/'cache.json',folder/'cache_after_three_questions.json')
        execute(folder,'02_top_k_3',[VECTOR])
        configure(7)
        execute(folder,'03_top_k_7',[VECTOR,VECTOR])
        configure(7,'Python')
        records=execute(folder,'04_filter_python',[VECTOR,PYTHON_QUESTION,PYTHON_QUESTION])
        validate(records)
        shutil.copy2(ROOT/'cache.json',folder/'cache_final.json')
        (folder/'validated.json').write_text(json.dumps({'status':'passed','requests':len(records),'initial_cache_records':3,'final_cache_records':len(json.loads((ROOT/'cache.json').read_text()))},indent=2))
        print(f'PASS {pass_number} VALIDATED',flush=True)
    configure(7)
    (ROOT/'results/COMPLETE.json').write_text(json.dumps({'status':'completed','clean_passes':2,'backend':'local','model':'Qwen2.5-3B-Instruct Q4_K_M','embeddings':'intfloat/multilingual-e5-small','original_documents':3},indent=2))
finally:
    server.terminate()
    try: server.wait(timeout=15)
    except subprocess.TimeoutExpired: server.kill();server.wait()
    server_log.close()

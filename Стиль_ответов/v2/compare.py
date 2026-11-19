import json
import re
import sys
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from run import MODEL, evaluate

torch.set_num_threads(2)
root=Path(__file__).resolve().parent
rows=[line.split('\t') for line in (root/'test.tsv').read_text().splitlines()]
report=json.loads((root/'result/report.json').read_text())
base=AutoModelForCausalLM.from_pretrained(MODEL,revision=report["revision"])
old=PeftModel.from_pretrained(base,sys.argv[1])
tok=AutoTokenizer.from_pretrained(MODEL,revision=report["revision"])
old_answers=evaluate(old,tok,[r[2] for r in rows])
def matches(answer,pattern):
    # Сопоставляем именно последний вопрос, исключая предложение с описанием услуги.
    question=re.split(r'[.!\n]',answer.lower())[-1].strip()
    return answer.count('?')==1 and question.endswith('?') and bool(re.search(pattern,question))
records=[]
for (topic,pattern,query),old_answer,result in zip(rows,old_answers,report['examples'],strict=True):
    assert result['question']==query
    row=dict(topic=topic,question=query,expected_pattern=pattern,v1=old_answer,v2=result['after'],
             v1_match=matches(old_answer,pattern),v2_match=matches(result['after'],pattern))
    records.append(row)
    print('EVAL_ROW '+json.dumps(row,ensure_ascii=False),flush=True)
(root/'result/comparison.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))

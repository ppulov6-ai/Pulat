from pathlib import Path
import json
rows=[]
topics=[]
for line in Path('cases.txt').read_text().splitlines():
    key,*qs,answer=line.split('|')
    if key in {"budget","budget_known","discount","deadline","deadline_known","change","support","transfer","meeting"}:
        answer="Готовы обсудить условия. "+answer
    topics.append(dict(id=key,questions=qs,answer=answer))
    rows.extend(dict(instruction=q,output=answer) for q in qs)
Path('train.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
Path('topics.json').write_text(json.dumps(topics,ensure_ascii=False,indent=2))

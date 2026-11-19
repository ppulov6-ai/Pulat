"""Distil the tuned transformer into a compact sentence representation for edge inference."""
import json
import re
from pathlib import Path
import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

torch.set_num_threads(2)
root=Path(__file__).resolve().parent
topics=json.loads((root/'topics.json').read_text())
texts=[q for t in topics for q in t['questions']]
labels=[t['id'] for t in topics for q in t['questions']]
meta=json.loads((root/'result/report.json').read_text())
tok=AutoTokenizer.from_pretrained(meta['model'],revision=meta['revision'])
tok.pad_token=tok.eos_token
model=PeftModel.from_pretrained(AutoModelForCausalLM.from_pretrained(meta['model'],revision=meta['revision']),root/'result/adapter').eval()
def grams(s):
    words=re.findall(r'[а-яa-z0-9]+',s.lower().replace('ё','е'))
    return {g for w in words for g in [w]+['^'+w[:5]]+[w[i:i+3] for i in range(len(w)-2)]}
features=[grams(q) for q in texts]
df={}
for row in features:
    for g in row:df[g]=df.get(g,0)+1
vocab=sorted(df)
idf=np.array([np.log((1+len(texts))/(1+df[g]))+1 for g in vocab])
X=np.array([[idf[i] if g in row else 0 for i,g in enumerate(vocab)] for row in features])
X/=np.linalg.norm(X,axis=1,keepdims=True)
encoded=[]
with torch.inference_mode():
    for i in range(0,len(texts),8):
        b=tok(texts[i:i+8],padding=True,return_tensors='pt')
        h=model(**b,output_hidden_states=True).hidden_states[-1]
        mask=b.attention_mask.unsqueeze(-1)
        encoded.extend(((h*mask).sum(1)/mask.sum(1)).numpy())
H=np.stack(encoded);H-=H.mean(axis=0)
u,s,_=np.linalg.svd(H,full_matrices=False)
Z=u[:,:24]*np.sqrt(s[:24])
Z/=np.linalg.norm(Z,axis=1,keepdims=True)
P=X.T@np.linalg.solve(X@X.T+0.05*np.eye(len(X)),Z)
(root/'result/edge.json').write_text(json.dumps(dict(vocab=vocab,idf=idf.round(3).tolist(),projection=P.round(4).tolist(),vectors=Z.round(4).tolist(),labels=labels),ensure_ascii=False,separators=(',',':')))

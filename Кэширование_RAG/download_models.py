import urllib.request,json,hashlib,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parent / 'models'
REPOS=[('Qwen/Qwen2.5-3B-Instruct-GGUF','qwen2.5-3b-instruct-q4_k_m.gguf','qwen/qwen2.5-3b-instruct-q4_k_m.gguf'),('intfloat/multilingual-e5-small','onnx/model.onnx','e5/model.onnx'),('intfloat/multilingual-e5-small','onnx/tokenizer.json','e5/tokenizer.json')]
manifest=[]
def get_json(url):
 for i in range(3):
  try:
   with urllib.request.urlopen(url,timeout=35) as r:return json.load(r)
  except Exception:
   if i==2:raise

def download(item):
 repo,remote,dest=item
 info=get_json('https://huggingface.co/api/models/'+repo+'?blobs=true')
 entry=next(e for e in info['siblings'] if e['rfilename']==remote)
 revision=info['sha']; expected=entry.get('lfs',{}).get('sha256');size=entry.get('size')
 target=ROOT/dest;target.parent.mkdir(parents=True,exist_ok=True)
 url='https://huggingface.co/'+repo+'/resolve/'+revision+'/'+remote
 print('Starting',dest,'bytes',size,flush=True)
 for attempt in range(3):
  try:
   with urllib.request.urlopen(url,timeout=50) as r, open(str(target)+'.part','wb') as f:
    total=0;last=time.monotonic();hasher=hashlib.sha256()
    while True:
     chunk=r.read(2**20)
     if not chunk:break
     f.write(chunk);hasher.update(chunk);total+=len(chunk)
     if time.monotonic()-last>15:
      print(dest,'downloaded MB',round(total/2**20),flush=True);last=time.monotonic()
   digest=hasher.hexdigest()
   if size is not None and total!=size:raise RuntimeError('size mismatch')
   if expected and digest!=expected:raise RuntimeError('SHA256 mismatch')
   Path(str(target)+'.part').replace(target)
   record={'repo':repo,'revision':revision,'file':remote,'local_path':str(target),'sha256':digest,'bytes':total,'expected_sha256':expected}
   print('DONE',dest,total,digest,flush=True)
   return record
  except Exception as exc:
   print(dest,'attempt',attempt+1,type(exc).__name__,flush=True)
   if attempt==2:raise
with ThreadPoolExecutor(max_workers=3) as pool:
 for result in pool.map(download,REPOS):manifest.append(result)
(ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = "ai-forever/rugpt3small_based_on_gpt2"
revision = "a9307e696cd3c5b7f953ff4cb19d76a4d81821d5"
torch.set_num_threads(1)
tok = AutoTokenizer.from_pretrained(base, revision=revision)
model = PeftModel.from_pretrained(
    AutoModelForCausalLM.from_pretrained(base, revision=revision, low_cpu_mem_usage=True),
    "/adapter",
).eval()

class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, data):
        raw = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.send_json(200 if self.path == "/health" else 404, {"model": "rugpt-lora-v3"})

    def do_POST(self):
        size = int(self.headers.get("Content-Length", 0))
        if self.path != "/generate" or not 0 < size <= 48000:
            return self.send_json(400, {"error": "invalid request"})
        data = json.loads(self.rfile.read(size))
        question = data["message"]
        history = data["history"]
        turns = [f"### Instruction:\n{q}\n\n### Response:\n{a}\n" for q, a in history]
        facts = data.get("facts", "")
        prefix = "Сведения о проекте: " + facts + "\n" if facts else ""
        prompt = prefix + "".join(turns) + f"### Instruction:\n{question}\n\n### Response:\n"
        ids = tok(prompt, return_tensors="pt").input_ids[:, -700:]
        with torch.inference_mode():
            out = model.generate(ids, attention_mask=torch.ones_like(ids), max_new_tokens=72,
                                 do_sample=False, repetition_penalty=1.12, pad_token_id=tok.eos_token_id)
        answer = tok.decode(out[0, ids.shape[1]:], skip_special_tokens=True).split("###")[0].strip()
        self.send_json(200 if answer else 503, {"answer": answer})

HTTPServer(("0.0.0.0", 8090), Handler).serve_forever()

"""LoRA для русскоязычной GPT-2. Запуск из каталога проекта."""
import argparse
import json
from pathlib import Path

import torch
from peft import LoraConfig, PeftModel, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed

MODEL = "ai-forever/rugpt3small_based_on_gpt2"
OUT = Path("result")

def prompt(question):
    # Формат instruction/output из fine_tuning/train.py преподавателя.
    return f"### Instruction:\n{question}\n\n### Response:\n"

def evaluate(model, tokenizer, questions):
    model.eval()
    with torch.inference_mode():
        answers = []
        for q in questions:
            ids = tokenizer(prompt(q),return_tensors="pt").input_ids
            tokens = model.generate(ids, attention_mask=torch.ones_like(ids), max_new_tokens=40,
                                    do_sample=False, pad_token_id=tokenizer.eos_token_id)
            answers.append(tokenizer.decode(tokens[0,ids.shape[1]:],skip_special_tokens=True).strip())
        return answers

def run():
    parser=argparse.ArgumentParser()
    parser.add_argument("--chat",action="store_true")
    args=parser.parse_args()
    set_seed(37)
    torch.set_num_threads(2)
    tokenizer=AutoTokenizer.from_pretrained(MODEL)
    base=AutoModelForCausalLM.from_pretrained(MODEL)
    if args.chat:
        model=PeftModel.from_pretrained(base,OUT/"adapter")
        while q:=input("Вопрос (Enter для выхода): ").strip():
            print(evaluate(model,tokenizer,[q])[0])
        return
    data=json.loads(Path("train.json").read_text())
    tests=json.loads(Path("test.json").read_text())
    assert set(tests).isdisjoint(row["instruction"] for row in data)
    before=evaluate(base,tokenizer,tests)
    adapter=LoraConfig(task_type="CAUSAL_LM",r=16,lora_alpha=32,lora_dropout=0.05,
                       target_modules=["c_attn","c_proj","c_fc"],fan_in_fan_out=True)
    model=get_peft_model(base,adapter)
    model.print_trainable_parameters()
    optimizer=torch.optim.AdamW((p for p in model.parameters() if p.requires_grad),lr=0.0005)
    samples=[]
    for row in data:
        prefix=tokenizer.encode(prompt(row["instruction"]),add_special_tokens=False)
        reply=tokenizer.encode(row["output"],add_special_tokens=False)+[tokenizer.eos_token_id]
        samples.append((prefix+reply,[-100]*len(prefix)+reply))
    model.train()
    losses=[]
    for epoch in range(5):
        order=torch.randperm(len(samples)).tolist()
        batch_losses=[]
        for pos in range(0,len(order),4):
            batch=[samples[i] for i in order[pos:pos+4]]
            width=max(len(ids) for ids,_ in batch)
            ids=torch.tensor([x+[tokenizer.eos_token_id]*(width-len(x)) for x,_ in batch])
            mask=torch.tensor([[1]*len(x)+[0]*(width-len(x)) for x,_ in batch])
            labels=torch.tensor([y+[-100]*(width-len(y)) for _,y in batch])
            optimizer.zero_grad()
            loss=model(input_ids=ids,attention_mask=mask,labels=labels,use_cache=False).loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),1)
            optimizer.step()
            batch_losses.append(loss.item())
        losses.append(sum(batch_losses)/len(batch_losses))
        print("epoch",epoch+1,"loss",losses[-1],flush=True)
    OUT.mkdir(exist_ok=True)
    model.save_pretrained(OUT/"adapter")
    revision=base.config._commit_hash
    del model,base,optimizer
    reload_base=AutoModelForCausalLM.from_pretrained(MODEL,revision=revision)
    restored=PeftModel.from_pretrained(reload_base,OUT/"adapter")
    after=evaluate(restored,tokenizer,tests)
    rows=[dict(question=q,before=b,after=a) for q,b,a in zip(tests,before,after)]
    def brief(s):
        return 0 < len(s.split()) <= 25 and s.count("?")==1 and s.endswith("?")
    report=dict(model=MODEL,revision=revision,train=len(data),test=len(tests),loss=losses,
                brief_before=sum(map(brief,before)),brief_after=sum(map(brief,after)),examples=rows)
    (OUT/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print("RESULT_JSON "+json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":
    run()

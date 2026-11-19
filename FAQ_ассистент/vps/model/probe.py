import json
from urllib.request import Request, urlopen

history = []
for question in ["У нас две мастерские. Надо распределять заявки клиентов между ними.",
                 "Район узнаём только после получения адреса. Что тогда предложите?"]:
    data = json.dumps(dict(message=question, history=history, facts="")).encode()
    req = Request("http://127.0.0.1:8090/generate", data, {"Content-Type": "application/json"})
    with urlopen(req, timeout=65) as response:
        answer = json.load(response)["answer"]
    if not answer.strip():
        raise RuntimeError("Пустой ответ")
    history.append([question, answer])
    print("Клиент:", question, "\nМодель:", answer, flush=True)

import json
from pathlib import Path

here = Path(__file__).resolve().parent
def continuation(first, answer, followup):
    return f"{first}\n\n### Response:\n{answer}\n### Instruction:\n{followup}"

rows = json.loads((here.parent / "v3/train.json").read_text())
for line in (here / "dialogues.txt").read_text().splitlines():
    first, clarifier, followup, answer = line.split("|")
    rows.append({"instruction": first, "output": clarifier})
    rows.append({"instruction": continuation(first, clarifier, followup), "output": answer})
tests = [
    continuation("Заказы делят две мастерские по районам.", "Как узнаёте район?", "Только после получения адреса. Что предложите?"),
    continuation("Заказы делят две мастерские по специализации.", "Как узнаёте тип техники?", "Из фото шильдика. Что предложите?"),
    continuation("Мы возим мебель. Цена зависит от этажа.", "Когда узнаёте этаж?", "При звонке после оформления. Когда назвать стоимость?"),
    continuation("У заявки два согласующих.", "В каком порядке они отвечают?", "Юрист подключается после руководителя. Что предложите?"),
    continuation("Ведём три разных прайса.", "Какой показать клиенту?", "Это зависит от договора. Что предложите?"),
]
assert len({r['instruction'] for r in rows}) == len(rows)
assert set(tests).isdisjoint(r['instruction'] for r in rows)
for name, value in [('train', rows), ('test', tests)]:
    (here / f'{name}.json').write_text(json.dumps(value, ensure_ascii=False, indent=2))

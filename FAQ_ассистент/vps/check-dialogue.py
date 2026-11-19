import json
import re
import sys
from urllib.request import Request, urlopen

base = sys.argv[1]
def ask(question, history):
    body = json.dumps(dict(message=question, history=history)).encode()
    request = Request(base + '/chat', body, {'Content-Type': 'application/json'})
    with urlopen(request, timeout=95) as res:
        data = json.load(res)
    assert data['model'] == 'pulat-qwen', data
    answer = data['answer']
    print(question, '\n', answer, flush=True)
    return answer

for first, second, clues in [
    ('У нас две мастерские, заявки между ними делим по району.', 'Район узнаём только после получения адреса. Как распределить заявку?', ['адрес', 'район|территори', 'мастерск|филиал|отделени']),
    ('У нас две мастерские. Одна чинит телефоны, вторая ноутбуки.', 'Клиент присылает только фото техники. Как выбрать, куда отправить заявку?', ['фото|сним|изображен', 'телефон|ноутбук|тип|вид|модел']),
]:
    a = ask(first, [])
    b = ask(second, [[first, a]]).lower()
    assert all(re.search(clue,b) for clue in clues) and not re.search('₽|рубл',b), 'Ответ требует ручной проверки'
price=ask('Сколько стоит Telegram-бот для заявок?', [])
assert '30 000' in price and 'обсуд' in price.lower()
assert not re.search(r'Какие конкретные шаги вы планируете', b, re.I)

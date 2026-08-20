# Pulat GRP Competitor AI

Персональный мультимодальный анализатор рынка оборудования и услуг гидроразрыва пласта. Проект принимает конкурентные тексты и изображения, открывает разрешённые сайты через Selenium, возвращает отраслевой JSON и хранит последние 10 запросов.

## Конкуренты и материалы

В `data/` подготовлены четыре PDF-карточки по официальным материалам:

- Halliburton - электрический ГРП ZEUS и цифровая автоматизация OCTIV;
- Liberty Energy - low-emission флоты, digiFrac и digiPrime;
- Jereh - электрическое и турбинное оборудование ГРП;
- SLB - многостадийный ГРП, моделирование и инженерные решения.

Источники: [Halliburton Hydraulic Fracturing](https://www.halliburton.com/en/completions/stimulation/hydraulic-fracturing), [Liberty Hydraulic Fracturing](https://libertyenergy.com/completion-services/frac/), [Jereh Oilfield Equipment](https://www.jereh.com/en/business-area/oilfield-equipment), [SLB Fracturing Services](https://www.slb.com/products-and-services/innovating-in-oil-and-gas/completions/stimulation/fracturing-services).

## Что реализовано

- FastAPI: `/analyze_text`, `/analyze_image`, `/parse_demo`, `/history`, `/health`;
- совместимые с заданием алиасы: `/analyzetext`, `/analyzeimage`, `/parsedemo`;
- JSON-схемы с `design_score`, `frac_relevance_score`, `industrial_credibility_score` и `digitalization_potential`;
- ProxyAPI через официальный OpenAI SDK;
- Selenium Chrome с ожиданием загрузки и сохранением скриншота;
- защита парсера: только HTTPS, allowlist доменов, запрет локальных адресов, логинов и нестандартных портов;
- локальная атомарная история на 10 запросов;
- веб-интерфейс и PyQt6 desktop-интерфейс;
- `build.py` для сборки `competitionmonitor.exe` в Windows;
- тесты схем, API, истории, параллельных записей, безопасности URL и сборочной команды.

## Быстрый запуск в Windows

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Откройте `.env` в любом текстовом редакторе и вставьте ключ только после `PROXY_API_KEY=`. Не отправляйте ключ в чат или скриншоты.

```powershell
uvicorn run:app --reload
```

Откройте `http://127.0.0.1:8000`. Документация API: `http://127.0.0.1:8000/docs`.

## Проверка API

Проверка состояния:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Анализ текста:

```powershell
$body = @{text="Halliburton развивает электрический ГРП и автоматизацию операций."; company_name="Halliburton"} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/analyze_text -ContentType "application/json" -Body $body
```

Парсинг настроенного сайта:

```powershell
$body = @{competitor="halliburton"} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/parse_demo -ContentType "application/json" -Body $body
```

## Desktop и EXE

Запуск из исходников:

```powershell
python desktop\main.py
```

Desktop сам поднимает локальный backend на `127.0.0.1:8765`.

Сборка в Windows:

```powershell
python build.py
Copy-Item .env dist\.env
```

Результат: `dist\competitionmonitor.exe`. Файл `.env` должен лежать рядом с `.exe`; он не встраивается в приложение и не передаётся другим людям.

Важно: PyInstaller не является кросс-компилятором. Windows `.exe` необходимо собирать и проверять именно в Windows.

## Безопасность

- ключ хранится только в `.env`, который внесён в `.gitignore`;
- приложение по умолчанию слушает только `127.0.0.1`, а не внешний интерфейс;
- сайты ограничены четырьмя доменами из `backend/config.py`;
- повторно проверяется конечный URL после редиректа;
- входные тексты считаются недоверенными и не могут менять системный промпт;
- локальная история не содержит API-ключа.

## Тесты

```powershell
pytest
python build.py --dry-run
```

Тесты используют изолированный `FakeAI` и не имитируют реальный ответ модели в рабочем приложении. Реальный вызов ProxyAPI проверяется только после добавления собственного ключа.

Подробности API: [docs.md](docs.md). Итог сдачи: [ASSIGNMENT_REPORT.md](ASSIGNMENT_REPORT.md).

"""HTTP interface for the two existing lesson applications; one process per project."""
import argparse
import html
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

PROJECTS = {'5.7': 'Кэширование_RAG', '5.8': 'Финальный_RAG_ассистент'}
PAGE = """<!doctype html><html lang="ru"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Помощник по документам</title>
<main style="font:18px/1.5 system-ui;max-width:46rem;margin:3rem auto;padding:1rem">
<h1>Помощник по документам</h1><form method="post" action="/ask"><label>Ваш вопрос<br>
<textarea name="question" required maxlength="4000" rows="4" style="width:100%"></textarea></label>
<p><button>Получить ответ</button></p></form>{}</main></html>"""

def application(ask):
    def handle(env, start):
        def send(status, body, mime='application/json'):
            data = (json.dumps(body, ensure_ascii=False) if mime == 'application/json' else body).encode()
            start(status, [('Content-Type', mime+'; charset=utf-8'),
                           ('Content-Length', str(len(data))), ('Cache-Control','no-store')])
            return [data]

        method, path = env['REQUEST_METHOD'], env['PATH_INFO']
        if method == 'GET' and path == '/':
            return send('200 OK', PAGE.format(''), 'text/html')
        if method == 'GET' and path == '/health':
            return send('200 OK', {'status':'ready'})
        if path != '/ask':
            return send('404 Not Found', {'error':'Страница не найдена'})
        if method != 'POST':
            return send('405 Method Not Allowed', {'error':'Требуется POST'})
        mime = env.get('CONTENT_TYPE','').split(';')[0]
        if mime not in ('application/json','application/x-www-form-urlencoded'):
            return send('415 Unsupported Media Type', {'error':'Требуется JSON или форма'})
        try:
            length = int(env.get('CONTENT_LENGTH') or 0)
            if not 0 < length <= 65536:
                return send('413 Payload Too Large', {'error':'Пустое или слишком большое тело запроса'})
            raw = env['wsgi.input'].read(length).decode()
            data = json.loads(raw) if mime == 'application/json' else dict(
                (key, values[0]) for key, values in parse_qs(raw).items())
            question = data.get('question') if isinstance(data, dict) else None
            if not isinstance(question,str) or not 0 < len(question.strip()) <= 4000:
                raise ValueError
        except (ValueError, UnicodeError):
            return send('400 Bad Request', {'error':'Введите вопрос длиной до 4000 символов'})
        try:
            result = ask(question.strip())
        except Exception as exc:
            print('Ошибка запроса:', type(exc).__name__, file=sys.stderr, flush=True)
            return send('503 Service Unavailable', {'error':'Не удалось получить ответ'})
        if mime == 'application/json':
            return send('200 OK', result)
        answer = html.escape(result['answer'])
        mode = 'из кэша' if result['from_cache'] else 'новый ответ'
        return send('200 OK', PAGE.format(f'<h2>Ответ</h2><p>{answer}</p><small>{mode}</small>'), 'text/html')
    return handle

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('project', choices=PROJECTS)
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent.parent / PROJECTS[args.project]
    os.chdir(folder)
    sys.path.insert(0, str(folder))
    cleanup = None
    if args.project == '5.8':
        from settings import load_config
        from rag_pipeline import RAGPipeline
        config = load_config()
        config.runtime_dir.mkdir(parents=True, exist_ok=True)
        pipeline = RAGPipeline(config)
        ask = lambda q: pipeline.query(q, source_channel='web')
        cleanup = pipeline.close
    else:
        from main import initialize_system, answer_question
        _, assistant, cache = initialize_system()
        ask = lambda q: answer_question(q, assistant, cache, source_channel='web', detailed=True)
    try:
        with make_server('127.0.0.1', args.port or (8757 if args.project=='5.7' else 8758),
                         application(ask)) as server:
            server.serve_forever()
    finally:
        if cleanup:
            cleanup()

if __name__ == '__main__':
    main()

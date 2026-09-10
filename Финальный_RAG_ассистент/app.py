"""Final lesson application: run python app.py, then ask questions."""
import json, logging, sys
from settings import load_config
from rag_pipeline import RAGPipeline
from provider import ModelError

HELP = '''Команды:
  /help                 помощь
  /stats                модель, документы, кэш и параметры
  /sources              список файлов базы знаний
  /top_k 3              число фрагментов: от 1 до 10
  /source python.txt    поиск только в выбранном файле
  /source all           поиск по всем файлам
  /reindex              обновить индекс после изменения data/
  /clear_cache          очистить кэш ответов
  /exit                 выход
Каждый вопрос обрабатывается отдельно. Добавляйте уточнения в сам вопрос.'''

def display(result):
    print('\n'+result['answer'])
    print('\nНайденные источники:')
    for i, source in enumerate(result['sources'],1):
        print(f"[{i}] {source['source']} — фрагмент {source['chunk']}")
    print(f"Кэш: {'найден' if result['from_cache'] else 'новый ответ'} | Время: {result['seconds']:.6f} с\n")

def main():
    pipeline=None
    try:
        config=load_config()
        config.runtime_dir.mkdir(parents=True,exist_ok=True)
        print('Pulat RAG — ассистент по документам')
        print('Подготовка базы знаний...',flush=True)
        pipeline=RAGPipeline(config)
        print(f'Модель: {config.model} | режим: {config.backend}')
        print(f"Документов: {pipeline.stats()['documents']}; фрагментов: {pipeline.stats()['chunks']}")
        print('Введите вопрос или /help. Модель запускается автоматически при первом новом вопросе.\n')
        while True:
            try:
                question=input('Вы: ').strip()
            except (EOFError,KeyboardInterrupt):
                print('\nДо свидания!')
                break
            try:
                if question.lower() in {'/exit','exit','quit','q'}:
                    print('До свидания!')
                    break
                if not question:
                    print('Введите вопрос.');continue
                command,_,argument=question.partition(' ')
                if command in {'/help','help'}:
                    print(HELP);continue
                if command in {'/stats','stats'}:
                    print(json.dumps(pipeline.stats(),ensure_ascii=False,indent=2));continue
                if command=='/sources':
                    print('\n'.join(pipeline.vector_store.source_names));continue
                if command=='/top_k':
                    pipeline.set_top_k(int(argument));print(f'TOP_K={pipeline.top_k}');continue
                if command=='/source':
                    pipeline.set_source(None if argument.strip()=='all' else argument.strip())
                    print('Источник: '+(pipeline.source or 'все'));continue
                if command=='/reindex':
                    print('Обновление базы...',flush=True)
                    changed=pipeline.reindex()
                    print('Индекс обновлён.' if changed else 'База не изменилась.');continue
                if command in {'/clear_cache','clear'}:
                    pipeline.clear_cache();print('Кэш очищен.');continue
                if command.startswith('/'):
                    print('Неизвестная команда. Используйте /help.');continue
                print('Обрабатываю вопрос...',flush=True)
                display(pipeline.query(question))
            except (ValueError,ModelError) as exc:
                print('Ошибка: '+str(exc))
                with (config.runtime_dir/'errors.log').open('a') as log:
                    log.write(type(exc).__name__+'\n')
            except Exception as exc:
                # Do not print API bodies, keys or potentially sensitive tracebacks.
                print('Ошибка обработки: '+type(exc).__name__+'. Результат не подтверждён.')
                with (config.runtime_dir/'errors.log').open('a') as log:
                    log.write(type(exc).__name__+'\n')
    except Exception as exc:
        print('Не удалось запустить ассистента: '+type(exc).__name__)
        if isinstance(exc,(ValueError,ModelError,FileNotFoundError)):
            print(str(exc))
        return 1
    finally:
        if pipeline is not None:
            pipeline.close()
    return 0

if __name__=='__main__':
    sys.exit(main())

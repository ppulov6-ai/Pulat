"""
Главный файл для запуска RAG-ассистента.

Это точка входа в приложение. Здесь происходит:
1. Загрузка конфигурации
2. Инициализация всех компонентов (кеш, векторная база, RAG)
3. Добавление примеров документов (при первом запуске)
4. Интерактивный цикл общения с пользователем
"""

import os
import json, time, hashlib
from datetime import datetime, timezone
from pathlib import Path
from settings import load_settings

from dotenv import load_dotenv
from embeddings import EmbeddingStore, get_sample_documents
from rag import RAGAssistant
from cache import ResponseCache
from db_logger import DatabaseLogger


def initialize_system():
    """
    Инициализирует все компоненты RAG-системы.
    
    Returns:
        Кортеж (embedding_store, rag_assistant, cache)
    """
    print("=" * 70)
    print("🚀 ИНИЦИАЛИЗАЦИЯ RAG-АССИСТЕНТА")
    print("=" * 70)
    
    # Загружаем переменные окружения из .env файла
    settings = load_settings()
    
    # Проверяем наличие API ключа OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if settings["backend"] == "openai" and not api_key:
        print("⚠️  ВНИМАНИЕ: Не найден OPENAI_API_KEY в переменных окружения!")
        print("   Создайте файл .env и добавьте туда: OPENAI_API_KEY=your_key_here")
        print("   Или установите переменную окружения в системе.")
        print()
    
    # 1. Инициализируем кеш для хранения ответов
    print("\n[1/3] Инициализация кеша...")
    cache = ResponseCache(cache_file=settings["cache_file"])
    
    # 2. Инициализируем векторное хранилище ChromaDB
    print("\n[2/3] Инициализация векторного хранилища...")
    embedding_store = EmbeddingStore(
        collection_name="rag_documents",
        persist_directory=settings["persist_dir"],
        embedding_model=settings["embedding_model"],  # Модель OpenAI для эмбеддингов
        api_key=api_key
    )
    
    # Проверяем, нужно ли добавить примеры документов
    if embedding_store.collection.count() == 0:
        print("\n📝 База данных пуста. Добавляем примеры документов...")
        sample_docs = get_sample_documents()
        embedding_store.add_documents(sample_docs)
    else:
        print(f"✓ В базе уже есть {embedding_store.collection.count()} документов")
    
    # 3. Инициализируем RAG-ассистента
    print("\n[3/3] Инициализация RAG-ассистента...")
    rag_assistant = RAGAssistant(
        embedding_store=embedding_store,
        model=settings["model"],
        temperature=settings["temperature"]
    )
    
    print("\n" + "=" * 70)
    print("✅ СИСТЕМА ГОТОВА К РАБОТЕ")
    print("=" * 70)
    
    log_path = Path(os.getenv("LOG_DB", "results/logs.db"))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    rag_assistant.logger = DatabaseLogger(str(log_path))
    rag_assistant.settings = settings
    records = embedding_store.collection.get(include=["documents", "metadatas"])
    corpus = sorted(zip(records["ids"], records["documents"], records["metadatas"]))
    signature = {"backend": settings["backend"], "model": settings["model"],
                 "temperature": settings["temperature"], "top_k": settings["top_k"],
                 "source": settings["source"], "embedding_model": settings["embedding_model"],
                 "corpus": corpus, "prompt": rag_assistant._create_prompt("", "")}
    cache.namespace = hashlib.sha256(json.dumps(signature, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    print(f"TOP_K={settings['top_k']} | SOURCE_FILTER={settings['source'] or 'нет'} | backend={settings['backend']}")
    return embedding_store, rag_assistant, cache


def answer_question(query: str, rag_assistant: RAGAssistant, cache: ResponseCache, *,
                    source_channel="console", detailed=False) -> str | dict:
    """
    Отвечает на вопрос пользователя с использованием кеша и RAG.
    
    Логика работы:
    1. Проверяем кеш - если ответ есть, возвращаем его
    2. Если ответа нет, выполняем RAG (поиск + генерация)
    3. Сохраняем новый ответ в кеш
    4. Возвращаем ответ
    
    Args:
        query: Вопрос пользователя
        rag_assistant: Экземпляр RAG-ассистента
        cache: Экземпляр кеша
        
    Returns:
        Ответ на вопрос
    """
    started = time.perf_counter()
    settings = rag_assistant.settings
    print("\n" + "=" * 70)
    print(f"ВОПРОС: {query}")
    hit = False
    contexts = []
    try:
        cached = cache.get(query)
        hit = cached is not None
        if hit:
            answer = cached
        else:
            answer, contexts = rag_assistant.generate_response(
                query=query, top_k=settings["top_k"], verbose=True, source=settings["source"])
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("Модель вернула пустой ответ")
            cache.set(query, answer)
        print("\nОТВЕТ:")
        print(answer)
        elapsed = time.perf_counter() - started
        print(f"Кэш найден? {'Да' if hit else 'Нет'} | Время ответа: {elapsed:.6f} с | Записей: {cache.size()}")
        record = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
                  "query": query, "answer": answer, "cache_hit": hit,
                  "seconds": elapsed, "cache_records": cache.size(),
                  "top_k": settings["top_k"], "source_filter": settings["source"],
                  "model": settings["model"], "contexts": contexts}
        path = Path(os.getenv("RESULTS_FILE", "results/requests.jsonl"))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        rag_assistant.logger.log_interaction(query, type(exc).__name__, source=source_channel+".error",
            from_cache=hit, response_time_ms=round((time.perf_counter()-started)*1000))
        print(f"Ошибка обработки запроса: {type(exc).__name__}.")
        raise
    rag_assistant.logger.log_interaction(query, answer, source=source_channel, from_cache=hit,
        response_time_ms=round(elapsed*1000))
    if detailed:
        return {"answer":answer, "from_cache":hit, "seconds":elapsed}
    return answer


def interactive_mode(rag_assistant: RAGAssistant, cache: ResponseCache):
    """
    Интерактивный режим общения с ассистентом.
    
    Пользователь может задавать вопросы в цикле до тех пор,
    пока не введет команду выхода.
    """
    print("\n" + "=" * 70)
    print("💬 ИНТЕРАКТИВНЫЙ РЕЖИМ")
    print("=" * 70)
    print("\nВы можете задавать вопросы ассистенту.")
    print("Для выхода введите: exit, quit, выход или q")
    print("\nДоступные команды:")
    print("  • cache - показать информацию о кеше")
    print("  • clear_cache - очистить кеш")
    print("  • stats - показать статистику системы")
    print()
    
    while True:
        try:
            # Получаем ввод от пользователя
            user_input = input("\n👤 Вы: ").strip()
            
            # Проверяем команды выхода
            if user_input.lower() in ['exit', 'quit', 'выход', 'q', '']:
                print("\n👋 До свидания!")
                break
            
            # Обрабатываем специальные команды
            if user_input.lower() == 'cache':
                print(f"\n📊 Кеш содержит {cache.size()} записей")
                continue
            
            if user_input.lower() == 'clear_cache':
                cache.clear()
                print("\n✓ Кеш очищен")
                continue
            
            if user_input.lower() in ('stats', '/stats'):
                print(rag_assistant.logger.get_stats())
                print(f"\n📊 СТАТИСТИКА СИСТЕМЫ:")
                print(f"  • Документов в ChromaDB: {rag_assistant.embedding_store.collection.count()}")
                print(f"  • Записей в кеше: {cache.size()}")
                print(f"  • Модель LLM: {rag_assistant.model}")
                continue
            
            if user_input.lower() == "/csv":
                print(rag_assistant.logger.export_to_csv(str(rag_assistant.logger.db_path.with_suffix(".csv"))))
                continue

            # Обрабатываем вопрос пользователя
            answer_question(user_input, rag_assistant, cache)
            
        except KeyboardInterrupt:
            print("\n\n👋 Прервано пользователем. До свидания!")
            break
        except Exception as e:
            print(f"\n❌ Ошибка: {str(e)}")


def demo_mode(rag_assistant: RAGAssistant, cache: ResponseCache):
    """
    Демонстрационный режим с заранее заготовленными вопросами.
    
    Показывает работу системы на примерах, включая использование кеша.
    """
    print("\n" + "=" * 70)
    print("🎬 ДЕМОНСТРАЦИОННЫЙ РЕЖИМ")
    print("=" * 70)
    print("\nСейчас будет продемонстрирована работа RAG-ассистента")
    print("на нескольких примерах вопросов.\n")
    
    # Список демо-вопросов
    demo_questions = [
        "Что такое Python и для чего он используется?",
        "Расскажи про RAG и как он работает",
        "Что такое векторные базы данных?",
        "Что такое Python и для чего он используется?"  # Повторный вопрос для демонстрации кеша
    ]
    
    for i, question in enumerate(demo_questions, 1):
        print(f"\n\n{'#' * 70}")
        print(f"ВОПРОС {i} из {len(demo_questions)}")
        print(f"{'#' * 70}")
        
        answer_question(question, rag_assistant, cache)
        
        # Пауза между вопросами (кроме последнего)
        if i < len(demo_questions):
            input("\n[Нажмите Enter для следующего вопроса...]")
    
    print("\n\n" + "=" * 70)
    print("✅ ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА")
    print("=" * 70)


def main():
    """
    Главная функция приложения.
    """
    try:
        # Инициализируем систему
        embedding_store, rag_assistant, cache = initialize_system()
        
        # Выбор режима работы
        print("\n" + "=" * 70)
        print("ВЫБОР РЕЖИМА РАБОТЫ")
        print("=" * 70)
        print("\n1. Интерактивный режим - задавайте свои вопросы")
        print("2. Демонстрационный режим - готовые примеры вопросов")
        print()
        
        mode = input("Выберите режим (1 или 2, по умолчанию 1): ").strip()
        
        if mode == '2':
            demo_mode(rag_assistant, cache)
            
            # Предложить перейти в интерактивный режим
            print("\n" + "=" * 70)
            continue_interactive = input("\nПерейти в интерактивный режим? (y/n): ").strip().lower()
            if continue_interactive in ['y', 'yes', 'д', 'да', '']:
                interactive_mode(rag_assistant, cache)
        else:
            interactive_mode(rag_assistant, cache)
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()


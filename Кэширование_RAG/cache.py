"""Persistent answer cache, isolated by retrieval/model configuration."""
import hashlib
import json
import os
import tempfile
from pathlib import Path

class ResponseCache:
    def __init__(self, cache_file='cache.json', namespace=''):
        self.cache_file = Path(cache_file)
        self.namespace = namespace
        self.cache = {}
        self._load_cache()

    def _get_cache_key(self, query):
        normalized = ' '.join(query.lower().split())
        return hashlib.sha256((self.namespace + '\n' + normalized).encode()).hexdigest()

    def get(self, query):
        result = self.cache.get(self._get_cache_key(query))
        print('✓ Найден ответ в кеше' if result is not None else '✗ Ответ не найден в кеше, выполняем RAG поиск...')
        return result

    def set(self, query, response):
        if not isinstance(response, str) or not response.strip():
            raise ValueError('Нельзя кэшировать пустой ответ')
        key = self._get_cache_key(query)
        updated = {**self.cache, key: response}
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=self.cache_file.parent, prefix='.cache-', suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(updated, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, self.cache_file)
        finally:
            Path(name).unlink(missing_ok=True)
        self.cache = updated
        print('✓ Ответ сохранен в кеше')

    def _load_cache(self):
        if self.cache_file.exists():
            obj = json.loads(self.cache_file.read_text(encoding='utf-8'))
            if not isinstance(obj, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in obj.items()):
                raise ValueError('Повреждённый файл кэша; сохраните его и очистите перед запуском')
            self.cache = obj
            print(f'✓ Загружен кеш с {len(obj)} записями')

    def clear(self):
        self.cache_file.unlink(missing_ok=True)
        self.cache = {}
        print('✓ Кеш очищен')

    def size(self):
        return len(self.cache)

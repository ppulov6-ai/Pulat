"""Configuration for the lesson; local backend is an explicit optional choice."""
import os
from pathlib import Path
from urllib.parse import urlparse
import httpx
from openai import OpenAI
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parent

def load_settings():
    load_dotenv(ROOT / '.env')
    backend = os.getenv('BACKEND', 'openai')
    if backend not in {'local', 'openai'}:
        raise ValueError('BACKEND должен быть local или openai')
    settings = {'backend': backend, 'top_k': int(os.getenv('TOP_K', '3')),
                'source': os.getenv('SOURCE_FILTER', '').strip() or None,
                'model': os.getenv('MODEL_NAME', 'gpt-3.5-turbo'),
                'embedding_model': os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small'),
                'temperature': float(os.getenv('TEMPERATURE', '0.7')),
                'persist_dir': os.getenv('CHROMA_PERSIST_DIR', str(ROOT / 'chroma_db')),
                'cache_file': os.getenv('CACHE_FILE', str(ROOT / 'cache.json'))}
    if settings['top_k'] < 1 or not 0 <= settings['temperature'] <= 2:
        raise ValueError('Неверный TOP_K или TEMPERATURE')
    return settings

def make_client(api_key=None):
    if os.getenv('BACKEND', 'openai') == 'local':
        base = os.getenv('OPENAI_BASE_URL', 'http://127.0.0.1:8765/v1')
        if base != 'http://127.0.0.1:8765/v1':
            raise ValueError('Локальный режим разрешён только на 127.0.0.1:8765')
        # Protocol placeholder for an unauthenticated loopback server; not an API secret.
        return OpenAI(base_url=base, api_key='local-no-auth',
                      http_client=httpx.Client(trust_env=False), timeout=300, max_retries=0)
    key = api_key or os.getenv('OPENAI_API_KEY')
    if not key or key == 'your_openai_api_key_here':
        raise ValueError('OPENAI_API_KEY не настроен')
    base = os.getenv('OPENAI_BASE_URL') or 'https://api.openai.com/v1'
    if urlparse(base).scheme != 'https':
        raise ValueError('Для внешнего API требуется HTTPS')
    return OpenAI(api_key=key, base_url=base, timeout=300, max_retries=0)

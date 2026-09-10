"""Validated settings; keys are only read from environment/local .env."""
from dataclasses import dataclass
from pathlib import Path
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent

@dataclass(frozen=True)
class Config:
    data_dir: Path = ROOT / 'data'
    runtime_dir: Path = ROOT / 'runtime'
    models_dir: Path = ROOT / 'models'
    backend: str = 'local'
    model: str = 'qwen2.5-3b-instruct'
    api_base: str = 'https://api.openai.com/v1'
    top_k: int = 3
    temperature: float = 0.0
    max_tokens: int = 600
    threads: int = 8
    chunk_size: int = 500
    overlap: int = 80
    cache_ttl: int = 86400

    def __post_init__(self):
        if self.backend not in {'local', 'openai'}:
            raise ValueError('BACKEND: local или openai')
        if not 1 <= self.top_k <= 10 or not 0 <= self.temperature <= 1:
            raise ValueError('TOP_K: 1–10; TEMPERATURE: 0–1')
        if not 128 <= self.chunk_size <= 1500 or not 0 <= self.overlap < self.chunk_size:
            raise ValueError('Неверные параметры разбиения текста')
        if not 64 <= self.max_tokens <= 1500 or not 1 <= self.threads <= 32 or self.cache_ttl < 1:
            raise ValueError('Неверные ограничения модели/кэша')
        if self.backend == 'openai':
            if urlparse(self.api_base).scheme != 'https':
                raise ValueError('Внешний API должен использовать HTTPS')
            if not os.getenv('OPENAI_API_KEY'):
                raise ValueError('OPENAI_API_KEY не задан')

def load_config():
    load_dotenv(ROOT / '.env')
    backend = os.getenv('BACKEND', 'local')
    return Config(data_dir=Path(os.getenv('DATA_DIR', str(ROOT/'data'))).resolve(),
                  runtime_dir=Path(os.getenv('RUNTIME_DIR', str(ROOT/'runtime'))).resolve(),
                  models_dir=Path(os.getenv('MODELS_DIR', str(ROOT/'models'))).resolve(),
                  backend=backend,
                  model=os.getenv('MODEL_NAME', 'qwen2.5-3b-instruct' if backend=='local' else 'gpt-4o-mini'),
                  api_base=os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1'),
                  top_k=int(os.getenv('TOP_K','3')),
                  temperature=float(os.getenv('TEMPERATURE','0')),
                  threads=int(os.getenv('MODEL_THREADS','8')),
                  max_tokens=int(os.getenv('MAX_TOKENS','600')))

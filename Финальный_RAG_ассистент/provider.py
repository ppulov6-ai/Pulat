"""OpenAI SDK and an automatically managed, loopback-only Qwen API."""
import atexit
from pathlib import Path
import os, socket, subprocess, sys, time
import httpx
from openai import OpenAI

class ModelError(RuntimeError):
    pass

class ModelProvider:
    def __init__(self, config):
        self.config = config
        self.client = None
        self.process = None
        self.log = None
        self.calls = 0
        self.config.runtime_dir.mkdir(parents=True, exist_ok=True)
        atexit.register(self.close)

    @property
    def identity(self):
        cfg = self.config
        if cfg.backend == 'local':
            path = cfg.models_dir/'qwen/qwen2.5-3b-instruct-q4_k_m.gguf'
            if not path.is_file():
                raise ModelError('Нет весов Qwen. Выполните python download_models.py')
            info = path.stat()
            return ['local', cfg.model, info.st_size, info.st_mtime_ns]
        return ['openai', cfg.model, cfg.api_base]

    def start(self):
        if self.client is not None:
            return
        cfg = self.config
        if cfg.backend == 'openai':
            self.client = OpenAI(api_key=os.environ['OPENAI_API_KEY'], base_url=cfg.api_base,
                                 timeout=180, max_retries=0)
            return
        _ = self.identity
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        self.log = (cfg.runtime_dir/'model_server.log').open('a', encoding='utf-8')
        self.process = subprocess.Popen([
            sys.executable, '-m', 'llama_cpp.server', '--model',
            str(cfg.models_dir/'qwen/qwen2.5-3b-instruct-q4_k_m.gguf'),
            '--model_alias', cfg.model, '--host', '127.0.0.1', '--port', str(port),
            '--n_ctx', '8192', '--n_threads', str(cfg.threads),
            '--n_threads_batch', str(cfg.threads), '--n_batch', '512',
            '--chat_format', 'chatml', '--verbose', 'false'],
            stdout=self.log, stderr=subprocess.STDOUT)
        base = f'http://127.0.0.1:{port}/v1'
        try:
            with httpx.Client(trust_env=False, timeout=2) as probe:
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    if self.process.poll() is not None:
                        raise ModelError('Не запустился локальный API; журнал runtime/model_server.log')
                    try:
                        response = probe.get(base+'/models')
                        if response.status_code == 200:
                            if cfg.model not in [x['id'] for x in response.json()['data']]:
                                raise ModelError('API сообщил другую модель')
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.25)
                else:
                    raise ModelError('Превышено время запуска локального API')
            # This is a protocol placeholder, not a credential, for our child process only.
            self.client = OpenAI(api_key='local-no-auth', base_url=base,
                                 http_client=httpx.Client(trust_env=False), timeout=180, max_retries=0)
        except Exception:
            self.close()
            raise

    def generate(self, system, prompt):
        self.start()
        try:
            response = self.client.chat.completions.create(
                model=self.config.model, temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                messages=[{'role':'system','content':system}, {'role':'user','content':prompt}])
        except Exception as exc:
            raise ModelError('Модель недоступна: ответ не получен и не сохранён в кэш') from exc
        self.calls += 1
        choice = response.choices[0]
        if choice.finish_reason != 'stop':
            raise ModelError('Модель не завершила ответ; результат не сохранён в кэш')
        answer = choice.message.content
        if not isinstance(answer, str) or not answer.strip():
            raise ModelError('Модель вернула пустой ответ')
        return answer.strip()

    def close(self):
        if self.client is not None:
            self.client.close()
            self.client = None
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None
        if self.log is not None:
            self.log.close()
            self.log = None

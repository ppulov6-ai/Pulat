from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8011"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def request(path: str, payload: dict[str, object] | None = None) -> tuple[int, str]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {} if data is None else {"Content-Type": "application/json"}
    req = urllib.request.Request(BASE + path, data=data, headers=headers)
    try:
        with OPENER.open(req, timeout=5) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def main() -> None:
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "run:app", "--host", "127.0.0.1", "--port", "8011", "--log-level", "warning"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        for _ in range(50):
            if process.poll() is not None:
                output, _ = process.communicate(timeout=2)
                raise RuntimeError(f"Backend завершился при запуске: {output}")
            try:
                status, _ = request("/health")
                if status == 200:
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("Backend не запустился за 5 секунд")

        health_status, health_body = request("/health")
        index_status, index_body = request("/")
        schema_status, _ = request("/openapi.json")
        no_key_status, no_key_body = request(
            "/analyze_text",
            {"text": "Описание конкурентной технологии гидроразрыва пласта для проверки."},
        )
        bad_url_status, bad_url_body = request(
            "/parse_demo", {"url": "https://example.com/"}
        )

        assert health_status == 200 and json.loads(health_body)["status"] == "ok"
        assert index_status == 200 and "Pulat GRP Competitor AI" in index_body
        assert schema_status == 200
        assert no_key_status == 503 and "PROXY_API_KEY" in no_key_body
        assert bad_url_status == 400 and "config.py" in bad_url_body
        print(
            json.dumps(
                {
                    "health": health_status,
                    "index": index_status,
                    "openapi": schema_status,
                    "no_key": no_key_status,
                    "unsafe_url": bad_url_status,
                },
                ensure_ascii=False,
            )
        )
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    main()

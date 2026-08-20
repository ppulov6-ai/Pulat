from __future__ import annotations

import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
ENV_FILE = (
    Path(sys.executable).resolve().parent / ".env"
    if getattr(sys, "frozen", False)
    else PROJECT_ROOT / ".env"
)

COMPETITOR_URLS: dict[str, str] = {
    "halliburton": "https://www.halliburton.com/en/completions/stimulation/hydraulic-fracturing",
    "liberty": "https://libertyenergy.com/completion-services/frac/",
    "jereh": "https://www.jereh.com/en/business-area/oilfield-equipment",
    "slb": "https://www.slb.com/products-and-services/innovating-in-oil-and-gas/completions/stimulation/fracturing-services",
}


def _writable_runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(os.getenv("LOCALAPPDATA") or Path.home())
        return base / "PulatGRPCompetitorAI"
    return PROJECT_ROOT / "runtime"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    proxy_api_key: str = ""
    proxy_api_base_url: str = "https://api.proxyapi.ru/openai/v1"
    openai_model: str = "gpt-4o-mini"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    parser_timeout_seconds: int = 25
    parser_max_text_chars: int = 20_000
    max_history_items: int = 10
    max_image_bytes: int = 10 * 1024 * 1024
    headless_browser: bool = True

    @property
    def runtime_dir(self) -> Path:
        path = _writable_runtime_dir()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def history_file(self) -> Path:
        return self.runtime_dir / "history.json"

    @property
    def screenshot_dir(self) -> Path:
        path = self.runtime_dir / "parser_screenshots"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def allowed_hosts(self) -> set[str]:
        from urllib.parse import urlparse

        return {
            (urlparse(url).hostname or "").lower()
            for url in COMPETITOR_URLS.values()
        }


settings = Settings()

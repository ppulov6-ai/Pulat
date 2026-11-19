from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
import socket
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

from backend.config import settings


logger = logging.getLogger(__name__)


class ParserSecurityError(ValueError):
    pass


class ParsingService:
    """Selenium parser restricted to the configured public competitor hosts."""

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="selenium")

    @staticmethod
    def _host_allowed(host: str) -> bool:
        host = host.lower().rstrip(".")
        return any(host == allowed or host.endswith(f".{allowed}") for allowed in settings.allowed_hosts)

    @classmethod
    def validate_url(cls, url: str, resolve_dns: bool = True) -> str:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise ParserSecurityError("Разрешены только HTTPS-ссылки")
        if parsed.username or parsed.password:
            raise ParserSecurityError("Ссылки с логином или паролем запрещены")
        host = (parsed.hostname or "").lower()
        if not host or not cls._host_allowed(host):
            raise ParserSecurityError("Домен не входит в список конкурентов из config.py")
        if parsed.port not in (None, 443):
            raise ParserSecurityError("Нестандартные порты запрещены")
        if resolve_dns:
            try:
                addresses = {
                    item[4][0]
                    for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
                }
            except socket.gaierror as exc:
                raise ParserSecurityError("Не удалось проверить DNS домена") from exc
            for address in addresses:
                ip = ipaddress.ip_address(address)
                if not ip.is_global:
                    raise ParserSecurityError("Домен ведёт на закрытый или локальный адрес")
        return url

    def _make_driver(self) -> webdriver.Chrome:
        options = Options()
        if settings.headless_browser:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1440,1200")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-notifications")
        options.add_argument("--lang=ru-RU")
        options.set_capability("pageLoadStrategy", "eager")
        return webdriver.Chrome(options=options)

    @staticmethod
    def _safe_file_stem(host: str) -> str:
        return re.sub(r"[^a-z0-9.-]+", "-", host.lower()).strip("-")[:80]

    def _parse_sync(self, url: str) -> dict[str, str | None]:
        safe_url = self.validate_url(url)
        driver: webdriver.Chrome | None = None
        try:
            driver = self._make_driver()
            driver.set_page_load_timeout(settings.parser_timeout_seconds)
            driver.get(safe_url)
            WebDriverWait(driver, settings.parser_timeout_seconds).until(
                lambda browser: browser.execute_script("return document.readyState")
                in {"interactive", "complete"}
            )

            final_url = driver.current_url
            self.validate_url(final_url)
            soup = BeautifulSoup(driver.page_source, "html.parser")
            for node in soup(["script", "style", "noscript", "svg"]):
                node.decompose()
            title = soup.title.get_text(" ", strip=True) if soup.title else None
            h1_node = soup.find("h1")
            h1 = h1_node.get_text(" ", strip=True) if h1_node else None
            text = " ".join(soup.stripped_strings)[: settings.parser_max_text_chars]

            host = urlparse(final_url).hostname or "competitor"
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            screenshot = settings.screenshot_dir / f"{self._safe_file_stem(host)}-{timestamp}.png"
            driver.save_screenshot(str(screenshot))
            return {
                "url": final_url,
                "title": title,
                "h1": h1,
                "text": text,
                "screenshot_file": str(screenshot),
            }
        except TimeoutException as exc:
            raise RuntimeError("Сайт не загрузился за отведённое время") from exc
        except WebDriverException as exc:
            logger.warning("Ошибка Selenium: %s", type(exc).__name__)
            raise RuntimeError("Chrome/Selenium не смог открыть сайт") from exc
        finally:
            if driver is not None:
                driver.quit()

    async def parse(self, url: str) -> dict[str, str | None]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._parse_sync, url)


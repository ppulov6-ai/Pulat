from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from backend.models.schemas import HistoryItem


class HistoryService:
    """Thread-safe, atomic storage for the ten latest local requests."""

    def __init__(self, file_path: Path, max_items: int = 10) -> None:
        self.file_path = Path(file_path)
        self.max_items = max_items
        self._lock = threading.RLock()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _read_unlocked(self) -> list[HistoryItem]:
        if not self.file_path.exists():
            return []
        try:
            payload = json.loads(self.file_path.read_text(encoding="utf-8"))
            return [HistoryItem.model_validate(item) for item in payload]
        except (json.JSONDecodeError, OSError, ValueError):
            corrupt = self.file_path.with_suffix(
                f".corrupt-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.json"
            )
            try:
                os.replace(self.file_path, corrupt)
            except OSError:
                pass
            return []

    def _write_unlocked(self, items: list[HistoryItem]) -> None:
        payload = [item.model_dump(mode="json") for item in items[-self.max_items :]]
        temporary = self.file_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temporary, self.file_path)

    def list(self) -> list[HistoryItem]:
        with self._lock:
            return self._read_unlocked()

    def add(
        self,
        request_type: Literal["text", "image", "parse"],
        request_summary: str,
        response: dict[str, Any],
    ) -> HistoryItem:
        item = HistoryItem(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            request_type=request_type,
            request_summary=request_summary[:300],
            response=response,
        )
        with self._lock:
            items = self._read_unlocked()
            items.append(item)
            self._write_unlocked(items)
        return item

    def clear(self) -> None:
        with self._lock:
            self._write_unlocked([])


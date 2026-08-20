from concurrent.futures import ThreadPoolExecutor

from backend.services.history_service import HistoryService


def test_history_keeps_ten_latest_atomically(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.json", max_items=10)

    def add(index: int) -> None:
        service.add("text", f"request-{index}", {"index": index})

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(add, range(40)))

    items = service.list()
    assert len(items) == 10
    assert len({item.id for item in items}) == 10


def test_corrupt_history_is_quarantined(tmp_path) -> None:
    file = tmp_path / "history.json"
    file.write_text("not-json", encoding="utf-8")
    service = HistoryService(file)
    assert service.list() == []
    assert list(tmp_path.glob("history.corrupt-*.json"))


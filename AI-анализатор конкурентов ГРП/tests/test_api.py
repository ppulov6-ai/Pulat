import base64

from fastapi.testclient import TestClient

import backend.main as main
from backend.models.schemas import CompetitorTextAnalysis, ImageAnalysis


class FakeAI:
    async def analyze_text(self, text: str, company_name: str | None = None):
        return CompetitorTextAnalysis(
            company_name=company_name or "Тест",
            market_position="Поставщик ГРП",
            strengths=["Сильная сторона 1", "Сильная сторона 2", "Сильная сторона 3"],
            weaknesses=["Пробел 1", "Пробел 2", "Пробел 3"],
            technologies=["Технология 1", "Технология 2", "Технология 3"],
            risks=["Риск 1", "Риск 2", "Риск 3"],
            recommendations=["Шаг 1", "Шаг 2", "Шаг 3"],
            frac_relevance_score=8,
            digitalization_potential=7,
            summary="Тестовый ответ из изолированного теста.",
        )

    async def analyze_image(self, image_base64: str, mime_type: str, company_name: str | None = None):
        assert base64.b64decode(image_base64)
        return ImageAnalysis(
            company_name=company_name or "Тест",
            description="Промышленный визуал",
            design_score=7,
            industrial_credibility_score=8,
            frac_relevance_score=9,
            digitalization_potential=6,
            marketing_insights=["Инсайт 1", "Инсайт 2", "Инсайт 3"],
            visual_weaknesses=["Минус 1", "Минус 2", "Минус 3"],
            recommendations=["Шаг 1", "Шаг 2", "Шаг 3"],
            summary="Тестовый ответ.",
        )

    async def analyze_web_page(self, url: str, title: str | None, h1: str | None, text: str):
        return await self.analyze_text(text, "Halliburton")


class FakeParser:
    async def parse(self, url: str):
        return {
            "url": url,
            "title": "Hydraulic Fracturing",
            "h1": "Hydraulic fracturing",
            "text": "Официальное описание технологии гидроразрыва пласта.",
            "screenshot_file": "/isolated-test/screenshot.png",
        }


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def test_health_and_text_endpoint(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(main, "openai_service", FakeAI())
    monkeypatch.setattr(main, "history_service", main.HistoryService(tmp_path / "history.json"))
    client = TestClient(main.app)
    assert client.get("/health").status_code == 200
    response = client.post(
        "/analyze_text",
        json={"text": "Описание конкурентной технологии гидроразрыва пласта.", "company_name": "Компания"},
    )
    assert response.status_code == 200
    assert response.json()["frac_relevance_score"] == 8
    assert client.get("/history").json()["total"] == 1


def test_image_endpoint_and_alias(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(main, "openai_service", FakeAI())
    monkeypatch.setattr(main, "history_service", main.HistoryService(tmp_path / "history.json"))
    client = TestClient(main.app)
    response = client.post(
        "/analyzeimage",
        files={"file": ("sample.png", PNG_1X1, "image/png")},
        data={"company_name": "Компания"},
    )
    assert response.status_code == 200
    assert response.json()["design_score"] == 7


def test_image_rejects_wrong_type() -> None:
    client = TestClient(main.app)
    response = client.post(
        "/analyze_image",
        files={"file": ("sample.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 415


def test_image_rejects_invalid_payload_with_image_mime() -> None:
    client = TestClient(main.app)
    response = client.post(
        "/analyze_image",
        files={"file": ("broken.png", b"not an image", "image/png")},
    )
    assert response.status_code == 400


def test_parse_alias_saves_history(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(main, "openai_service", FakeAI())
    monkeypatch.setattr(main, "parsing_service", FakeParser())
    monkeypatch.setattr(main, "history_service", main.HistoryService(tmp_path / "history.json"))
    client = TestClient(main.app)
    response = client.post("/parsedemo", json={"competitor": "halliburton"})
    assert response.status_code == 200
    assert response.json()["analysis"]["company_name"] == "Halliburton"
    assert client.get("/history").json()["items"][0]["request_type"] == "parse"

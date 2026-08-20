from __future__ import annotations

import base64
import io
import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

from backend.config import COMPETITOR_URLS, PROJECT_ROOT, settings
from backend.models.schemas import (
    CompetitorTextAnalysis,
    HistoryResponse,
    ImageAnalysis,
    ParseRequest,
    ParsedPage,
    TextAnalysisRequest,
)
from backend.services import (
    HistoryService,
    MissingAPIKeyError,
    OpenAIService,
    ParserSecurityError,
    ParsingService,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Pulat GRP Competitor AI",
    version="1.0.0",
    description="Персональный AI-анализатор рынка оборудования и услуг ГРП",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:8765",
        "http://localhost:8765",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

openai_service = OpenAIService()
parsing_service = ParsingService()
history_service = HistoryService(settings.history_file, settings.max_history_items)


def _service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, MissingAPIKeyError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, ParserSecurityError):
        return HTTPException(status_code=400, detail=str(exc))
    logger.exception("Ошибка обработки запроса: %s", type(exc).__name__)
    return HTTPException(status_code=502, detail="Внешний сервис не выполнил запрос")


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "api_configured": bool(settings.proxy_api_key),
        "competitors": list(COMPETITOR_URLS),
    }


@app.post("/analyze_text", response_model=CompetitorTextAnalysis)
async def analyze_text(request: TextAnalysisRequest) -> CompetitorTextAnalysis:
    try:
        result = await openai_service.analyze_text(request.text, request.company_name)
        history_service.add("text", request.text[:180], result.model_dump())
        return result
    except Exception as exc:
        raise _service_error(exc) from exc


@app.post("/analyze_image", response_model=ImageAnalysis)
async def analyze_image(
    file: UploadFile = File(...),
    company_name: str | None = Form(default=None),
) -> ImageAnalysis:
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=415, detail="Разрешены JPEG, PNG и WEBP")
    payload = await file.read(settings.max_image_bytes + 1)
    if len(payload) > settings.max_image_bytes:
        raise HTTPException(status_code=413, detail="Изображение превышает 10 МБ")
    try:
        with Image.open(io.BytesIO(payload)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail="Файл не является корректным изображением") from exc
    try:
        result = await openai_service.analyze_image(
            base64.b64encode(payload).decode("ascii"),
            file.content_type,
            company_name,
        )
        history_service.add("image", file.filename or "image", result.model_dump())
        return result
    except Exception as exc:
        raise _service_error(exc) from exc


@app.post("/parse_demo", response_model=ParsedPage)
async def parse_demo(request: ParseRequest) -> ParsedPage:
    url = str(request.url) if request.url else COMPETITOR_URLS[request.competitor or ""]
    try:
        page = await parsing_service.parse(url)
        analysis = await openai_service.analyze_web_page(
            str(page["url"]),
            page.get("title"),
            page.get("h1"),
            str(page.get("text") or ""),
        )
        result = ParsedPage(
            url=str(page["url"]),
            title=page.get("title"),
            h1=page.get("h1"),
            text_excerpt=str(page.get("text") or "")[:1000],
            screenshot_file=page.get("screenshot_file"),
            analysis=analysis,
        )
        history_service.add("parse", result.url, result.model_dump())
        return result
    except Exception as exc:
        raise _service_error(exc) from exc


# Aliases preserve the endpoint spelling used in the homework text.
app.add_api_route("/analyzetext", analyze_text, methods=["POST"], include_in_schema=False)
app.add_api_route("/analyzeimage", analyze_image, methods=["POST"], include_in_schema=False)
app.add_api_route("/parsedemo", parse_demo, methods=["POST"], include_in_schema=False)


@app.get("/history", response_model=HistoryResponse)
async def get_history() -> HistoryResponse:
    items = history_service.list()
    return HistoryResponse(items=items, total=len(items))


@app.delete("/history", status_code=204)
async def clear_history() -> None:
    history_service.clear()


frontend_dir = PROJECT_ROOT / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(frontend_dir / "index.html")


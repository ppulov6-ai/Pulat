from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class TextAnalysisRequest(BaseModel):
    text: str = Field(min_length=20, max_length=40_000)
    company_name: str | None = Field(default=None, max_length=120)

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 20:
            raise ValueError("Текст должен содержать не менее 20 символов")
        return value


class CompetitorTextAnalysis(BaseModel):
    company_name: str
    market_position: str
    strengths: list[str] = Field(min_length=3, max_length=5)
    weaknesses: list[str] = Field(min_length=3, max_length=5)
    technologies: list[str] = Field(min_length=3, max_length=7)
    risks: list[str] = Field(min_length=3, max_length=5)
    recommendations: list[str] = Field(min_length=3, max_length=5)
    frac_relevance_score: int = Field(ge=0, le=10)
    digitalization_potential: int = Field(ge=0, le=10)
    summary: str


class ImageAnalysis(BaseModel):
    company_name: str
    description: str
    design_score: int = Field(ge=0, le=10)
    industrial_credibility_score: int = Field(ge=0, le=10)
    frac_relevance_score: int = Field(ge=0, le=10)
    digitalization_potential: int = Field(ge=0, le=10)
    marketing_insights: list[str] = Field(min_length=3, max_length=5)
    visual_weaknesses: list[str] = Field(min_length=3, max_length=5)
    recommendations: list[str] = Field(min_length=3, max_length=5)
    summary: str


class ParseRequest(BaseModel):
    competitor: Literal["halliburton", "liberty", "jereh", "slb"] | None = None
    url: HttpUrl | None = None

    @model_validator(mode="after")
    def require_one_target(self) -> "ParseRequest":
        if not self.competitor and not self.url:
            raise ValueError("Укажите competitor или url")
        return self


class ParsedPage(BaseModel):
    url: str
    title: str | None = None
    h1: str | None = None
    text_excerpt: str
    screenshot_file: str | None = None
    analysis: CompetitorTextAnalysis


class HistoryItem(BaseModel):
    id: str
    timestamp: datetime
    request_type: Literal["text", "image", "parse"]
    request_summary: str
    response: dict[str, Any]


class HistoryResponse(BaseModel):
    items: list[HistoryItem]
    total: int


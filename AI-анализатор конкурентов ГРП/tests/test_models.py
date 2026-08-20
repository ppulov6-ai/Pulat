import pytest
from pydantic import ValidationError

from backend.models.schemas import CompetitorTextAnalysis, ImageAnalysis, TextAnalysisRequest


def test_text_request_rejects_short_input() -> None:
    with pytest.raises(ValidationError):
        TextAnalysisRequest(text="слишком коротко")


def test_industry_scores_are_bounded() -> None:
    with pytest.raises(ValidationError):
        ImageAnalysis(
            company_name="Test",
            description="Описание",
            design_score=11,
            industrial_credibility_score=5,
            frac_relevance_score=5,
            digitalization_potential=5,
            marketing_insights=["1", "2", "3"],
            visual_weaknesses=["1", "2", "3"],
            recommendations=["1", "2", "3"],
            summary="Вывод",
        )


def test_text_analysis_requires_three_items() -> None:
    with pytest.raises(ValidationError):
        CompetitorTextAnalysis(
            company_name="Test",
            market_position="Позиция",
            strengths=["1"],
            weaknesses=["1", "2", "3"],
            technologies=["1", "2", "3"],
            risks=["1", "2", "3"],
            recommendations=["1", "2", "3"],
            frac_relevance_score=5,
            digitalization_potential=5,
            summary="Вывод",
        )


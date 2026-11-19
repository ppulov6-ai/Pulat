import pytest

from backend.services.parsing_service import ParserSecurityError, ParsingService


@pytest.mark.parametrize(
    "url",
    [
        "http://www.halliburton.com/en/completions",
        "https://127.0.0.1/private",
        "https://localhost/private",
        "https://example.com/",
        "https://user:pass@www.halliburton.com/",
        "https://www.halliburton.com:8443/",
    ],
)
def test_parser_blocks_unsafe_targets(url: str) -> None:
    with pytest.raises(ParserSecurityError):
        ParsingService.validate_url(url, resolve_dns=False)


def test_parser_accepts_configured_https_host_without_dns() -> None:
    url = "https://www.halliburton.com/en/completions/stimulation/hydraulic-fracturing"
    assert ParsingService.validate_url(url, resolve_dns=False) == url


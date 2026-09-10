"""Isolated edge checks. Test doubles are never used by the homework pipeline."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import json
import os
import traceback

from cache import ResponseCache
from embeddings import EmbeddingStore
from main import answer_question


def expect_error(error_type, action):
    try:
        action()
    except error_type:
        return
    raise AssertionError(f"Expected {error_type.__name__}")


def run_checks():
    passed = []
    with TemporaryDirectory(prefix="rag57-edge-") as temp:
        root = Path(temp)
        cache_path = root / "cache.json"
        query = "Что такое RAG?"
        namespace = lambda top_k, source: json.dumps(
            {"top_k": top_k, "source": source}, sort_keys=True
        )
        first = ResponseCache(cache_path, namespace(3, None))
        first.set(query, "Saved response")
        reloaded = ResponseCache(cache_path, namespace(3, None))
        assert reloaded.get(query) == "Saved response"
        assert reloaded.size() == 1
        passed.append("PASS cache save/reload")

        changed_k = ResponseCache(cache_path, namespace(7, None))
        assert changed_k.get(query) is None
        changed_source = ResponseCache(cache_path, namespace(3, "Python"))
        assert changed_source.get(query) is None
        assert reloaded.get(query) == "Saved response"
        passed.append("PASS cache namespace isolation: TOP_K and source")

        previous_bytes = cache_path.read_bytes()
        expect_error(ValueError, lambda: reloaded.set("Empty", "  "))
        assert cache_path.read_bytes() == previous_bytes
        assert reloaded.size() == 1
        passed.append("PASS empty answer rejected without writing")

        broken = root / "broken.json"
        broken.write_text("{not valid JSON", encoding="utf-8")
        expect_error(ValueError, lambda: ResponseCache(broken))
        broken.write_text('["wrong schema"]', encoding="utf-8")
        expect_error(ValueError, lambda: ResponseCache(broken))
        passed.append("PASS malformed JSON and wrong schema fail explicitly")

        settings = {"top_k": 3, "source": None, "model": "test-double"}
        calls = []

        def forbidden_generator(**kwargs):
            calls.append(kwargs)
            raise AssertionError("Generator must not run on cache hit")

        assistant = SimpleNamespace(settings=settings, generate_response=forbidden_generator)
        prior_results = os.environ.get("RESULTS_FILE")
        os.environ["RESULTS_FILE"] = str(root / "requests.jsonl")
        try:
            assert answer_question(query, assistant, reloaded) == "Saved response"
            assert calls == []
            rows = [json.loads(line) for line in (root / "requests.jsonl").read_text().splitlines()]
            assert len(rows) == 1 and rows[0]["cache_hit"] is True
            assert rows[0]["seconds"] >= 0
            passed.append("PASS cache hit bypasses generation and records actual timer")

            def failing_generator(**kwargs):
                calls.append(kwargs)
                raise RuntimeError("Deliberate isolated test failure")

            assistant.generate_response = failing_generator
            before_size = reloaded.size()
            before_bytes = cache_path.read_bytes()
            expect_error(RuntimeError, lambda: answer_question("Uncached failing query", assistant, reloaded))
            assert len(calls) == 1
            assert reloaded.size() == before_size
            assert cache_path.read_bytes() == before_bytes
            assert reloaded.get("Uncached failing query") is None
            assert len((root / "requests.jsonl").read_text().splitlines()) == 1
            passed.append("PASS generation exception propagates without caching or success record")
        finally:
            if prior_results is None:
                os.environ.pop("RESULTS_FILE", None)
            else:
                os.environ["RESULTS_FILE"] = prior_results

        store = EmbeddingStore.__new__(EmbeddingStore)
        assert store._create_chunks("x" * 500) == ["x" * 500]
        assert [len(s) for s in store._create_chunks("x" * 501)] == [500, 51]
        assert store._create_chunks("") == []
        for size, overlap in [(0, 0), (-1, 0), (500, -1), (500, 500), (500, 501)]:
            expect_error(ValueError, lambda s=size, o=overlap: store._create_chunks("text", s, o))
        passed.append("PASS chunk boundary 500/501, empty text and invalid parameters")
    return passed


if __name__ == "__main__":
    captured = StringIO()
    output = Path(__file__).resolve().parent / "results" / "edge_checks.log"
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with redirect_stdout(captured):
            checks = run_checks()
    except Exception:
        output.write_text(
            "ISOLATED EDGE CHECKS — FAILED\n" + captured.getvalue() + traceback.format_exc(),
            encoding="utf-8",
        )
        raise
    report = (
        "ISOLATED EDGE CHECKS\n"
        "Temporary files and explicit test doubles only; no model inference results.\n"
        "Live .env, cache.json and ChromaDB are not modified.\n\n"
        + "\n".join(checks)
        + f"\n\nRESULT: {len(checks)}/{len(checks)} checks passed.\n"
    )
    output.write_text(report, encoding="utf-8")
    print(report, end="")

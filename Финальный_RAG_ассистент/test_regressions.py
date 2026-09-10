"""Fast isolated regressions. Doubles test failure paths, not model quality.

Real inference and retrieval are checked separately by the integration run.
Run: python -m unittest -v test_regressions
"""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cache import RAGCache
from provider import ModelError, ModelProvider
from rag_pipeline import RAGPipeline
from settings import Config
from vector_store import chunk_text
import app


class ChunkTests(unittest.TestCase):
    def test_short_fact_is_preserved(self):
        text = 'Ответить за 2 минуты.'
        self.assertEqual([p['text'] for p in chunk_text(text)], [text])

    def test_long_paragraph_after_short_has_bounded_complete_coverage(self):
        text = 'А' * 100 + '\n\n' + 'Б' * 1000
        parts = chunk_text(text, 500, 80)
        covered = set()
        for part in parts:
            self.assertLessEqual(part['end'] - part['start'], 500)
            self.assertEqual(part['text'], text[part['start']:part['end']].strip())
            covered.update(range(part['start'], part['end']))
        self.assertEqual(covered, set(range(len(text))))
        self.assertEqual(parts[-1]['end'], len(text))

    def test_zero_overlap_does_not_repeat_previous_text(self):
        text = 'А' * 100 + '\n\n' + 'Б' * 1000
        parts = chunk_text(text, 500, 0)
        self.assertTrue(all(a['end'] == b['start'] for a, b in zip(parts, parts[1:])))
        self.assertEqual(sum(p['end'] - p['start'] for p in parts), len(text))

    def test_invalid_parameters_and_empty_document(self):
        for size, overlap in [(0, 0), (10, -1), (10, 10), (10, 11)]:
            with self.subTest(size=size, overlap=overlap), self.assertRaises(ValueError):
                chunk_text('fact', size, overlap)
        self.assertEqual(chunk_text(' \n\t'), [])


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = RAGCache(Path(self.temp.name) / 'cache.sqlite3', ttl=60)
        self.scope = {'model': 'test-model', 'corpus': 'v1', 'top_k': 3, 'source': None}
        self.result = {'answer': 'Факт [1].', 'sources': [
            {'id': 'document-id', 'source': 'python.txt', 'chunk': 2,
             'text': 'Факт.', 'distance': 0.125}]}

    def test_sources_survive_disk_roundtrip(self):
        self.cache.set('Вопрос?', self.scope, self.result)
        reopened = RAGCache(self.cache.path, ttl=60)
        self.assertEqual(reopened.get('Вопрос?', self.scope), self.result)
        self.assertEqual(reopened.count(), 1)

    def test_namespace_changes_never_reuse_old_answer(self):
        self.cache.set('Вопрос?', self.scope, self.result)
        for name, value in [('model', 'other'), ('corpus', 'v2'), ('top_k', 7), ('source', 'python.txt')]:
            with self.subTest(name=name):
                self.assertIsNone(self.cache.get('Вопрос?', {**self.scope, name: value}))
        self.assertIsNone(self.cache.get('вопрос?', self.scope))
        self.assertIsNone(self.cache.get('Вопрос!', self.scope))

    def test_expiration_boundary_evicts_record(self):
        with patch('cache.time.time', return_value=1000):
            self.cache.set('Вопрос?', self.scope, self.result)
        with patch('cache.time.time', return_value=1059.9):
            self.assertIsNotNone(self.cache.get('Вопрос?', self.scope))
        with patch('cache.time.time', return_value=1060):
            self.assertIsNone(self.cache.get('Вопрос?', self.scope))
            self.assertEqual(self.cache.count(), 0)

    def test_clear_and_empty_answer_rejection(self):
        with self.assertRaises(ValueError):
            self.cache.set('Вопрос?', self.scope, {'answer': ' ', 'sources': []})
        self.cache.set('Вопрос?', self.scope, self.result)
        self.cache.clear()
        self.assertEqual(self.cache.count(), 0)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Config(runtime_dir=Path(self.temp.name))
        self.source = {'id': 'chunk-id', 'source': 'python.txt', 'chunk': 1,
                       'text': 'Python — язык программирования.', 'distance': 0.1}
        self.store = Mock(version='v1', source_names=['python.txt'])
        self.store.search.return_value = [self.source]
        self.provider = Mock(identity=['test-only'], calls=0)
        self.provider.generate.return_value = 'Python — язык программирования [1].'
        with patch('rag_pipeline.VectorStore', return_value=self.store):
            self.pipeline = RAGPipeline(self.config, provider=self.provider)

    def test_repeat_skips_retrieval_and_generation_preserves_sources(self):
        first = self.pipeline.query('Что такое Python?')
        repeat = self.pipeline.query('Что такое Python?')
        self.assertFalse(first['from_cache'])
        self.assertTrue(repeat['from_cache'])
        self.assertEqual(repeat['sources'], first['sources'])
        self.assertEqual(repeat['answer'], first['answer'])
        self.assertEqual(self.provider.generate.call_count, 1)
        self.assertEqual(self.store.search.call_count, 1)

    def test_failed_generation_is_not_cached_or_logged_as_success(self):
        self.provider.generate.side_effect = ModelError('Expected test failure')
        with self.assertRaises(ModelError):
            self.pipeline.query('Что такое Python?')
        self.assertEqual(self.pipeline.cache.count(), 0)
        self.assertFalse(self.pipeline.journal.exists())

    def test_empty_retrieval_skips_generation_and_cache(self):
        self.store.search.return_value = []
        with self.assertRaises(ValueError):
            self.pipeline.query('Что такое Python?')
        self.provider.generate.assert_not_called()
        self.assertEqual(self.pipeline.cache.count(), 0)

    def test_top_k_source_and_corpus_change_require_new_generation(self):
        question = 'Что такое Python?'
        self.pipeline.query(question)
        self.pipeline.set_top_k(7)
        self.assertFalse(self.pipeline.query(question)['from_cache'])
        self.store.search.assert_called_with(question, 7, None)
        self.pipeline.set_source('python.txt')
        self.assertFalse(self.pipeline.query(question)['from_cache'])
        self.store.search.assert_called_with(question, 7, 'python.txt')
        self.store.version = 'v2'
        self.assertFalse(self.pipeline.query(question)['from_cache'])
        self.assertEqual(self.provider.generate.call_count, 4)

    def test_bypass_does_not_read_or_write_cache(self):
        question = 'Что такое Python?'
        for _ in range(2):
            self.assertFalse(self.pipeline.query(question, use_cache=False)['from_cache'])
        self.assertEqual(self.provider.generate.call_count, 2)
        self.assertEqual(self.pipeline.cache.count(), 0)


class ProviderAndConsoleTests(unittest.TestCase):
    def test_empty_or_truncated_model_answer_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = ModelProvider(Config(runtime_dir=Path(tmp)))
            provider.client = Mock()
            try:
                for reason, answer in [('length', 'Часть ответа'), ('stop', None), ('stop', ' ' )]:
                    with self.subTest(reason=reason, answer=answer):
                        provider.client.chat.completions.create.return_value = SimpleNamespace(
                            choices=[SimpleNamespace(finish_reason=reason, message=SimpleNamespace(content=answer))])
                        with self.assertRaises(ModelError):
                            provider.generate('System', 'Question')
            finally:
                provider.close()

    def test_eof_exits_once_and_closes_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(runtime_dir=Path(tmp))
            pipeline = Mock()
            pipeline.stats.return_value = {'documents': 1, 'chunks': 1}
            with patch('app.load_config', return_value=config), \
                 patch('app.RAGPipeline', return_value=pipeline), \
                 patch('builtins.input', side_effect=EOFError) as input_mock, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(app.main(), 0)
            self.assertEqual(input_mock.call_count, 1)
            pipeline.close.assert_called_once()
            pipeline.query.assert_not_called()


if __name__ == '__main__':
    unittest.main()

"""SQLite cache preserving full source records, scope and expiry."""
from pathlib import Path
import hashlib, json, sqlite3, time
from contextlib import contextmanager

class RAGCache:
    def __init__(self, db_path, ttl=86400):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS answers (key TEXT PRIMARY KEY, payload TEXT NOT NULL, created REAL NOT NULL)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute('PRAGMA busy_timeout=10000')
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def key(question, scope):
        # Preserve case/punctuation: different code snippets must not share an answer.
        payload = json.dumps([question.strip(), scope], ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def get(self, question, scope):
        key = self.key(question, scope)
        with self.connect() as db:
            row = db.execute('SELECT payload,created FROM answers WHERE key=?',(key,)).fetchone()
            if row is None:
                return None
            if time.time()-row[1] >= self.ttl:
                db.execute('DELETE FROM answers WHERE key=?',(key,))
                return None
        obj = json.loads(row[0])
        if not isinstance(obj, dict) or not obj.get('answer') or not isinstance(obj.get('sources'),list):
            raise ValueError('Повреждённая запись кэша; используйте /clear_cache')
        return obj

    def set(self, question, scope, result):
        if not isinstance(result.get('answer'),str) or not result['answer'].strip():
            raise ValueError('Пустой ответ не кэшируется')
        payload = json.dumps(result,ensure_ascii=False)
        with self.connect() as db:
            db.execute('INSERT INTO answers VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, created=excluded.created',
                       (self.key(question,scope),payload,time.time()))

    def clear(self):
        with self.connect() as db:
            db.execute('DELETE FROM answers')

    def count(self):
        with self.connect() as db:
            db.execute('DELETE FROM answers WHERE created <= ?', (time.time()-self.ttl,))
            return db.execute('SELECT COUNT(*) FROM answers').fetchone()[0]

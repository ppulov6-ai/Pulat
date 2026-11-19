import http from 'node:http';
import { Readable } from 'node:stream';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import app from '../dist/server/index.js';

const database = new DatabaseSync(process.env.DB_PATH || '/data/portfolio.sqlite');
database.exec('PRAGMA journal_mode=WAL');
database.exec('BEGIN IMMEDIATE');
try {
  if (!database.prepare("SELECT 1 FROM sqlite_master WHERE type='table' AND name='interaction_log'").get()) {
    database.exec(readFileSync(new URL('../drizzle/0000_interactions.sql', import.meta.url), 'utf8'));
  }
  database.exec('COMMIT');
} catch (error) {
  database.exec('ROLLBACK');
  throw error;
}
function statement(sql, args = []) {
  const query = database.prepare(sql);
  return {
    bind: (...values) => statement(sql, values),
    first: () => query.get(...args),
    all: () => ({results: query.all(...args)}),
    run: () => query.run(...args)
  };
}
const DB = {
  prepare: statement,
  batch(queries) {
    database.exec('BEGIN');
    try {
      for (const query of queries) query.run();
      database.exec('COMMIT');
    } catch (error) {
      database.exec('ROLLBACK');
      throw error;
    }
  }
};
const server = http.createServer(async (req, res) => {
  try {
    const scheme = req.headers['x-forwarded-proto'] === 'https' ? 'https' : 'http';
    const url = new URL(scheme + '://' + req.headers.host);
    if (!req.url.startsWith('/') || req.url.startsWith('//')) {
      res.writeHead(400).end();
      return;
    }
    const init = {method: req.method, headers: req.headers};
    if (!['GET', 'HEAD'].includes(req.method)) {
      init.body = Readable.toWeb(req);
      init.duplex = 'half';
    }
    const reply = await app.fetch(new Request(url.origin + req.url, init), {DB,MODEL_URL:process.env.MODEL_URL,CHAT_MODEL:process.env.CHAT_MODEL});
    res.writeHead(reply.status, Object.fromEntries(reply.headers));
    res.end(Buffer.from(await reply.arrayBuffer()));
  } catch (error) {
    console.error('HTTP', error.name);
    res.writeHead(500).end();
  }
});
server.listen(Number(process.env.PORT || 8080), process.env.LISTEN_HOST || '127.0.0.1');
process.on('SIGTERM', () => server.close(() => {database.close();}));

const examples = {
  rag: ['Что такое RAG?', 'RAG (Retrieval-Augmented Generation)'],
  python: ['Кто создал Python?', 'Гвидо ван Россумом'],
  vectors: ['Что такое эмбеддинги?', 'Что такое эмбеддинги?'],
  support: ['Какой телефон службы поддержки проекта?', 'телефон службы поддержки']
};
const headers = {'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'};
function escape(value) {
  return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
}
function layout(content) {
  return '<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/style.css"><title>Журнал помощника | Пулат Сафаров</title><main class="shell cases"><a href="/">Портфолио Пулата Сафарова</a><h1 style="margin-top:1rem">Журнал помощника</h1>'+content+'</main>'+widget+'</html>';
}
function findAnswer(term) {
  for (const [source, paragraphs] of Object.entries(corpus)) {
    const answer = paragraphs.find(text => text.includes(term));
    if (answer) return {response:answer, source, status:'ok'};
  }
  return {response:'В учебных документах ответа нет.', source:'Поиск по базе', status:'no_answer'};
}
async function demo(request, db, path) {
  const cookie = request.headers.get('Cookie') || '';
  const session = cookie.match(/(?:^|;\s*)rag_demo=([a-f0-9-]{36})(?:;|$)/)?.[1] || crypto.randomUUID();
  const cookieHeader = 'rag_demo='+session+'; Path=/logging; Secure; HttpOnly; SameSite=Lax; Max-Age=86400';
  if (request.method === 'POST' && path === '/logging') {
    const origin = request.headers.get('Origin');
    if (origin && origin !== new URL(request.url).origin) return new Response('Другой источник', {status:403});
    const start = Date.now();
    const key = new URL(request.url).searchParams.get('q');
    const valid = Object.hasOwn(examples,key);
    const [query,term] = valid ? examples[key] : ['Некорректный запрос',''];
    const previous = valid && await db.prepare("SELECT response,source,status FROM interaction_log WHERE session=? AND question_key=? AND status='ok' ORDER BY id DESC LIMIT 1").bind(session,key).first();
    const result = previous || (valid ? findAnswer(term) : {source:'Проверка ввода',response:'Выберите учебный вопрос.',status:'rejected'});
    await db.batch([
      db.prepare("DELETE FROM interaction_log WHERE timestamp < datetime('now','-7 days')"),
      db.prepare("INSERT INTO interaction_log(session,question_key,query,response,source,from_cache,response_time_ms,status) VALUES(?,?,?,?,?,?,?,?)").bind(session,valid?key:'invalid',query,result.response,result.source,previous?1:0,Date.now()-start,result.status)
    ]);
    return new Response(null,{status:303,headers:{Location:'/logging','Set-Cookie':cookieHeader,'Cache-Control':'no-store'}});
  }
  if (request.method !== 'GET') return new Response('Метод недоступен',{status:405});
  const fields = ['id','timestamp','query','response','source','from_cache','response_time_ms','status'];
  const rows = (await db.prepare('SELECT '+fields.join(',')+' FROM interaction_log WHERE session=? ORDER BY id DESC LIMIT 100').bind(session).all()).results;
  if (path === '/logging/logs.csv') {
    const csv = [fields,...rows.map(row=>fields.map(f=>row[f]))].map(row=>row.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\r\n');
    return new Response('\ufeff'+csv,{headers:{'Content-Type':'text/csv; charset=utf-8','Content-Disposition':'attachment; filename="logs.csv"','Cache-Control':'no-store'}});
  }
  const stats = await db.prepare('SELECT count(*) AS total,coalesce(sum(from_cache),0) AS cached FROM interaction_log WHERE session=?').bind(session).first();
  const buttons = Object.entries(examples).map(([key,[question]])=>'<button class="button" style="white-space:normal;text-align:left" formaction="/logging?q='+key+'">'+escape(question)+'</button>').join('');
  const history = rows.map(row=>'<article><p class="kind">Запись №'+row.id+' · '+escape(row.timestamp)+' UTC</p><h3>'+escape(row.query)+'</h3><p>'+escape(row.response)+'</p><p>'+escape(row.source)+' · '+(row.from_cache?'Из кэша':'Без кэша')+' · '+row.response_time_ms+' мс · '+escape(row.status)+'</p></article>').join('');
  return new Response(layout('<p class="intro">Выберите вопрос дважды. Веб-версия находит фрагмент в учебных документах проекта 5.7. При повторе сервер читает сохранённый ответ. Qwen используется в полной версии проекта на Python.</p><form method="post" class="actions">'+buttons+'</form><h2 style="margin-top:2rem">Ваши запросы</h2><p>Всего: '+stats.total+' · Из кэша: '+stats.cached+' · <a href="/logging/logs.csv">Скачать CSV</a></p>'+history),{headers:{...headers,'Set-Cookie':cookieHeader}});
}
export default {async fetch(request,env) {
  const path=new URL(request.url).pathname;
  if(path==='/chat')return faqRequest(request);
  if(path==='/health' && request.method==='GET')return Response.json({status:'ok',faq:faq.length,topics:topics.length,model:'dialogue-v3-edge'});
  if(path==='/chat.js' && request.method==='GET')return new Response(widgetCode,{headers:{'Content-Type':'text/javascript; charset=utf-8'}});
  if (path==='/' && request.method==='GET') return new Response(home,{headers});
  if (path==='/style.css') return new Response(css,{headers:{'Content-Type':'text/css; charset=utf-8'}});
  if (path==='/logging' || path==='/logging/logs.csv') {
    try {return await demo(request,env.DB,path);} catch(error) {console.error('logging demo', error.name,error.message);return new Response('Журнал временно недоступен',{status:503});}
  }
  return new Response('Страница не найдена',{status:404});
}};

import assert from 'node:assert/strict';
import fs from 'node:fs';
const source=fs.readFileSync('dist/server/index.js','utf8');
const {default:app}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
async function post(body){return app.fetch(new Request('https://example.com/chat',{
  method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)
}));}
const cases=[
 ['Привет!','intro'],['Что сделали в Нефтебазе?','neft'],['Какие есть кейсы?','work'],
 ['Что вы исправляли в документации Yandex Cloud?','yandex'],
 ['Как с вами связаться?','contact'],['Сколько стоит Telegram-бот для заявок?','price_bot'],
 ['Во сколько обойдётся внедрение Битрикс24?','price_crm'],['Оцените ассистента по базе знаний','price_rag'],
 ['Цена CRM-бота в Telegram с ролями и отчётами?','price_crmbot'],['Сколько стоит?','budget'],
 ['Сколько стоит?','price_bot','facade'],['Битрикс24','price_crm','budget'],['Передать пароль?','secret'],
 ['Гарантируете рост продаж?','guarantee'],['фотосинтез у мхов','fallback'],
 ['Хотим попробовать на небольшом примере.','demo'],['После обновления всё сломалось.','bug'],
 ['Данные конфиденциальны. Как показать пример?','nda'],['Мы поменяли требования после согласования.','change']
];
for(const [message,expected,previous] of cases){
  const res=await post({message,previous});assert.equal(res.status,200);const data=await res.json();
  assert.equal(data.topic,expected,message);
  if(data.link)assert.match(data.link.url,/^\/(?:#|logging)/);
  if(expected.startsWith('price_')){assert.match(data.answer,/₽.*готовы обсудить/i);assert.equal(data.link,null);}
}
for(const invalid of [{message:' '},{message:'я'.repeat(1201)},{message:'тест',top_k:99},null]){
  assert.equal((await post(invalid)).status,400);
}
for(const page of ['/','/health','/chat.js']){
 const response=await app.fetch(new Request('https://example.com'+page));assert.equal(response.status,200);
}
console.log('19 диалоговых сценариев, 4 ошибки ввода и 3 маршрута прошли проверку.');

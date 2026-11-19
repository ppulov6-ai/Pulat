const normalize = t => t.toLowerCase().replaceAll('ё','е');
function grams(text) {
  const set=new Set();
  for(const w of normalize(text).match(/[а-яa-z0-9]+/g)||[]){
    set.add(w);set.add('^'+w.slice(0,5));
    for(let i=0;i<w.length-2;i++)set.add(w.slice(i,i+3));
  }
  return set;
}
function similarity(a,b){
  let count=0;
  for(const x of a)if(b.has(x))count++;
  return count/Math.sqrt(a.size*b.size||1);
}
const indexedFAQ=faq.map(f=>({...f,keys:[f.question,...f.aliases].map(grams)}));
const byId=Object.fromEntries(topics.map(t=>[t.id,t]));
const wordIndex=new Map(edge.vocab.map((g,i)=>[g,i]));
const trainingKeys=topics.flatMap(t=>t.questions.map(grams));
function embedKeys(keys){
  const v=new Float64Array(edge.vectors[0].length);
  for(const key of keys){
    const i=wordIndex.get(key);
    if(i===undefined)continue;
    edge.projection[i].forEach((p,j)=>v[j]+=p*edge.idf[i]);
  }
  const norm=Math.hypot(...v)||1;
  return v.map(x=>x/norm);
}
function dialogue(keys){
  const v=embedKeys(keys);
  let best={id:null,score:0,lexical:0};
  for(let i=0;i<edge.labels.length;i++){
    const lexical=similarity(keys,trainingKeys[i]);
    const semantic=edge.vectors[i].reduce((s,x,j)=>s+x*v[j],0);
    const score=.65*semantic+.35*lexical;
    if(score>best.score)best={id:edge.labels[i],score,lexical};
  }
  return best;
}
const fallback='В базе нет точного ответа на этот вопрос. Можно описать задачу Пулату напрямую.';
const faqVectors=indexedFAQ.map(f=>f.keys.map(embedKeys));
const contactLink={url:'/#contact',label:'Связаться с Пулатом'};
function reply(id,answer,link,context=[]){
  return {topic:id,answer,link:link||contactLink,context};
}
function priceKind(s){
  if(/(?:crm|срм|црм).*(бот|телеграм|telegram)|(бот|телеграм|telegram).*(crm|срм|црм)/u.test(s))return 'price_crmbot';
  if(/битрикс|bitrix/.test(s))return 'price_crm';
  if(/rag|раг|баз[а-я]* знани|по документ|внутренн.{0,18}инструкц/.test(s))return 'price_rag';
  if(/бот|телеграм|telegram/.test(s))return 'price_bot';
}
function answerFAQ(message,previous='',lastUser='',topK=3){
  const s=normalize(message);
  const keys=grams(s);
  const v=embedKeys(keys);
  const ranked=indexedFAQ.map((f,i)=>({f,score:Math.max(...f.keys.map((k,j)=>
    .8*similarity(k,keys)+.2*faqVectors[i][j].reduce((sum,x,n)=>sum+x*v[n],0)))})).sort((a,b)=>b.score-a.score);
  const ctx=ranked.slice(0,topK).filter(x=>x.score>=.28).map(x=>({question:x.f.question,answer:x.f.answer}));
  if(/^(привет|здравствуйте|добрый (день|вечер)|доброе утро)[!. ]*$/.test(s))return reply('intro',byId.intro.answer);
  if(/кейсы|кейсов|примеры (работ|проектов)/.test(s) && !/нефтебаз|яндекс|фасад/.test(s)){
    const f=faq.find(x=>x.id==='work');return reply(f.id,f.answer,{url:f.link,label:f.label});
  }
  if(/парол|токен|секретный ключ/.test(s))return reply('secret',byId.secret.answer);
  if(/цен[ауые]|стоимост|сколько.{0,18}(стоит|возьм|денег)|поч[её]м|прайс|бюджет|обойд[её]т|расцен|оцените|во сколько|дорого|дешевле|скидк|торг/.test(s)){
    const known={grp:'price_rag',repair:'price_bot',facade:'price_bot',faq:'price_bot',crm_known:'price_crm'};
    const kind=priceKind(s)||((s.split(/\s+/).length<=9)?prices[previous]&&previous||known[previous]||priceKind(lastUser):null);
    if(kind)return reply(kind,byId[kind].answer,{url:prices[kind].url,label:'Посмотреть сопоставимый заказ'});
    return reply('budget','Готовы обсудить бюджет. Что нужно оценить: бот для заявок, интеграцию с CRM или помощника по документам?');
  }
  if(previous==='budget' && priceKind(s)){
    const kind=priceKind(s);return reply(kind,byId[kind].answer,{url:prices[kind].url,label:'Посмотреть сопоставимый заказ'});
  }
  if(/гарант|обеща.{0,16}(прибыл|выручк|рост)/.test(s))return reply('guarantee',byId.guarantee.answer);
  if(/нефтебаз|yandex cloud|яндекс.{0,15}(ссылк|ошибк|докум)|фасад.?про|фасад pro|логирован|ругпт|дообуч|стил[ьяе] модел|контакт|связаться|позвонить|номер телефона/.test(s)){
    const id=/нефтебаз/.test(s)?'neft':/яндекс|yandex/.test(s)?'yandex':/фасад/.test(s)?'facade':/логирован/.test(s)?'journal':/контакт|связаться|позвонить|номер телефона/.test(s)?'contact':'style';
    const f=faq.find(x=>x.id===id);return reply(id,f.answer,{url:f.link,label:f.label},[{question:f.question,answer:f.answer}]);
  }
  if(/(?:битрикс|bitrix)/.test(s))return reply('crm_known',byId.crm_known.answer,{url:'/#crm',label:'Пример интеграции'});
  if(ranked[0].score>.52){
    const f=ranked[0].f;return reply(f.id,f.answer,{url:f.link,label:f.label},ctx);
  }
  const match=dialogue(keys);
  if(match.score>.49 && match.lexical>.18 && !prices[match.id]){
    const t=byId[match.id];
    if(previous!==t.id)return reply(t.id,t.answer,t.id==='portfolio'?{url:'/#cases',label:'Кейсы Пулата'}:null);
  }
  if(previous && !['fallback','unknown','intro','thanks'].includes(previous))
    return reply('handover','Понял. Для точной оценки понадобится разобрать детали. Отправьте Пулату описание задачи и пример результата.');
  return reply('fallback',fallback);
}
let generating=false;
async function faqRequest(request, modelUrl){
  const json=(body,status=200)=>Response.json(body,{status,headers:{'Cache-Control':'no-store'}});
  if(request.method!=='POST')return json({error:'Требуется POST'},405);
  if(!request.headers.get('content-type')?.includes('application/json'))return json({error:'Нужен JSON'},415);
  const reader=request.body?.getReader();if(!reader)return json({error:'Пустой запрос'},400);
  const chunks=[];let size=0;
  while(true){const {value,done}=await reader.read();if(done)break;size+=value.length;
    if(size>36000){await reader.cancel();return json({error:'Слишком большой запрос'},413);}chunks.push(value);}
  let data;try{const bytes=new Uint8Array(size);let offset=0;for(const c of chunks){bytes.set(c,offset);offset+=c.length;}data=JSON.parse(new TextDecoder().decode(bytes));}catch{return json({error:'Некорректный JSON'},400);}
  if(typeof data?.message!=='string'||!data.message.trim()||data.message.length>1200)return json({error:'Введите от 1 до 1200 символов'},400);
  const top=data.top_k??3;if(!Number.isInteger(top)||top<1||top>5)return json({error:'top_k от 1 до 5'},400);
  if(modelUrl){
    if(generating)return json({error:'Помощник занят. Повторите через минуту.'},429);
    const history=data.history??[];
    if(!Array.isArray(history)||history.length>3||history.some(pair=>!Array.isArray(pair)||pair.length!==2||pair.some(x=>typeof x!=='string'||x.length>2400)))return json({error:'Некорректная история'},400);
    const matched=answerFAQ(data.message.trim(),'',history.at(-1)?.[0]||'',top);
    const price=Object.hasOwn(prices,matched.topic);
    const fact=faq.find(f=>f.id===matched.topic);
    const facts=price?matched.answer:(fact?.answer||'');
    generating=true;
    try{
      const upstream=await fetch(modelUrl,{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({message:data.message,history,facts}),signal:AbortSignal.timeout(60000)});
      if(!upstream.ok)throw Error();
      const result=await upstream.json();
      if(typeof result.answer!=='string'||!result.answer.trim())throw Error();
      let answer=result.answer.trim();
      if(price){
        const question=answer.match(/[^.!?\n]+\?/g)?.at(-1)?.trim();
        const commercial=matched.answer.split(/(?<=[.!])\s+/).slice(0,2).join(' ');
        answer=commercial+' '+(question&&!/\d/.test(question)?question:matched.answer.slice(commercial.length).trim());
      }
      return json({answer,topic:matched.topic,model:'rugpt-lora-v3',link:fact||price?matched.link:contactLink});
    }catch{return json({error:'Модель временно недоступна'},503);}
    finally{generating=false;}
  }
  return json(answerFAQ(data.message.trim(),typeof data.previous==='string'?data.previous.slice(0,40):'',typeof data.lastUser==='string'?data.lastUser.slice(0,1200):'',top));
}

(() => {
  const get=id=>document.getElementById(id);
  const dialog=get('chat-widget'),launcher=get('chat-launcher'),input=get('chat-input');
  const messages=get('chat-messages'),send=get('chat-send');
  let previous='',lastUser='';
  const history=[];
  function open(){
    if(!dialog.open)dialog.showModal();
    launcher.setAttribute('aria-expanded','true');
    input.focus();
  }
  launcher.addEventListener('click',open);
  document.querySelectorAll('[data-chat-open]').forEach(b=>b.addEventListener('click',open));
  if(location.hash==='#chat')open();
  get('chat-close').onclick=()=>dialog.close();
  dialog.addEventListener('close',()=>{launcher.setAttribute('aria-expanded','false');launcher.focus();});
  dialog.addEventListener('click',event=>{
    if(event.target.closest('a') && event.target.closest('a').getAttribute('href').startsWith('/#'))dialog.close();
  });
  function appendMessage(text,from){
    const p=document.createElement('p');
    p.className='bubble '+from;p.textContent=text;
    messages.append(p);messages.scrollTop=messages.scrollHeight;return p;
  }
  async function sendMessage(text){
    if(!text||send.disabled)return;
    appendMessage(text,'user');input.value='';send.disabled=true;
    const pending=appendMessage('Подбираю ответ…','bot');
    try{
      const result=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({message:text,previous,lastUser,history,top_k:3}),signal:AbortSignal.timeout(95000)});
      if(!result.ok)throw new Error();
      const data=await result.json();
      history.push([text,data.answer]);
      if(history.length>3)history.shift();
      previous=data.topic;lastUser=text;pending.textContent=data.answer;
      if(data.link){
        const a=document.createElement('a');a.href=data.link.url;a.textContent=data.link.label;
        pending.append(document.createElement('br'),a);
      }
    }catch{
      pending.textContent='Ответ не пришёл. Попробуйте ещё раз или напишите Пулату напрямую.';
      input.value=text;
    }finally{send.disabled=false;messages.scrollTop=messages.scrollHeight;if(dialog.open)input.focus();}
  }
  get('chat-form').onsubmit=event=>{event.preventDefault();sendMessage(input.value.trim());};
  document.querySelectorAll('.chat-examples button').forEach(b=>b.onclick=()=>sendMessage(b.textContent));
})();

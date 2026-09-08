const $ = s => document.querySelector(s);
let state = {conversations: [], knowledge: [], settings: {}, stats: {}}, current = null, busy = false, memoryTab = 'all', retry = null;
const labels = {asserted:'Informado por você',deduced:'Dedução condicional',hypothesis:'Hipótese',disputed:'Em conflito',retracted:'Retirado'};
const methods = {deduction:'Dedução',opposition:'Oposição',analogy:'Analogia',composition:'Composição'};
function el(tag, cls, text) { const n = document.createElement(tag); if(cls)n.className=cls; if(text!==undefined)n.textContent=text; return n; }
async function api(path, data) {
  const options = data===undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json','X-Workspace-Token':state.token},body:JSON.stringify(data)};
  const response=await fetch(path,options), result=await response.json();
  if(!response.ok)throw new Error(result.error||'Não foi possível concluir a operação.'); return result;
}
async function streamReply(data, onToken) {
  const response=await fetch('/api/chat/stream',{method:'POST',headers:{'Content-Type':'application/json','X-Workspace-Token':state.token},body:JSON.stringify(data)});
  if(!response.ok)throw new Error((await response.json()).error||'Falha ao enviar a mensagem.');
  const reader=response.body.getReader(), decoder=new TextDecoder(); let buffer='', result=null;
  function consume(line) {
    if(!line.trim())return;
    const event=JSON.parse(line);
    if(event.type==='delta')onToken(event.content);
    else if(event.type==='done')result=event.result;
    else if(event.type==='error')throw new Error(event.error);
  }
  try {
    while(true) {
      const chunk=await reader.read();
      buffer+=decoder.decode(chunk.value||new Uint8Array(),{stream:!chunk.done});
      let newline;
      while((newline=buffer.indexOf('\n'))!==-1){consume(buffer.slice(0,newline));buffer=buffer.slice(newline+1);}
      if(chunk.done)break;
    }
    if(buffer.trim())consume(buffer);
    if(!result)throw new Error('A conexão foi interrompida. Tente enviar novamente.');
    return result;
  } finally {reader.releaseLock();}
}
function error(message='') { $('#error').textContent=message; $('#error').hidden=!message; }
async function refresh() {
  state=await api('/api/state'); renderNavigation(); renderKnowledge();
  $('#provider-badge').textContent={symbolic:'Modo técnico',ollama:'Modelo local',openai:'OpenAI'}[state.settings.provider];
  $('#composer-mode').textContent=state.settings.provider==='symbolic'?'Conversa livre desativada · configure um modelo':state.settings.model+' · contexto da conversa ativo';
}
function renderNavigation() {
  const nav=$('#conversations'); nav.replaceChildren();
  for(const c of state.conversations) {
    const b=el('button','conversation'+(current===c.id?' active':''),c.title); b.disabled=busy; b.title=c.title;
    b.addEventListener('click',()=>selectConversation(c.id).catch(e=>error(e.message))); nav.append(b);
  } $('#new-chat').disabled=busy;
}
async function selectConversation(id) {
  if(busy)return; const r=await api('/api/conversations/'+id); current=id; localStorage.setItem('ra.conversation',id);
  $('#conversation-title').textContent=r.conversation.title; renderNavigation(); renderMessages(r.messages); error(); toggleNav(false);
}
async function newConversation() {
  if(busy)return; const r=await api('/api/conversations',{}); await refresh(); await selectConversation(r.id); $('#message-input').focus();
}
function richText(node,text) {
  // Render text and local citations only. User/model HTML is never interpreted.
  for(const part of text.split(/(\[M\d+\]|\*\*[^*\n]+\*\*|`[^`\n]+`)/g)) {
    const match=part.match(/^\[M(\d+)\]$/);
    if(match) { const b=el('button','citation',part); b.addEventListener('click',()=>focusClaim(Number(match[1]))); node.append(b); }
    else if(part.startsWith('**')&&part.endsWith('**'))node.append(el('strong','',part.slice(2,-2)));
    else if(part.startsWith('`')&&part.endsWith('`'))node.append(el('code','inline-code',part.slice(1,-1)));
    else node.append(document.createTextNode(part));
  }
}
function responseText(node,text) {
  const blocks=text.split(/(```[\s\S]*?```)/g);
  for(const block of blocks) {
    if(block.startsWith('```')&&block.endsWith('```')) {
      const newline=block.indexOf('\n'), code=block.slice(newline===-1?3:newline+1,-3);
      const pre=el('pre','code-block');pre.append(el('code','',code));node.append(pre);
    } else richText(node,block);
  }
}
function renderMessage(m) {
  const item=el('article','message '+m.role), head=el('div','message-head');
  head.append(el('span','avatar',m.role==='user'?'EU':'r·a'),el('strong','',m.role==='user'?'Você':'Raciocínio Artificial'));
  if(m.created_at)head.append(el('span','',new Date(m.created_at).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})));
  const content=el('div','message-content'); if(m.role==='assistant')responseText(content,m.content);else content.textContent=m.content; item.append(head,content);
  const meta=m.metadata||{};
  if(m.role==='assistant') {
    const badges=el('div','message-meta');
    if(meta.learned?.length)badges.append(el('span','pill',meta.learned.length+' conhecimento(s) registrado(s)'));
    if(meta.inferences?.length)badges.append(el('span','pill',meta.inferences.length+' conexão(ões) explorada(s)'));
    if(meta.invalidated?.length)badges.append(el('span','pill warning',meta.invalidated.length+' revisão(ões)'));
    badges.append(el('span','pill',meta.provider==='symbolic'?'Motor simbólico':meta.model||'Modelo neural'));
    for(const w of meta.warnings||[])badges.append(el('span','pill warning',w));
    item.append(badges);
    if(meta.inferences?.length) {
      const details=el('details','evidence'); details.append(el('summary','','Ver premissas e formas de validação'));
      for(const original of meta.inferences) {
        const c=state.knowledge.find(c=>c.id===original.id), evidence=el('div','evidence-item');
        evidence.append(el('strong','',(c?labels[c.status]:'Conclusão retirada após revisão')+' · M'+original.id),el('p','',original.explanation));
        const refs=el('p',''); richText(refs,'Premissas: '+original.premises.map(id=>'[M'+id+']').join(' '));
        evidence.append(refs,el('p','','Verificação: '+original.validation)); details.append(evidence);
      } item.append(details);
    }
  } return item;
}
function renderMessages(messages) { $('#welcome').hidden=messages.length>0; $('#messages').replaceChildren(...messages.map(renderMessage)); scrollBottom(); }
function scrollBottom() { requestAnimationFrame(()=>{$('#chat-scroll').scrollTop=$('#chat-scroll').scrollHeight;}); }
function renderKnowledge() {
  $('#stat-assertions').textContent=state.stats.assertions||0; $('#stat-hypotheses').textContent=state.stats.hypotheses||0; $('#stat-messages').textContent=state.stats.messages||0;
  const query=$('#knowledge-search').value.toLocaleLowerCase('pt-BR');
  const claims=state.knowledge.filter(c=>(memoryTab!=='hypotheses'||c.status==='hypothesis')&&(c.text.toLocaleLowerCase('pt-BR').includes(query)||('m'+c.id)===query));
  const list=$('#knowledge-list'); list.replaceChildren();
  if(!claims.length) {
    const empty=el('div','empty-memory'); empty.append(el('div','empty-icon','⌘'),el('strong','',query?'Nenhuma conexão encontrada':memoryTab==='hypotheses'?'Espaço para novas possibilidades':'Tudo começa com uma ideia'));
    empty.append(el('p','',query?'Tente outro termo da sua memória.':'Os conhecimentos e relações das nossas conversas aparecerão aqui, com sua origem e espaço para revisão.')); list.append(empty);
  }
  for(const c of claims) {
    const card=el('article','knowledge-card'); card.id='claim-'+c.id;
    const top=el('div','claim-top'); top.append(el('span','claim-badge '+c.status,labels[c.status]),el('span','','M'+c.id));
    card.append(top,el('div','claim-body',c.text)); const detail=el('details','claim-detail'); detail.append(el('summary','','Origem e relações'));
    for(const source of c.sources) {
      detail.append(el('p','','Mensagem '+source.message_id+': “'+source.quote+'”'));
      const b=el('button','retract','Abrir conversa de origem ↗'); b.disabled=busy;
      b.addEventListener('click',()=>selectConversation(source.conversation_id).catch(e=>error(e.message))); detail.append(b);
    }
    if(c.premises.length) { const refs=el('p',''); richText(refs,(methods[c.method]||'Inferência')+': '+c.premises.map(id=>'[M'+id+']').join(' ')); detail.append(refs,el('p','',c.explanation)); }
    const retract=el('button','retract','Retirar este conhecimento'); retract.disabled=busy;
    retract.addEventListener('click',async()=>{
      try { await api('/api/claims/'+c.id+'/retract',{}); await refresh(); if(current)await selectConversation(current); $('#learning-status').textContent='Conhecimento retirado; conclusões dependentes foram revisadas.'; }
      catch(e){error(e.message);}
    }); detail.append(retract); card.append(detail); list.append(card);
  }
}
function focusClaim(id) {
  memoryTab='all'; setTab(); $('#knowledge-search').value=''; document.body.classList.add('show-memory'); renderKnowledge();
  const card=document.getElementById('claim-'+id);
  if(card){card.querySelector('details').open=true;card.classList.add('highlight');card.scrollIntoView({block:'nearest'});setTimeout(()=>card.classList.remove('highlight'),2200);}
  else error('Essa referência pertence a um conhecimento retirado. O histórico preserva a resposta original.');
}
function setTab() { for(const [id,tab] of [['tab-all','all'],['tab-hypotheses','hypotheses']]){$('#'+id).classList.toggle('active',memoryTab===tab);$('#'+id).setAttribute('aria-selected',String(memoryTab===tab));} }
async function submit(event) {
  event.preventDefault(); if(busy)return; const message=$('#message-input').value.trim();if(!message)return;error();
  try {
    if(!current){const c=await api('/api/conversations',{});current=c.id;localStorage.setItem('ra.conversation',current);}
    busy=true;$('#send').disabled=true;$('#message-input').disabled=true;renderNavigation();renderKnowledge();
    const before=await api('/api/conversations/'+current);renderMessages([...before.messages,{role:'user',content:message}]);$('#welcome').hidden=true;
    const thinking=el('div','thinking','Preparando a resposta');$('#messages').append(thinking);$('#learning-status').textContent='Considerando sua mensagem e o contexto da conversa…';scrollBottom();
    const requestId=retry?.message===message&&retry?.conversation===current?retry.id:crypto.randomUUID();retry={id:requestId,message,conversation:current};
    let live=null, partial='';
    const result=await streamReply({conversation_id:current,message,request_id:requestId},token=>{
      const pane=$('#chat-scroll'), pinned=pane.scrollHeight-pane.scrollTop-pane.clientHeight<100;
      if(!live){thinking.remove();live=renderMessage({role:'assistant',content:'',metadata:{provider:state.settings.provider,model:state.settings.model}});$('#messages').append(live);}
      partial+=token;live.querySelector('.message-content').textContent=partial;
      if(pinned)scrollBottom();
    });$('#message-input').value='';retry=null;
    await refresh();const after=await api('/api/conversations/'+current);$('#conversation-title').textContent=after.conversation.title;renderMessages(after.messages);
    $('#learning-status').textContent=result.learned.length?result.learned.length+' conhecimento(s) integrado(s) à memória':'Interação registrada · novas conexões podem surgir';
  } catch(e) {
    error(e.message);$('#learning-status').textContent='Envio interrompido. Sua mensagem continua no campo para tentar novamente.';
    if(current){try{const persisted=await api('/api/conversations/'+current);renderMessages(persisted.messages);}catch(_){}}
  } finally {busy=false;$('#send').disabled=false;$('#message-input').disabled=false;renderNavigation();renderKnowledge();$('#message-input').focus();}
}
function explainProvider(changed=false) {
  const p=$('#setting-provider').value;$('#neural-settings').hidden=p==='symbolic';
  if(changed)$('#setting-url').value=p==='openai'?'https://api.openai.com/v1':'http://127.0.0.1:11434';
  $('#provider-explanation').textContent=p==='symbolic'?'Funciona sem instalação adicional. Entende afirmações simples em português e executa as regras de raciocínio. Não é um modelo de linguagem geral.':p==='ollama'?'Use um modelo já instalado no Ollama. O provedor precisa estar em execução no endereço indicado. Um endereço local mantém a linguagem neste computador.':'As próximas mensagens, o contexto recente e as memórias relevantes serão enviados à API configurada. Configure OPENAI_API_KEY no ambiente do servidor. A API pode gerar custos. Chave disponível: '+(state.settings.api_key_configured?'sim.':'não.');
}
function toggleNav(open) {
  document.body.classList.toggle('show-nav',open); $('#nav-toggle').setAttribute('aria-expanded',String(open)); $('#nav-backdrop').hidden=!open;
}
$('#nav-toggle').addEventListener('click',()=>toggleNav(!document.body.classList.contains('show-nav')));
$('#nav-backdrop').addEventListener('click',()=>toggleNav(false));
document.addEventListener('keydown',e=>{if(e.key==='Escape'){toggleNav(false);document.body.classList.remove('show-memory');}});
$('#chat-form').addEventListener('submit',submit);
$('#message-input').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('#chat-form').requestSubmit();}});
$('#new-chat').addEventListener('click',()=>newConversation().catch(e=>error(e.message)));
$('#memory-toggle').addEventListener('click',()=>document.body.classList.toggle('show-memory'));
$('#knowledge-search').addEventListener('input',renderKnowledge);
for(const [id,tab] of [['tab-all','all'],['tab-hypotheses','hypotheses']])$('#'+id).addEventListener('click',()=>{memoryTab=tab;setTab();renderKnowledge();});
document.querySelectorAll('[data-example]').forEach(b=>b.addEventListener('click',()=>{$('#message-input').value=b.dataset.example;$('#message-input').focus();}));
$('#settings-open').addEventListener('click',()=>{$('#setting-provider').value=state.settings.provider;$('#setting-model').value=state.settings.model||'';$('#setting-url').value=state.settings.base_url;$('#settings-status').textContent='';explainProvider();$('#settings-dialog').showModal();});
$('#settings-close').addEventListener('click',()=>$('#settings-dialog').close());
$('#setting-provider').addEventListener('change',()=>explainProvider(true));
$('#settings-form').addEventListener('submit',async e=>{
  e.preventDefault();if(busy){$('#settings-status').textContent='Aguarde a resposta atual para alterar o modelo.';return;}
  try {await api('/api/settings',{provider:$('#setting-provider').value,model:$('#setting-model').value.trim(),base_url:$('#setting-url').value.trim(),timeout:state.settings.timeout||120});await refresh();$('#settings-status').textContent='Configuração salva. Será usada nas próximas mensagens.';}
  catch(err){$('#settings-status').textContent=err.message;}
});
$('#test-connection').addEventListener('click',async()=>{
  const b=$('#test-connection');b.disabled=true;$('#settings-status').textContent='Testando o modelo configurado…';
  try {const r=await api('/api/connection',{});$('#settings-status').textContent=r.message;}catch(e){$('#settings-status').textContent=e.message;}finally{b.disabled=false;}
});
document.addEventListener('keydown',e=>{if(e.key.toLowerCase()==='n'&&!e.ctrlKey&&!e.metaKey&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)&&!$('#settings-dialog').open)newConversation().catch(err=>error(err.message));});
(async()=>{try{await refresh();const saved=localStorage.getItem('ra.conversation');if(saved&&state.conversations.some(c=>c.id===saved))await selectConversation(saved);}catch(e){error('Não consegui carregar o laboratório: '+e.message);}})();

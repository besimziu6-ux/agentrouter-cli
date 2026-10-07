"""Single-file vanilla GUI frontend for AgentRouter (no npm, no build, no CDN)."""

from __future__ import annotations

GUI_HTML: str = """<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AgentRouter</title>
<style>
:root{--bg:#fff;--fg:#111827;--mut:#6b7280;--line:#e5e7eb;--card:#f9fafb;--acc:#2563eb;--accfg:#fff;--code:#f3f4f6}
[data-theme="dark"]{--bg:#0f172a;--fg:#e5e7eb;--mut:#94a3b8;--line:#1e293b;--card:#1e293b;--acc:#38bdf8;--accfg:#082f49;--code:#0b1220}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif,"Apple Color Emoji","Segoe UI Emoji";font-size:15px;line-height:1.5}
header{display:flex;gap:.5rem;align-items:center;padding:.6rem 1rem;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg);z-index:5;flex-wrap:wrap}
header h1{font-size:1.05rem;margin:0 .5rem 0 0}
header select,input,textarea{font:inherit;color:var(--fg);background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:.45rem .6rem}
header select{min-width:12rem;max-width:22rem}
button{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:8px;padding:.45rem .8rem;cursor:pointer}
button.pri{background:var(--acc);color:var(--accfg);border-color:transparent}
button:disabled{opacity:.6;cursor:default}
nav{display:flex;gap:.4rem;padding:.5rem 1rem;border-bottom:1px solid var(--line);flex-wrap:wrap}
nav button[aria-selected="true"]{background:var(--acc);color:var(--accfg);border-color:transparent}
main{max-width:960px;margin:0 auto;padding:1rem;display:block}
.panel{display:none}
.panel.on{display:block}
#chatLog,#agentTl{display:flex;flex-direction:column;gap:.5rem;margin:.5rem 0;min-height:40vh}
.msg{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:.55rem .7rem;white-space:pre-wrap;word-break:break-word}
.msg.u{border-left:3px solid var(--acc)}
.msg.a{border-left:3px solid #22c55e}
.msg .r{font-size:.78rem;color:var(--mut)}
.row{display:flex;gap:.5rem}
.row input,.row textarea{flex:1}
.tl{border:1px solid var(--line);border-radius:10px;padding:.5rem .65rem;background:var(--card)}
.tl pre{background:var(--code);border-radius:8px;padding:.5rem;overflow:auto;max-height:16rem;font-size:.82rem}
.swrap{display:grid;grid-template-columns:16rem 1fr;gap:.75rem}
#sesList{list-style:none;margin:0;padding:0;border:1px solid var(--line);border-radius:10px;overflow:auto;max-height:60vh}
#sesList li{padding:.5rem .6rem;border-bottom:1px solid var(--line);cursor:pointer}
#sesList li:hover{background:var(--card)}
#sesView{border:1px solid var(--line);border-radius:10px;padding:.6rem;min-height:20rem;white-space:pre-wrap;word-break:break-word;max-height:60vh;overflow:auto}
.cfg{display:grid;gap:.5rem;max-width:34rem}
.hint{font-size:.82rem;color:var(--mut)}
.err{color:#b91c1c}
@media(max-width:720px){.swrap{grid-template-columns:1fr}header select{min-width:0;flex:1}.row{flex-direction:column}}
</style>
</head>
<body>
<header>
<h1>AgentRouter</h1>
<select id="model" aria-label="Model"></select>
<button id="theme" title="Toggle dark mode">Dark</button>
</header>
<nav role="tablist" aria-label="Views">
<button data-t="chat" aria-selected="true">Chat</button>
<button data-t="agent" aria-selected="false">Agent</button>
<button data-t="sessions" aria-selected="false">Sessions</button>
<button data-t="config" aria-selected="false">Config</button>
</nav>
<main>
<section id="p-chat" class="panel on" role="tabpanel">
<div id="chatLog" aria-live="polite"></div>
<form id="chatF" class="row"><input id="chatIn" placeholder="Ask anything..." autocomplete="off"><button class="pri" type="submit">Send</button></form>
<p class="hint">Streams POST /api/chat via SSE.</p>
</section>
<section id="p-agent" class="panel" role="tabpanel">
<form id="agentF">
<div class="row"><input id="goal" placeholder="Goal for agent..."></div>
<div class="row" style="margin-top:.5rem">
<label>Max steps <input id="steps" type="number" value="10" min="1" max="50" style="width:5rem"></label>
<label><input id="bash" type="checkbox"> allow-bash</label>
<button class="pri" type="submit">Run</button>
</div>
</form>
<div id="agentTl" aria-live="polite"></div>
</section>
<section id="p-sessions" class="panel" role="tabpanel">
<div class="row" style="margin-bottom:.5rem"><button id="sesR">Refresh</button><button id="toChat" disabled>Load to chat</button></div>
<div class="swrap"><ul id="sesList"></ul><div id="sesView">Select a session.</div></div>
</section>
<section id="p-config" class="panel" role="tabpanel">
<form id="cfgF" class="cfg">
<div id="cfgCur" class="hint">Loading...</div>
<label>API key <input id="apiKey" type="password" placeholder="sk-..." autocomplete="off"></label>
<label>Default model <input id="defModel" placeholder="model id"></label>
<label>Base URL <input id="baseUrl" placeholder="https://..."></label>
<div><button class="pri" type="submit">Save</button></div>
<div id="cfgMsg" class="hint"></div>
</form>
</section>
</main>
<script>
"use strict";
var $=function(id){return document.getElementById(id)};
var modelEl=$("model"),chatLog=$("chatLog"),chatF=$("chatF"),chatIn=$("chatIn");
var agentF=$("agentF"),goalEl=$("goal"),stepsEl=$("steps"),bashEl=$("bash"),agentTl=$("agentTl");
var sesList=$("sesList"),sesView=$("sesView"),sesR=$("sesR"),toChat=$("toChat");
var cfgF=$("cfgF"),apiKeyEl=$("apiKey"),defModelEl=$("defModel"),baseUrlEl=$("baseUrl"),cfgMsg=$("cfgMsg"),cfgCur=$("cfgCur");
var hist=[],curSes=null,chatCtl=null,agentCtl=null;
function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
function themeInit(){var t="light";try{t=localStorage.getItem("ar-theme")||"light"}catch(e){}document.documentElement.setAttribute("data-theme",t);$("theme").textContent=t==="dark"?"Light":"Dark"}
$("theme").onclick=function(){var c=document.documentElement.getAttribute("data-theme")==="dark"?"light":"dark";document.documentElement.setAttribute("data-theme",c);try{localStorage.setItem("ar-theme",c)}catch(e){}$("theme").textContent=c==="dark"?"Light":"Dark"};
document.querySelectorAll("nav button").forEach(function(b){b.onclick=function(){document.querySelectorAll("nav button").forEach(function(x){x.setAttribute("aria-selected","false")});b.setAttribute("aria-selected","true");document.querySelectorAll(".panel").forEach(function(p){p.classList.remove("on")});$("p-"+b.dataset.t).classList.add("on")}});
function model(){return modelEl.value||""}
function setModels(ids,def){modelEl.innerHTML="";if(!ids.length){modelEl.innerHTML="<option value=''>no models</option>";return}ids.forEach(function(id){var o=document.createElement("option");o.value=id;o.textContent=id;modelEl.appendChild(o)});var want="";try{want=localStorage.getItem("ar-model")||""}catch(e){}if(def)want=want||def;if(want&&ids.indexOf(want)>=0)modelEl.value=want}
modelEl.onchange=function(){try{localStorage.setItem("ar-model",modelEl.value)}catch(e){}};
function idsFrom(d){var items=[];if(Array.isArray(d))items=d;else if(d&&Array.isArray(d.data))items=d.data;else if(d&&Array.isArray(d.models))items=d.models;var out=[];items.forEach(function(x){if(typeof x==="string"&&x.trim())out.push(x.trim());else if(x&&typeof x.id==="string")out.push(x.id)});return out}
async function loadModels(){modelEl.innerHTML="<option>loading...</option>";try{var r=await fetch("/api/models");var d=await r.json();setModels(idsFrom(d),"")}catch(e){modelEl.innerHTML="<option value=''>models unavailable</option>"}}
async function loadCfg(){try{var r=await fetch("/api/config");var d=await r.json();cfgCur.textContent="base_url: "+(d.base_url||"")+" | api_key: "+(d.api_key||"")+" | default_model: "+(d.default_model||"(not set)");if(d.default_model&&!modelEl.value)setModels(Array.from(modelEl.options).map(function(o){return o.value}),d.default_model);if(d.default_model)defModelEl.placeholder=d.default_model}catch(e){cfgCur.textContent="config unavailable"}}}
function addMsg(role,text){var d=document.createElement("div");d.className="msg "+(role==="user"?"u":"a");d.innerHTML="<div class='r'>"+esc(role)+"</div><div class='b'>"+esc(text)+"</div>";chatLog.appendChild(d);chatLog.scrollTop=chatLog.scrollHeight;return d.querySelector(".b")}
async function ssePost(url,body,ctl,onEv,onErr){var r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body),signal:ctl.signal});if(!r.ok){var t="";try{t=await r.text()}catch(e){}throw new Error(t||("HTTP "+r.status))}var rd=r.body.getReader(),dec=new TextDecoder(),buf="";for(;;){var x=await rd.read();if(x.done)break;buf+=dec.decode(x.value,{stream:true});var parts=buf.split("\\n\\n");buf=parts.pop();parts.forEach(function(p){var line="";p.split("\\n").forEach(function(l){if(l.indexOf("data:")===0)line+=l.slice(5).trim()});if(!line)return;if(line==="[DONE]")return;try{onEv(JSON.parse(line))}catch(e){}})}if(buf.trim()){try{onEv(JSON.parse(buf.replace(/^data:\\s*/,"")))}catch(e){}}}
chatF.onsubmit=function(e){e.preventDefault();var q=chatIn.value.trim();if(!q)return;if(chatCtl)chatCtl.abort();chatCtl=new AbortController();var m=model();if(!m){addMsg("system","Pick a model first.");return}hist.push({role:"user",content:q});addMsg("user",q);chatIn.value="";var body=addMsg("assistant","");var acc="";ssePost("/api/chat",{model:m,messages:hist},chatCtl,function(ev){if(ev&&ev.error){acc+=ev.error;body.textContent=acc;return}var t=ev.content!=null?ev.content:(ev.text||ev.delta||"");if(typeof t==="string"&&t){acc+=t;body.textContent=acc;chatLog.scrollTop=chatLog.scrollHeight}},function(err){body.textContent+="\\n[error: "+err.message+"]"}).then(function(){if(acc)hist.push({role:"assistant",content:acc})}).catch(function(err){if(err&&err.name!=="AbortError")body.textContent+="\\n[error: "+err.message+"]"});};
function tl(html){var d=document.createElement("div");d.className="tl";d.innerHTML=html;agentTl.appendChild(d);return d}
agentF.onsubmit=function(e){e.preventDefault();var g=goalEl.value.trim();if(!g)return;if(agentCtl)agentCtl.abort();agentCtl=new AbortController();var m=model();if(!m){tl("Pick a model first.");return}var ms=parseInt(stepsEl.value,10)||10;tl("<b>Goal:</b> "+esc(g)+" <span class='hint'>model="+esc(m)+" steps="+ms+" bash="+(bashEl.checked?"on":"off")+"</span>");ssePost("/api/agent",{goal:g,model:m,max_steps:ms,allow_bash:bashEl.checked},agentCtl,function(ev){if(!ev)return;if(ev.type==="step"){var d=tl("<b>Step "+esc(ev.step||"")+"</b><pre>"+esc(ev.text||"")+"</pre>")}else if(ev.type==="tool"){tl("<b>Tool "+esc(ev.tool||"")+" (step "+esc(ev.step||"")+")</b><pre>"+esc(JSON.stringify(ev.args||{}))+"\\n--- result ---\\n"+esc(String(ev.result||"")).slice(0,4000)+"</pre>")}else if(ev.type==="done"){tl("<b>Done</b> session="+esc(ev.session_id||"")+"<pre>"+esc(ev.text||"")+"</pre>")}else if(ev.type==="error"){tl("<span class='err'><b>Error:</b> "+esc(ev.error||"unknown")+"</span>")}else if(ev.content){tl("<pre>"+esc(ev.content)+"</pre>")}},function(){}).catch(function(err){if(err&&err.name!=="AbortError")tl("<span class='err'>"+esc(err.message)+"</span>")});};
async function loadSes(){sesList.innerHTML="<li>loading...</li>";try{var r=await fetch("/api/sessions");var d=await r.json();var items=d.sessions||d||[];sesList.innerHTML="";if(!items.length)sesList.innerHTML="<li>(no sessions)</li>";items.forEach(function(s){var id=typeof s==="string"?s:(s.id||JSON.stringify(s));var li=document.createElement("li");li.textContent=id;li.onclick=function(){viewSes(id)};sesList.appendChild(li)})}catch(e){sesList.innerHTML="<li>failed to load</li>"}}
async function viewSes(id){sesView.textContent="loading "+id+"...";toChat.disabled=true;curSes=null;try{var r=await fetch("/api/sessions/"+encodeURIComponent(id));var d=await r.json();if(!r.ok)throw new Error(d.error||("HTTP "+r.status));curSes=d;var msgs=d.messages||[];sesView.innerHTML=msgs.map(function(m){return "<b>"+esc(m.role||"?")+":</b> "+esc(m.content||"")}).join("\\n\\n")||"(empty)";toChat.disabled=false}catch(e){sesView.textContent="error: "+e.message}}
toChat.onclick=function(){if(!curSes)return;hist=(curSes.messages||[]).filter(function(m){return m.role!=="system"});chatLog.innerHTML="";hist.forEach(function(m){addMsg(m.role==="user"?"user":"assistant",m.content||"")});document.querySelector('nav button[data-t="chat"]').click()};
sesR.onclick=loadSes;
cfgF.onsubmit=function(e){e.preventDefault();cfgMsg.textContent="saving...";var p={};if(apiKeyEl.value.trim())p.api_key=apiKeyEl.value.trim();if(defModelEl.value.trim())p.default_model=defModelEl.value.trim();else if(model())p.default_model=model();if(baseUrlEl.value.trim())p.base_url=baseUrlEl.value.trim();if(!Object.keys(p).length){cfgMsg.textContent="Nothing to update.";return}fetch("/api/config",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(p)}).then(function(r){return r.json().then(function(d){return{ok:r.ok,d:d}})}).then(function(x){cfgMsg.textContent=x.ok?("saved. default_model="+(x.d.default_model||"")):("error: "+(x.d.error||"failed"));if(x.ok)loadCfg()}).catch(function(err){cfgMsg.textContent="error: "+err.message})};
themeInit();loadModels().then(loadCfg);loadSes();
</script>
</body>
</html>"""

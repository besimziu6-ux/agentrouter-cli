"""Single-file vanilla GUI frontend for AgentRouter (no npm, no build, no CDN)."""

from __future__ import annotations

GUI_HTML: str = """<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AgentRouter</title>
<style>
:root{--bg:#fff;--fg:#111827;--mut:#6b7280;--line:#e5e7eb;--card:#f6f7f9;--acc:#2563eb;--accfg:#fff;--code:#f3f4f6;--bub:#ececf1;--sb:#f9f9f9}
[data-theme="dark"]{--bg:#0f172a;--fg:#e5e7eb;--mut:#94a3b8;--line:#1e293b;--card:#1e293b;--acc:#38bdf8;--accfg:#082f49;--code:#0b1220;--bub:#2f3b52;--sb:#0b1220}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--fg);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;font-size:15px;line-height:1.5}
button{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:8px;padding:.45rem .8rem;cursor:pointer}
button.pri{background:var(--acc);color:var(--accfg);border-color:transparent}
button:disabled{opacity:.55;cursor:default}
:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
#app{display:flex;min-height:100vh}
#sidebar{width:260px;flex:0 0 260px;background:var(--sb);border-right:1px solid var(--line);display:flex;flex-direction:column;min-height:100vh;position:sticky;top:0;max-height:100vh}
#sidebar .top{padding:.7rem;display:grid;gap:.55rem}
#newChat{width:100%;text-align:left}
#search{width:100%;font:inherit;color:var(--fg);background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:.45rem .6rem}
#sesList{list-style:none;margin:0;padding:0 .7rem;overflow:auto;flex:1;display:flex;flex-direction:column;gap:.25rem}
#sesList li{padding:.5rem .6rem;border:1px solid transparent;border-radius:8px;cursor:pointer;font-size:.9rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#sesList li:hover{background:var(--card)}
#sesList li.act{border-color:var(--line);background:var(--card)}
#sesList li small{display:block;color:var(--mut);font-size:.75rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sideFoot{border-top:1px solid var(--line);padding:.6rem .7rem;display:grid;gap:.4rem;font-size:.82rem;color:var(--mut)}
.sideFoot .frow{display:flex;align-items:center;gap:.45rem;justify-content:space-between}
.dot{width:9px;height:9px;border-radius:50%;background:#9ca3af;display:inline-block;flex:0 0 9px}
.dot.ok{background:#22c55e}.dot.bad{background:#ef4444}.dot.warn{background:#f59e0b}
#scrim{display:none}
main{flex:1;min-width:0;display:flex;flex-direction:column;min-height:100vh}
#bar{display:flex;align-items:center;gap:.6rem;padding:.55rem 1rem;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg);z-index:5}
#bar select{font:inherit;color:var(--fg);background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:.4rem .55rem;max-width:16rem}
.seg{display:flex;border:1px solid var(--line);border-radius:9px;overflow:hidden}
.seg button{border:0;border-radius:0;background:transparent;padding:.4rem .9rem}
.seg button[aria-selected="true"]{background:var(--acc);color:var(--accfg)}
#ham{display:none}
#wrap{max-width:768px;width:100%;margin:0 auto;display:flex;flex-direction:column;flex:1;min-height:0;padding:0 1rem}
#conv{flex:1;overflow:auto;padding:1rem 0 0;display:flex;flex-direction:column;gap:.8rem;min-height:30vh}
.urow{display:flex;justify-content:flex-end}
.ubub{background:var(--bub);border-radius:14px;padding:.5rem .8rem;max-width:85%;white-space:pre-wrap;word-break:break-word}
.arow{display:flex;gap:.6rem;align-items:flex-start}
.av{width:26px;height:26px;border-radius:50%;background:#22c55e;flex:0 0 26px;margin-top:.15rem}
.abody{flex:1;min-width:0}
.abody .md{word-break:break-word}
.abody .md pre{background:var(--code);border:1px solid var(--line);border-radius:8px;padding:.55rem;overflow:auto;font-size:.83rem}
.abody .md code{background:var(--code);border-radius:5px;padding:.1rem .3rem;font-size:.86em}
.abody .md pre code{background:transparent;padding:0}
.cwrap{position:relative}
.clab{display:flex;justify-content:space-between;align-items:center;font-size:.72rem;color:var(--mut);border-bottom:1px solid var(--line);padding-bottom:.25rem;margin-bottom:.35rem}
.clab button{font-size:.72rem;padding:.15rem .5rem}
.tool{border:1px solid var(--line);border-radius:10px;background:var(--card);overflow:hidden}
.tool summary{cursor:pointer;padding:.5rem .7rem;font-size:.88rem;display:flex;gap:.5rem;align-items:center;list-style:none}
.tool summary::-webkit-details-marker{display:none}
.tool .tb{padding:0 .7rem .7rem}
.tool pre{background:var(--code);border-radius:8px;padding:.5rem;overflow:auto;max-height:14rem;font-size:.8rem;white-space:pre-wrap;word-break:break-word}
.spin{width:12px;height:12px;border:2px solid var(--mut);border-top-color:transparent;border-radius:50%;display:inline-block;animation:sp .7s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
.st-ok{color:#16a34a}.st-err{color:#dc2626}
.typing{display:inline-flex;gap:5px;padding:.4rem 0}
.typing i{width:7px;height:7px;border-radius:50%;background:var(--mut);display:inline-block;animation:bl 1s infinite}
.typing i:nth-child(2){animation-delay:.15s}.typing i:nth-child(3){animation-delay:.3s}
@keyframes bl{0%,100%{opacity:.3;transform:translateY(0)}50%{opacity:1;transform:translateY(-4px)}}
#empty{text-align:center;padding:3rem 1rem;display:grid;gap:1rem;justify-items:center}
#empty h2{margin:0;font-size:1.4rem}
.chips{display:flex;gap:.5rem;flex-wrap:wrap;justify-content:center}
.chips button{border-radius:999px}
#dock{position:sticky;bottom:0;background:var(--bg);padding:.7rem 0 1rem}
#agentOpts{display:flex;gap:.6rem;align-items:center;flex-wrap:wrap;font-size:.85rem;color:var(--mut);margin-bottom:.45rem}
#agentOpts input{font:inherit;color:var(--fg);background:var(--bg);border:1px solid var(--line);border-radius:7px;padding:.3rem .5rem}
#composerRow{display:flex;gap:.5rem;align-items:flex-end}
#composer{flex:1;font:inherit;color:var(--fg);background:var(--bg);border:1px solid var(--line);border-radius:12px;padding:.6rem .75rem;resize:none;min-height:44px;max-height:180px;line-height:1.45}
.dbtns{display:flex;gap:.4rem}
.hint{font-size:.78rem;color:var(--mut);margin:.4rem 0 0}
#toasts{position:fixed;top:.8rem;right:.8rem;display:flex;flex-direction:column;gap:.5rem;z-index:60;max-width:min(92vw,360px)}
.toast{background:#111827;color:#f9fafb;border-radius:10px;padding:.6rem .8rem;font-size:.88rem;box-shadow:0 6px 24px rgba(0,0,0,.25)}
[data-theme="light"] .toast{background:#111827;color:#f9fafb}
.toast.err{background:#7f1d1d}
#cfgModal{position:fixed;inset:0;display:none;align-items:center;justify-content:center;background:rgba(0,0,0,.45);z-index:50;padding:1rem}
#cfgModal.on{display:flex}
#cfgBox{background:var(--bg);border:1px solid var(--line);border-radius:14px;max-width:26rem;width:100%;padding:1rem;display:grid;gap:.6rem}
#cfgBox input{font:inherit;color:var(--fg);background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:.45rem .6rem;width:100%}
#cfgBox .hint{margin:0}
#cfgMsg{font-size:.85rem;min-height:1.2em}
#cfgMsg.err{color:#dc2626}#cfgMsg.ok{color:#16a34a}
.krow{display:flex;gap:.5rem}
.krow input{flex:1}
@media(max-width:900px){
#sidebar{position:fixed;left:0;top:0;bottom:0;z-index:40;transform:translateX(-102%);transition:transform .18s ease}
body.nav-open #sidebar{transform:none}
#scrim{display:none;position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:30}
body.nav-open #scrim{display:block}
#ham{display:inline-block}
#bar select{max-width:9rem}
}
</style>
</head>
<body>
<div id="app">
<aside id="sidebar" aria-label="Chat history">
<div class="top">
<button id="newChat" aria-label="New chat">+ New chat</button>
<input id="search" type="search" placeholder="Search chats" aria-label="Search chats" autocomplete="off">
</div>
<ul id="sesList" aria-label="Sessions"></ul>
<div class="sideFoot">
<div class="frow"><span id="modelName" title="Active model">model: -</span><span id="keyDot" class="dot warn" title="API key status"></span></div>
<div class="frow"><span id="ver">v0.1.0</span><span><button id="themeBtn" aria-label="Toggle theme">Theme</button> <button id="cfgBtn" aria-label="Open config">Config</button></span></div>
</div>
</aside>
<div id="scrim" aria-hidden="true"></div>
<main>
<div id="bar">
<button id="ham" aria-label="Open sidebar">&#9776;</button>
<select id="model" aria-label="Model"></select>
<span id="statusDot" class="dot warn" title="Checking connection..." role="status" aria-label="Connection status"></span>
<div class="seg" role="tablist" aria-label="Mode">
<button id="tabChat" role="tab" aria-selected="true">Chat</button>
<button id="tabAgent" role="tab" aria-selected="false">Agent</button>
</div>
</div>
<div id="wrap">
<div id="conv" aria-live="polite" role="log" aria-label="Conversation"></div>
<div id="empty">
<h2>What can I help with?</h2>
<div class="chips">
<button data-s="Explain recursion with a short example">Explain recursion</button>
<button data-s="Use the agent to create hello.txt with hello world inside">Create hello.txt via agent</button>
<button data-s="List the available models">List models</button>
<button data-s="Summarize the README file in this repo">Summarize README</button>
</div>
</div>
<div id="dock">
<div id="agentOpts" hidden>
<label>Max steps <input id="maxSteps" type="number" value="10" min="1" max="50" style="width:4.5rem" aria-label="max-steps"></label>
<label><input id="allowBash" type="checkbox"> allow-bash</label>
<details><summary>System prompt</summary><input id="sysPrompt" placeholder="Optional system prompt" aria-label="System prompt" style="width:100%;margin-top:.4rem"></details>
</div>
<div id="composerRow">
<textarea id="composer" rows="1" placeholder="Message AgentRouter... (Enter send, Shift+Enter newline, Ctrl+K focus)" aria-label="Message composer"></textarea>
<div class="dbtns">
<button id="sendBtn" class="pri" aria-label="Send">Send</button>
<button id="stopBtn" disabled aria-label="Stop">Stop</button>
<button id="clearBtn" aria-label="New or clear">New</button>
</div>
</div>
<p class="hint">Enter sends. Shift+Enter newline. Ctrl+K focuses composer. Agent mode streams step and tool cards.</p>
</div>
</div>
</main>
</div>
<div id="cfgModal" role="dialog" aria-modal="true" aria-label="Config">
<div id="cfgBox">
<h3 style="margin:0">Config</h3>
<div id="cfgCur" class="hint">Loading...</div>
<label>API key<input id="apiKey" type="password" placeholder="sk-..." autocomplete="off"></label>
<div class="krow"><button id="showKey" type="button">Show</button><button id="testBtn" type="button">Test connection</button></div>
<label>Default model<input id="defModel" placeholder="model id" autocomplete="off"></label>
<label>Base URL<input id="baseUrl" placeholder="locked" disabled aria-disabled="true"></label>
<p class="hint">Locked to https://agentrouter.org/v1</p>
<div id="cfgMsg" aria-live="polite"></div>
<div class="krow"><button id="saveCfg" class="pri" type="button">Save</button><button id="closeCfg" type="button">Close</button></div>
</div>
</div>
<div id="toasts" aria-live="polite"></div>
<script>
"use strict";
var $=function(id){return document.getElementById(id)};
var side_list=$("sesList"),searchEl=$("search"),conv=$("conv"),emptyEl=$("empty");
var modelEl=$("model"),modelName=$("modelName"),statusDot=$("statusDot"),keyDot=$("keyDot");
var tabChat=$("tabChat"),tabAgent=$("tabAgent"),agentOpts=$("agentOpts");
var composer=$("composer"),sendBtn=$("sendBtn"),stopBtn=$("stopBtn"),clearBtn=$("clearBtn");
var maxSteps=$("maxSteps"),allowBash=$("allowBash"),sysPrompt=$("sysPrompt");
var cfgModal=$("cfgModal"),apiKeyEl=$("apiKey"),defModelEl=$("defModel"),baseUrlEl=$("baseUrl"),cfgMsg=$("cfgMsg"),cfgCur=$("cfgCur");
var toasts=$("toasts"),mode="chat",hist=[],ctl=null,sesCache=[],curSes=null;
function esc(s){return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}
function toast(m,kind){var d=document.createElement("div");d.className="toast"+(kind==="err"?" err":"");d.textContent=String(m);toasts.appendChild(d);setTimeout(function(){if(d.parentNode)d.parentNode.removeChild(d)},4200)}
function themeInit(){var t=null;try{t=localStorage.getItem("ar-theme")}catch(e){}if(!t){t=(window.matchMedia&&matchMedia("(prefers-color-scheme: dark)").matches)?"dark":"light"}document.documentElement.setAttribute("data-theme",t);$("themeBtn").textContent=t==="dark"?"Light":"Dark"}
$("themeBtn").onclick=function(){var c=document.documentElement.getAttribute("data-theme")==="dark"?"light":"dark";document.documentElement.setAttribute("data-theme",c);try{localStorage.setItem("ar-theme",c)}catch(e){}$("themeBtn").textContent=c==="dark"?"Light":"Dark"};
function setMode(m){mode=m;var a=m==="agent";tabChat.setAttribute("aria-selected",String(!a));tabAgent.setAttribute("aria-selected",String(a));agentOpts.hidden=!a;composer.placeholder=a?"Describe the goal for the agent...":"Message AgentRouter... (Enter send, Shift+Enter newline, Ctrl+K focus)"}
tabChat.onclick=function(){setMode("chat")};tabAgent.onclick=function(){setMode("agent")};
$("ham").onclick=function(){document.body.classList.add("nav-open")};
$("scrim").onclick=function(){document.body.classList.remove("nav-open")};
function curModel(){return modelEl.value||""}
function idsFrom(d){var items=[];if(Array.isArray(d))items=d;else if(d&&Array.isArray(d.data))items=d.data;else if(d&&Array.isArray(d.models))items=d.models;var out=[];items.forEach(function(x){if(typeof x==="string"&&x.trim())out.push(x.trim());else if(x&&typeof x.id==="string")out.push(x.id)});return out}
function setModels(ids,def){modelEl.innerHTML="";if(!ids.length){modelEl.innerHTML="<option value=''>no models</option>";modelName.textContent="model: -";return}ids.forEach(function(id){var o=document.createElement("option");o.value=id;o.textContent=id;modelEl.appendChild(o)});var want="";try{want=localStorage.getItem("ar-model")||""}catch(e){}if(def)want=want||def;if(want&&ids.indexOf(want)>=0)modelEl.value=want;modelName.textContent="model: "+modelEl.value}
modelEl.onchange=function(){try{localStorage.setItem("ar-model",modelEl.value)}catch(e){}modelName.textContent="model: "+modelEl.value};
function setStatus(ok,msg){statusDot.className="dot "+(ok?"ok":"bad");statusDot.title=msg||(ok?"Connected":"Connection failed");statusDot.setAttribute("aria-label",statusDot.title)}
async function boot(){themeInit();setMode("chat");try{var h=await fetch("/api/health");var m=await fetch("/api/models");if(h.ok&&m.ok){var d=await m.json();var ids=idsFrom(d);setModels(ids,"");setStatus(true,"Connected: /api/health and /api/models ok")}else{setStatus(false,"Health or models request failed: "+h.status+" / "+m.status);try{var d2=await m.json();setModels(idsFrom(d2),"")}catch(e){}}}catch(e){setStatus(false,"Connection failed: "+e.message)}loadCfg(true);loadSes()}
function mdLinkEsc(s){return esc(s)}
function inlineFmt(s){s=esc(s);s=s.replace(/\\[([^\\]]+)\\]\\(([^)\\s]+)\\)/g,function(m,t,u){var uu=esc(u);if(uu.slice(0,4)==="java"||uu.indexOf("<")>=0)return esc(t);return '<a href="'+uu+'" rel="noopener">'+esc(t)+"</a>"});s=s.replace(/`([^`\\n]+)`/g,"<code>$1</code>");s=s.replace(/\\*\\*([^*]+)\\*\\*/g,"<strong>$1</strong>");s=s.replace(/(^|\\W)\\*([^\\*\\n]+)\\*/g,"$1<em>$2</em>");return s}
function md(src){var t=String(src==null?"":src);var parts=t.split("```");var out="";for(var i=0;i<parts.length;i++){if(i%2===1){var blk=parts[i];var nl=blk.indexOf("\\n");var lang=(nl>0?blk.slice(0,nl).trim():"").slice(0,20)||"code";var code=nl>0?blk.slice(nl+1):blk;out+='<div class="cwrap"><div class="clab"><span>'+esc(lang)+'</span><button data-copy="'+esc(code).replace(/"/g,"&quot;")+'">Copy</button></div><pre><code>'+esc(code).replace(/^\\n+/,"")+"</code></pre></div>"}else{var seg=parts[i];var lines=seg.split("\\n");var html="",inList=false;lines.forEach(function(ln){var h=ln.match(/^(#{1,4})\\s+(.*)/);if(h){if(inList){html+="</ul>";inList=false}html+="<h"+h[1].length+">"+inlineFmt(h[2])+"</h"+h[1].length+">";return}var li=ln.match(/^\\s*[-*]\\s+(.*)/);if(li){if(!inList){html+="<ul>";inList=true}html+="<li>"+inlineFmt(li[1])+"</li>";return}if(!ln.trim()){if(inList){html+="</ul>";inList=false}html+="<br>";return}if(inList){html+="</ul>";inList=false}html+="<p style='margin:.3rem 0'>"+inlineFmt(ln)+"</p>"});if(inList)html+="</ul>";out+= '<div class="md">'+html+"</div>"}}return out}
conv.addEventListener("click",function(e){var b=e.target&&e.target.closest?e.target.closest("[data-copy]"):null;if(!b)return;var v=b.getAttribute("data-copy")||"";function done(){b.textContent="Copied";setTimeout(function(){b.textContent="Copy"},1200)}if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(v).then(done,function(){toast("Copy failed","err")})}else{var ta=document.createElement("textarea");ta.value=v;document.body.appendChild(ta);ta.select();try{document.execCommand("copy");done()}catch(err){toast("Copy failed","err")}ta.remove()}});
function hideEmpty(){emptyEl.style.display="none"}
function addUser(t){hideEmpty();var r=document.createElement("div");r.className="urow";var b=document.createElement("div");b.className="ubub";b.textContent=t;r.appendChild(b);conv.appendChild(r);conv.scrollTop=conv.scrollHeight}
function addAsst(){hideEmpty();var r=document.createElement("div");r.className="arow";var a=document.createElement("div");a.className="av";a.setAttribute("aria-hidden","true");var bd=document.createElement("div");bd.className="abody";r.appendChild(a);r.appendChild(bd);conv.appendChild(r);conv.scrollTop=conv.scrollHeight;return bd}
function typingEl(host){var d=document.createElement("div");d.className="typing";d.innerHTML="<i></i><i></i><i></i>";host.appendChild(d);return d}
function toolCard(title,open){var d=document.createElement("details");d.className="tool";if(open!==false)d.open=true;var s=document.createElement("summary");s.innerHTML='<span class="spin"></span><span>'+title+"</span>";d.appendChild(s);var b=document.createElement("div");b.className="tb";d.appendChild(b);conv.appendChild(d);conv.scrollTop=conv.scrollHeight;return{el:d,sum:s,body:b,done:function(st){var sp=s.querySelector(".spin");if(sp)sp.remove();var tag=document.createElement("span");tag.className=st==="error"?"st-err":"st-ok";tag.textContent=st==="error"?"error":"done";s.appendChild(tag)}}}
function preBox(label,text){var p=document.createElement("pre");p.textContent=(label?label+"\\n":"")+String(text==null?"":text).slice(0,4000);return p}
async function ssePost(url,body,onEv){var r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body),signal:ctl?ctl.signal:undefined});if(!r.ok){var t="";try{t=await r.text()}catch(e){}throw new Error(t||("HTTP "+r.status))}var rd=r.body.getReader(),dec=new TextDecoder(),buf="";for(;;){var x=await rd.read();if(x.done)break;buf+=dec.decode(x.value,{stream:true});var parts=buf.split("\\n\\n");buf=parts.pop();for(var i=0;i<parts.length;i++){var line="";parts[i].split("\\n").forEach(function(l){if(l.indexOf("data:")===0)line+=(line?"":"")+l.slice(5).trim()});if(!line)continue;if(line==="[DONE]")continue;try{onEv(JSON.parse(line))}catch(e){}}}var tail=buf.trim();if(tail){var raw=tail.replace(/^data:\\s*/,"");if(raw!=="[DONE]"&&raw){try{onEv(JSON.parse(raw))}catch(e){}}}}
function setBusy(b){sendBtn.disabled=b;stopBtn.disabled=!b}
async function sendChat(){var q=composer.value.trim();if(!q||ctl)return;var m=curModel();if(!m){toast("Pick a model first","err");return}ctl=new AbortController();setBusy(true);hist.push({role:"user",content:q});addUser(q);composer.value="";autoGrow();var host=addAsst();var tp=typingEl(host);var acc="";try{await ssePost("/api/chat",{model:m,messages:hist},function(ev){if(ev&&ev.error){acc+=ev.error;host.innerHTML=md(acc);return}var t=ev.content!=null?ev.content:(ev.text||ev.delta||"");if(typeof t==="string"&&t){acc+=t;if(tp&&tp.parentNode)tp.remove(),tp=null;host.innerHTML=md(acc);conv.scrollTop=conv.scrollHeight}});if(acc)hist.push({role:"assistant",content:acc);else if(tp)tp.remove()}catch(e){if(e&&e.name==="AbortError"){host.innerHTML=md(acc||"[stopped]");if(acc)hist.push({role:"assistant",content:acc})}else{host.innerHTML=md(acc+"\\n[error: "+e.message+"]");toast(e.message,"err")}}ctl=null;setBusy(false);loadSes()}
async function sendAgent(){var g=composer.value.trim();if(!g||ctl)return;var m=curModel();if(!m){toast("Pick a model first","err");return}ctl=new AbortController();setBusy(true);addUser(g);composer.value="";autoGrow();var ms=parseInt(maxSteps.value,10)||10;var card=toolCard("Agent: "+esc(g).slice(0,80),true);card.body.appendChild(preBox("goal",g));try{await ssePost("/api/agent",{goal:g,model:m,max_steps:ms,allow_bash:allowBash.checked,system:(sysPrompt.value||"").trim()||undefined},function(ev){if(!ev)return;if(ev.type==="step"){var c=toolCard("Step "+esc(ev.step||""));c.body.appendChild(preBox("",ev.text||""));c.done("ok")}else if(ev.type==="tool"){var t2=toolCard("Tool "+esc(ev.tool||"")+" (step "+esc(ev.step||"")+")");t2.body.appendChild(preBox("args",typeof ev.args==="string"?ev.args:JSON.stringify(ev.args||{},null,2)));t2.body.appendChild(preBox("result",String(ev.result==null?ev.output||"":ev.result)));t2.done(ev.error?"error":"ok")}else if(ev.type==="done"){card.body.appendChild(preBox("done session="+(ev.session_id||""),ev.text||""));card.done("ok");if(ev.text)hist.push({role:"assistant",content:String(ev.text)})}else if(ev.type==="error"){card.body.appendChild(preBox("error",ev.error||"unknown"));card.done("error");toast(ev.error||"agent error","err")}else if(ev.content){card.body.appendChild(preBox("",ev.content))}});card.done("ok")}catch(e){if(e&&e.name==="AbortError"){card.body.appendChild(preBox("","stopped"));card.done("error")}else{card.body.appendChild(preBox("error",e.message));card.done("error");toast(e.message,"err")}}ctl=null;setBusy(false);loadSes()}
sendBtn.onclick=function(){if(mode==="agent")sendAgent();else sendChat()};
stopBtn.onclick=function(){if(ctl)ctl.abort()};
clearBtn.onclick=function(){if(ctl)ctl.abort();hist=[];curSes=null;conv.innerHTML="";emptyEl.style.display="";composer.value="";autoGrow();renderSes();toast("New chat started")};
document.querySelectorAll(".chips button").forEach(function(b){b.onclick=function(){var v=b.getAttribute("data-s")||"";if(v.indexOf("via agent")>=0||v.indexOf("hello.txt")>=0)setMode("agent");composer.value=v;autoGrow();composer.focus()}});
$("newChat").onclick=function(){clearBtn.onclick();document.body.classList.remove("nav-open")};
function autoGrow(){composer.style.height="auto";composer.style.height=Math.min(180,Math.max(44,composer.scrollHeight))+"px"}
composer.addEventListener("input",autoGrow);
composer.addEventListener("keydown",function(e){if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="k"){e.preventDefault();composer.focus();return}if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();if(mode==="agent")sendAgent();else sendChat()}});
document.addEventListener("keydown",function(e){if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="k"){e.preventDefault();composer.focus()}});
async function loadSes(){try{var r=await fetch("/api/sessions");var d=await r.json();var items=d.sessions||d||[];if(!Array.isArray(items))items=[];sesCache=items.map(function(s){if(typeof s==="string")return{id:s,preview:""};return{id:s.id||s.session_id||JSON.stringify(s),preview:s.preview||""}});renderSes()}catch(e){side_list.innerHTML="<li>failed to load</li>"}}
function renderSes(){var q=(searchEl.value||"").toLowerCase();side_list.innerHTML="";var f=sesCache.filter(function(s){return!q||s.id.toLowerCase().indexOf(q)>=0});if(!f.length){side_list.innerHTML="<li>(no sessions)</li>";return}f.forEach(function(s){var li=document.createElement("li");li.tabIndex=0;li.setAttribute("role","button");var b=document.createElement("div");b.textContent=s.id;var sm=document.createElement("small");sm.textContent=s.preview||"tap to preview";li.appendChild(b);li.appendChild(sm);if(curSes===s.id)li.className="act";li.onclick=function(){viewSes(s.id)};li.onkeydown=function(e){if(e.key==="Enter")viewSes(s.id)};side_list.appendChild(li)})}
searchEl.addEventListener("input",renderSes);
async function viewSes(id){try{var r=await fetch("/api/sessions/"+encodeURIComponent(id));var d=await r.json();if(!r.ok)throw new Error(d.error||("HTTP "+r.status));curSes=id;renderSes();var msgs=d.messages||[];hist=msgs.filter(function(m){return m.role!=="system"});conv.innerHTML="";emptyEl.style.display=msgs.length?"none":"";msgs.forEach(function(m){if(m.role==="user")addUser(m.content||"");else if(m.role==="assistant"){var h=addAsst();h.innerHTML=md(m.content||"")}else{var h2=addAsst();h2.innerHTML=md(m.content||"")}});document.body.classList.remove("nav-open")}catch(e){toast("Session load failed: "+e.message,"err")}}
async function loadCfg(silent){try{var r=await fetch("/api/config");var d=await r.json();cfgCur.textContent="base: "+(d.base_url||"")+" | key: "+(d.api_key||"")+" | default: "+(d.default_model||"(not set)");keyDot.className="dot "+(d.has_key?"ok":"bad");keyDot.title=d.has_key?("API key set ("+(d.api_key||"")+")"):"API key missing";if(d.default_model){defModelEl.placeholder=d.default_model;if(!modelEl.value&&modelEl.querySelector){var ids=Array.from(modelEl.options).map(function(o){return o.value});if(ids.indexOf(d.default_model)>=0){modelEl.value=d.default_model;modelName.textContent="model: "+modelEl.value}}}}catch(e){if(!silent)toast("Config load failed","err");cfgCur.textContent="config unavailable"}}
function openCfg(){cfgModal.classList.add("on");cfgMsg.textContent="";cfgMsg.className="";loadCfg();setTimeout(function(){apiKeyEl.focus()},50)}
function closeCfg(){cfgModal.classList.remove("on")}
$("cfgBtn").onclick=openCfg;$("closeCfg").onclick=closeCfg;
cfgModal.addEventListener("click",function(e){if(e.target===cfgModal)closeCfg()});
$("showKey").onclick=function(){var p=apiKeyEl.type==="password";apiKeyEl.type=p?"text":"password";$("showKey").textContent=p?"Hide":"Show"};
$("saveCfg").onclick=async function(){cfgMsg.textContent="saving...";cfgMsg.className="";var p={};if(apiKeyEl.value.trim())p.api_key=apiKeyEl.value.trim();if(defModelEl.value.trim())p.default_model=defModelEl.value.trim();else if(curModel())p.default_model=curModel();if(!Object.keys(p).length){cfgMsg.textContent="Nothing to update.";cfgMsg.className="err";return}try{var r=await fetch("/api/config",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(p)});var d=await r.json();if(!r.ok)throw new Error(d.error||"save failed");cfgMsg.textContent="Saved. default="+(d.default_model||"");cfgMsg.className="ok";apiKeyEl.value="";toast("Config saved");loadCfg(true)}catch(e){cfgMsg.textContent=e.message;cfgMsg.className="err";toast(e.message,"err")}};
$("testBtn").onclick=async function(){cfgMsg.textContent="testing...";cfgMsg.className="";try{var r=await fetch("/api/models");var d=await r.json();if(!r.ok)throw new Error(d.error||("HTTP "+r.status));var n=idsFrom(d).length;cfgMsg.textContent="OK: "+n+" model(s) reachable";cfgMsg.className="ok";setStatus(true,"Connected: test ok")}catch(e){cfgMsg.textContent="Test failed: "+e.message;cfgMsg.className="err";setStatus(false,"Test failed: "+e.message);toast(e.message,"err")}};
autoGrow();boot();
</script>
</body>
</html>"""

from pathlib import Path
s = Path("board/HASHMARK.html").read_text(encoding="utf-8", errors="replace")
s = s.replace("SIM_N: 150000,", "SIM_N: 20000,")
s = s.replace("const n = Math.min(8000, (LIVE.SIM_N || 150000));", "const n = Math.min(20000, LIVE.SIM_N || 20000);")
s = s.replace("const n = (LIVE.SIM_N || 150000);", "const n = Math.min(20000, LIVE.SIM_N || 20000);")
s = s.replace("if (!fromFile && typeof liveRefresh === \"function\") {", "if (false && !fromFile && typeof liveRefresh === \"function\") {")
s = s.replace(".overlay {", ".overlay { pointer-events: none;")
s = s.replace(".overlay.show { display: flex; }", ".overlay.show { display: flex; pointer-events: auto; }")
if 'data-view="desk"' not in s:
    s = s.replace('<button class="tab active" data-view="nfl">NFL Week 3</button>',
                  '<button class="tab active" data-view="desk">Tonight\'s desk</button>\n      <button class="tab" data-view="nfl">NFL Week 3</button>')
    s = s.replace('<button class="tab" data-view="model">Model & desk</button>',
                  '<button class="tab" data-view="results">Results</button>\n      <button class="tab" data-view="model">Model & desk</button>')
    s = s.replace('<section id="boardSection">',
                  '<section id="deskSection"><div class="stat-row" id="deskStats"></div><div class="desk-grid" id="deskGrid"></div></section>\n    <section id="resultsSection" style="display:none"><div class="stat-row" id="resultsStats"></div><div class="prop-board" id="resultsBoard"></div></section>\n    <section id="boardSection" style="display:none">')
s = s.replace(".desk-grid{display:grid;gap:12px}", ".desk-grid{display:flex;gap:14px;overflow-x:auto;scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch;padding-bottom:16px;scrollbar-width:thin}")
if ".desk-grid{" not in s:
    s = s.replace("</style>", ".desk-grid{display:flex;gap:14px;overflow-x:auto;scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch;padding-bottom:16px;scrollbar-width:thin}.desk-col{flex:0 0 min(88vw,360px);scroll-snap-align:start}.desk-col h3{font-family:Fraunces,Georgia,serif}.prop-board{display:flex;gap:12px;overflow-x:auto;scroll-snap-type:x mandatory;padding-bottom:14px}.prop-board .prop-card{flex:0 0 min(86vw,340px);scroll-snap-align:start}\n</style>", 1)
else:
    if ".desk-col{flex:0 0" not in s:
        s = s.replace("</style>", ".desk-col{flex:0 0 min(88vw,360px);scroll-snap-align:start}.prop-board{display:flex;gap:12px;overflow-x:auto;scroll-snap-type:x mandatory;padding-bottom:14px}.prop-board .prop-card{flex:0 0 min(86vw,340px);scroll-snap-align:start}\n</style>", 1)
js = r'''
function restNote(g){const bits=[];const d=new Date(g.date||0);if(d.getDay()===4)bits.push("Short week");if(["Seattle","Santa Clara","Inglewood","Los Angeles","Glendale","Las Vegas","Denver"].some(c=>(g.city||"").includes(c))&&d.getHours()<=17)bits.push("West coast early window");return bits;}
function injuryBits(g){return (g.injuries||[]).filter(x=>x.status&&!/active/i.test(x.status)).map(x=>x.name+" "+x.status).slice(0,4);}
function applyInjuryTax(g){return g;}
function boardConfMatch(g,conf){if(!conf||conf==="ALL")return true;if(conf==="AFC"||conf==="NFC")return g.league==="nfl"&&(nflConf(g.home.abbr)===conf||nflConf(g.away.abbr)===conf);return g.league==="cfb"&&(cfbConf(g.home.name)===conf||cfbConf(g.away.name)===conf);}
function renderDesk(){if(!document.getElementById("deskGrid"))return;const up=(DATA.games||[]).filter(g=>!g.completed&&g.proj);const nfl=up.filter(g=>g.league==="nfl").sort((a,b)=>Math.abs(b.proj.edge_spread||0)-Math.abs(a.proj.edge_spread||0));const cfb=up.filter(g=>g.league==="cfb").sort((a,b)=>cfbPickScore(b)-cfbPickScore(a));const props=(typeof collectNflProps==="function"?collectNflProps():[]).filter(p=>!p.completed);props.forEach(p=>p._score=propScore(p));props.sort((a,b)=>b._score-a._score);const wx=up.filter(g=>!g.indoor&&((g.weather_impact||{}).harsh||(g.proj.weather_adj_total||-0)<-1));document.getElementById("deskStats").innerHTML=`<div class="stat"><b>${nfl.length}</b><span>NFL left</span></div><div class="stat"><b>${cfb.length}</b><span>CFB left</span></div><div class="stat"><b>${props.length}</b><span>props</span></div><div class="stat"><b>${wx.length}</b><span>weather</span></div>`;const lean=(g,k)=>{const p=g.proj||{};return `<article class="prop-card" data-id="${g.id}"><div class="who"><div><h4>${g.away.abbr} @ ${g.home.abbr}</h4><div class="prop-meta">${fmt.when(g.date)} · ${k}</div></div><div class="pick-score">${p.pick_line||p.total_pick||"lean"}</div></div></article>`;};document.getElementById("deskGrid").innerHTML=`<div class="desk-col"><h3>NFL leans</h3>${nfl.slice(0,5).map(g=>lean(g,"NFL")).join("")}</div><div class="desk-col"><h3>CFB leans</h3>${cfb.slice(0,5).map(g=>lean(g,"CFB")).join("")}</div><div class="desk-col"><h3>Props</h3>${props.slice(0,5).map(p=>`<article class="prop-card" data-id="${p.game_id}"><h4>${p.name}</h4><div class="prop-meta">${p.pos} · ${p.team}</div></article>`).join("")}</div><div class="desk-col"><h3>Weather</h3>${wx.slice(0,3).map(g=>lean(g,"WX")).join("")}</div>`;document.querySelectorAll("#deskGrid .prop-card").forEach(el=>el.addEventListener("click",()=>openGame(el.dataset.id)));}
function renderResults(){if(!document.getElementById("resultsBoard"))return;const done=(DATA.games||[]).filter(g=>g.completed&&g.proj&&g.home.score!=null);document.getElementById("resultsStats").innerHTML=`<div class="stat"><b>${done.length}</b><span>graded</span></div>`;document.getElementById("resultsBoard").innerHTML=done.map(g=>`<article class="prop-card"><h4>${g.away.abbr} ${g.away.score} @ ${g.home.abbr} ${g.home.score}</h4></article>`).join("")||"<div class='empty'>No finals yet.</div>";}
'''
if "function renderDesk(" not in s:
    s = s.replace("function setView(next) {", js + "\nfunction setView(next) {", 1)
s = s.replace('  setView("nfl");', '  setView("desk");')
s = s.replace(
    '  $("#boardSection").style.display = board ? "" : "none";\n  $("#propsSection").style.display = next === "props" ? "" : "none";',
    '  const desk=document.getElementById("deskSection"); if(desk) desk.style.display = next==="desk"?"":"none";\n  const resS=document.getElementById("resultsSection"); if(resS) resS.style.display = next==="results"?"":"none";\n  $("#boardSection").style.display = board ? "" : "none";\n  $("#propsSection").style.display = next === "props" ? "" : "none";'
)
s = s.replace(
    '  if (board) renderBoard();\n  if (next === "props") renderProps();',
    '  if (next === "desk") renderDesk();\n  if (next === "results") renderResults();\n  if (board) renderBoard();\n  if (next === "props") renderProps();'
)
Path("site").mkdir(exist_ok=True)
Path("site/index.html").write_text(s)
Path("index.html").write_text(s)
print("ok", len(s))

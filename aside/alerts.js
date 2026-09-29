/* Set aside 2026-09-29. Not loaded by the site.
   Put it back by restoring the Alerts tile, #alertBell, #alertsSection,
   the CSS below, scanAlerts() inside syncDesk, the setView lines,
   and the phone-alert button listener.

   CSS:
.alert-row{
  background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 14px;margin:0 0 8px;
}
.alert-row.hot{border-color:rgba(255,122,104,.45)}
.alert-bell{
  position:sticky;top:8px;z-index:5;display:none;
  background:#1a120c;border:1px solid rgba(240,180,41,.45);border-radius:14px;padding:10px 14px;margin:0 0 12px;
}

   Section:
<section id="alertsSection" style="display:none">
      <div class="controls">
        <button class="refresh-btn" id="notifBtn" type="button">Turn on phone alerts</button>
      </div>
      <p class="subn" style="margin:0 0 10px">We watch QB news, line jumps, and weather that would change a pick. Alerts fire on this phone while the site is open. Texts/emails need a later setup.</p>
      <div id="alertsWrap"></div>
    </section>

    
*/
function watchSnapshot(g) {
  const p = g.proj || {};
  const o = g.odds || {};
  const qb = (g.injuries || []).filter((r) => /QB/i.test(r.pos || "") && /OUT|IR|INACTIVE|DOUBT/i.test(r.tag || r.status || ""));
  return {
    spread: o.home_spread, total: o.total,
    pick: p.pick, total_pick: p.total_pick,
    wx: (g.weather_impact && g.weather_impact.adj) || 0,
    qb: qb.map((r) => r.name).join(", ")
  };
}
function pushAlert(kind, title, body, hot) {
  const desk = loadDesk();
  const sig = kind + "|" + title + "|" + body;
  if ((desk.alerts || []).some((a) => a.sig === sig)) return;
  const row = { t: Date.now(), kind, title, body, hot: !!hot, sig };
  desk.alerts.unshift(row);
  desk.alerts = desk.alerts.slice(0, 40);
  saveDesk();
  if (desk.notif && typeof Notification !== "undefined" && Notification.permission === "granted") {
    try { new Notification(title, { body, silent: false }); } catch (e) {}
  }
  const bell = document.getElementById("alertBell");
  if (bell) {
    bell.style.display = "block";
    bell.textContent = title + " — " + body;
    setTimeout(() => { if (bell.textContent.indexOf(title) === 0) bell.style.display = "none"; }, 8000);
  }
}
function scanAlerts() {
  const desk = loadDesk();
  const seedOnly = !window.__watchReady;
  (DATA.games || []).forEach((g) => {
    if (g.completed) return;
    const id = String(g.id);
    const now = watchSnapshot(g);
    const prev = desk.watch[id];
    desk.watch[id] = now;
    if (seedOnly || !prev) return;
    if (prev.spread != null && now.spread != null && Math.abs(Number(now.spread) - Number(prev.spread)) >= 1) {
      pushAlert("line", g.short_name + " line moved", `${g.home.abbr} ${prev.spread} → ${now.spread}`, true);
    }
    if (prev.total != null && now.total != null && Math.abs(Number(now.total) - Number(prev.total)) >= 1.5) {
      pushAlert("total", g.short_name + " total moved", `${prev.total} → ${now.total}`, false);
    }
    if ((now.qb || "") && now.qb !== (prev.qb || "")) {
      pushAlert("injury", "QB news · " + g.short_name, now.qb + " is on the report", true);
    }
    if (prev.pick && now.pick && prev.pick !== now.pick) {
      pushAlert("pick", "We flipped a pick · " + g.short_name, `${prev.pick} → ${now.pick}`, true);
    }
    if (prev.wx != null && now.wx != null && Math.abs(Number(prev.wx)) >= 0.4 && Math.abs(Number(now.wx) - Number(prev.wx)) >= 1.5) {
      pushAlert("wx", "Weather flipped the total · " + g.short_name, `weather tax ${prev.wx} → ${now.wx}`, false);
    }
  });
  window.__watchReady = true;
  saveDesk();
}

function renderAlerts() {
  const desk = loadDesk();
  const wrap = document.getElementById("alertsWrap");
  if (!wrap) return;
  const rows = desk.alerts || [];
  if (!rows.length) { wrap.innerHTML = `<div class="empty">Quiet for now. We’ll flag QB news, 1+ point line moves, and weather flips.</div>`; return; }
  wrap.innerHTML = rows.map((a) => `<article class="alert-row ${a.hot ? "hot" : ""}"><div class="lbl">${new Date(a.t).toLocaleString()}</div><b>${a.title}</b><div class="subn">${a.body}</div></article>`).join("");
}



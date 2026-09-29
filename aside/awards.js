/* Set aside 2026-09-29. Not loaded by the site.
   Put it back by adding the NFL tile:
     <a class="tab" href="#awards" data-view="awards">All awards</a>
   the awardsSection (select #awardPick, #awardStamp, #awardBoard),
   awards:1 in setView, the display toggle, renderNflAwards() on that view,
   and the awardPick change listener.
*/
const NFL_AWARDS = {
  mvp: {
    note: "DraftKings, Sept 22. Shortest price first.",
    rows: [
      { name: "Josh Allen", id: "3918298", pos: "QB", team: "BUF", odds: 290 },
      { name: "Brock Purdy", id: "4361741", pos: "QB", team: "SF", odds: 800 },
      { name: "Patrick Mahomes", id: "3139477", pos: "QB", team: "KC", odds: 800 },
      { name: "Joe Burrow", id: "3915511", pos: "QB", team: "CIN", odds: 850 },
      { name: "Lamar Jackson", id: "3916387", pos: "QB", team: "BAL", odds: 850 }
    ]
  },
  cpoy: {
    note: "DraftKings, Sept 22. Only the posted favorite is shown.",
    rows: [
      { name: "Patrick Mahomes", id: "3139477", pos: "QB", team: "KC", odds: -220 }
    ]
  }
};
function renderNflAwards() {
  const box = document.getElementById("awardBoard");
  const stamp = document.getElementById("awardStamp");
  const sel = document.getElementById("awardPick");
  if (!box) return;
  const key = (sel && sel.value) || "mvp";
  const pack = NFL_AWARDS[key];
  if (!pack || !pack.rows || !pack.rows.length) {
    if (stamp) stamp.textContent = "DraftKings did not have a board we could read for this award. No number is filled in.";
    box.innerHTML = `<div class="empty">No DraftKings price is posted here for this award.</div>`;
    return;
  }
  if (stamp) stamp.textContent = pack.note;
  const rows = pack.rows.slice().sort((a, b) => a.odds - b.odds);
  box.innerHTML = rows.map((p, i) => {
    const price = p.odds > 0 ? "+" + p.odds : String(p.odds);
    return `<article class="prop-card" style="cursor:default">
      <div class="who">
        <div class="who-row">
          <b style="font-family:Syne,sans-serif;font-size:22px;width:28px">${i + 1}</b>
          ${faceHtml(p.id, p.name, 56, "nfl")}
          <div>
            <h4>${escHtml(p.name)}</h4>
            <div class="prop-meta">${escHtml(p.team)} · ${escHtml(p.pos)}</div>
          </div>
        </div>
        <div style="text-align:right">
          <b style="font-family:Syne,sans-serif;font-size:28px;color:var(--sun)">${price}</b>
          <div class="prop-meta">DraftKings</div>
        </div>
      </div>
    </article>`;
  }).join("");
}

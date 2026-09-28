/* Set aside 2026-09-28. Not loaded by the site.
   Put it back by adding the college tile, the heismanSection, and the
   setView lines that called renderHeisman. */
const HEISMAN_BOOKS = ["DraftKings", "BetMGM", "Caesars"];
const HEISMAN_BOARD = [
  { name: "Trinidad Chambliss", id: "4911529", pos: "QB", team: "Ole Miss", books: { DraftKings: 290, BetMGM: 325, Caesars: 300 } },
  { name: "Darian Mensah", id: "5121169", pos: "QB", team: "Miami", books: { DraftKings: 370, BetMGM: 325, Caesars: 350 } },
  { name: "Jeremiah Smith", id: "5079720", pos: "WR", team: "Ohio State", books: { DraftKings: 1050, BetMGM: 1000, Caesars: 975 } },
  { name: "Arch Manning", id: "4870906", pos: "QB", team: "Texas", books: { DraftKings: 1400, BetMGM: 1000, Caesars: 1000 } },
  { name: "Kamario Taylor", id: "5177084", pos: "QB", team: "Mississippi State", books: { BetMGM: 1000, Caesars: 1100 } },
  { name: "Malachi Toney", id: "5159175", pos: "WR", team: "Miami", books: { DraftKings: 1300, BetMGM: 1000, Caesars: 1200 } },
  { name: "CJ Carr", id: "5079369", pos: "QB", team: "Notre Dame", books: { DraftKings: 1500, BetMGM: 1400, Caesars: 1200 } },
  { name: "Keelon Russell", id: "5141629", pos: "QB", team: "Alabama", books: { DraftKings: 2500, BetMGM: 2500, Caesars: 2500 } },
  { name: "Josh Hoover", id: "4685401", pos: "QB", team: "Indiana", books: { DraftKings: 2500, BetMGM: 3500, Caesars: 2500 } },
  { name: "Julian Sayin", id: "5079712", pos: "QB", team: "Ohio State", books: { DraftKings: 2500, BetMGM: 3000, Caesars: 3000 } }
];
function renderHeisman() {
  const box = document.getElementById("heismanBoard");
  const stamp = document.getElementById("heismanStamp");
  if (!box) return;
  if (stamp) stamp.textContent = "Ranking board for the 2026 Heisman. DraftKings is their Sept 21 price. BetMGM and Caesars are the other posted prices. A dash means that app did not list him.";
  const price = (p) => HEISMAN_BOOKS.map((b) => p.books[b]).filter((n) => Number.isFinite(n)).sort((a, b) => a - b);
  const rows = HEISMAN_BOARD.slice().sort((a, b) => {
    const pa = price(a), pb = price(b);
    return (pa[0] - pb[0]) || ((pa[1] || pa[0]) - (pb[1] || pb[0]));
  }).slice(0, 10);
  const head = HEISMAN_BOOKS.map((b) => `<th>${escHtml(b)}</th>`).join("");
  const body = rows.map((p, i) => {
    const best = price(p)[0];
    const cells = HEISMAN_BOOKS.map((b) => {
      const n = p.books[b];
      const shown = Number.isFinite(n) ? "+" + n : "—";
      return `<td class="price${n === best ? " best" : ""}">${shown}</td>`;
    }).join("");
    return `<tr>
      <td>${i + 1}</td>
      <td class="player"><div class="award-who">${faceHtml(p.id, p.name, 40, "cfb")}<div><b>${escHtml(p.name)}</b><div class="prop-meta">${escHtml(p.team)} · ${escHtml(p.pos)}</div></div></div></td>
      ${cells}
    </tr>`;
  }).join("");
  box.innerHTML = `<div class="award-board-wrap"><table class="award-board"><thead>
    <tr><th rowspan="2">#</th><th rowspan="2">Player</th><th colspan="${HEISMAN_BOOKS.length}">Betting apps</th></tr>
    <tr>${head}</tr>
  </thead><tbody>${body}</tbody></table></div>`;
}

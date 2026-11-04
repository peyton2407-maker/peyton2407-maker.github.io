// Create your own (the #create page): the question bar, its tickets, checks, comparisons,
// explanations, hedges and the saved-ticket record. Loaded by index.html the first time the
// page opens (loadCreateJs); it runs in the same global scope as the page's own script.
// ==== CREATE YOUR OWN =====================================================================
// A search bar that reads a plain-English request ("3 leg NFL parlay at +600", "safe college
// moneyline parlay Saturday", "Bills and Ravens", "Sunday prop unders", "longshot with
// Mahomes") and builds tickets from the live board: every side, total, moneyline and player
// prop we price, each leg valued with our checked chance at its best book, the ticket priced at
// the one book that pays the most for all its legs, with the reason for every leg. Runs in the
// page; nothing is sent anywhere.
const CREATE_WORDS = { one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, single: 1, double: 2, triple: 3 };
const CREATE_DAYS = { sunday: 0, sun: 0, monday: 1, mon: 1, tuesday: 2, tue: 2, tues: 2, wednesday: 3, wed: 3, thursday: 4, thu: 4, thurs: 4, friday: 5, fri: 5, saturday: 6, sat: 6 };
function createParse(text) {
  const raw = String(text || "");
  let q = " " + raw.toLowerCase().replace(/[’']/g, "").replace(/[^a-z0-9+\-.$ ]/g, " ").replace(/\s+/g, " ") + " ";
  const has = (re) => re.test(q);
  const want = { raw, legs: null, target: null, mode: "value", league: null, days: null, kinds: null, side: null, teams: [], players: [], notes: [] };
  // legs
  let m = q.match(/ (\d)\s*-?\s*(?:leg|legs|team|teams|pick|picks|piece|way|game|games)\b/) || q.match(/ (one|two|three|four|five|six|single|double|triple)\s*-?\s*(?:leg|legs|team|teams|pick|picks|way|game|games)?\b(?! (?:point|pts|td|tds|yards|yds))/);
  if (m) { const n = Number(m[1]) || CREATE_WORDS[m[1]]; if (n >= 1 && n <= 6) want.legs = n; }
  // payout target: +600, 6 to 1, 10-1, pays $100 on $10
  m = q.match(/ \+(\d{3,5})\b/);
  if (m) want.target = 1 + Number(m[1]) / 100;
  if (!want.target) { m = q.match(/ (\d{1,3})\s*(?:to|-|:)\s*1\b/); if (m) want.target = 1 + Number(m[1]); }
  if (!want.target) { m = q.match(/(?:pay|pays|win|turn|make)\s*\$?(\d+)\s*(?:on|with|from|off|for)\s*(?:a\s*)?\$?(\d+)/); if (m && Number(m[2]) > 0) want.target = Number(m[1]) / Number(m[2]) + (/win|make/.test(m[0]) ? 1 : 0); }
  // "$20 to win $200", "turn $20 into $200", "20 into 500", "bet 10 get 100"
  if (!want.target) { m = q.match(/\$?(\d+(?:\.\d+)?)\s*(?:to win|to make|to get|to profit|into|wins|returns|for a shot at|to collect)\s*\$?(\d+(?:\.\d+)?)/); if (m && Number(m[1]) > 0 && Number(m[2]) > Number(m[1])) { want.target = /into|returns|collect/.test(m[0]) ? Number(m[2]) / Number(m[1]) : 1 + Number(m[2]) / Number(m[1]); q = q.replace(m[0], " "); } }
  if (!want.target) { m = q.match(/ (?:around|about|near|roughly|close to|at|like) (-\d{3,4})\b/); if (m) want.target = pbDec(Number(m[1])); }
  if (!want.target && has(/ (even money|even odds|evens|pick ?em|coin flip|near even|around even|about even|close to even|one to one|1 to 1|1-1|\+100) /)) want.target = 2;
  want.explicitTarget = !!want.target;
  if (has(/ (safe|safest|likely|lock|locks|sure|high chance|best chance|low risk|conservative) /)) want.mode = "safe";
  if (has(/ (longshot|long shot|lotto|big payout|big money|huge|moonshot|dart|hail mary) /)) { want.mode = "long"; if (!want.target) want.target = 11; }
  if (want.target && want.mode === "value") want.mode = "target";
  // league
  if (has(/ (nfl|pro|sunday|monday night|thursday night|snf|mnf|tnf) /)) want.league = "nfl";
  if (has(/ (college|cfb|ncaa|ncaaf|saturday) /)) want.league = want.league === "nfl" && has(/ (college|cfb|ncaa|ncaaf) /) && !has(/ nfl /) ? "cfb" : (want.league || "cfb");
  if (has(/ (college|cfb|ncaa|ncaaf) /) && has(/ nfl /)) want.league = null;
  // days
  const days = new Set();
  Object.keys(CREATE_DAYS).forEach((d) => { if (new RegExp(" " + d + "(day)? ").test(q) || new RegExp(" " + d + " ").test(q)) days.add(CREATE_DAYS[d]); });
  if (has(/ (today|tonight) /)) days.add(new Date(new Date().toLocaleString("en-US", { timeZone: "America/New_York" })).getDay());
  if (has(/ (tomorrow) /)) days.add((new Date(new Date().toLocaleString("en-US", { timeZone: "America/New_York" })).getDay() + 1) % 7);
  if (has(/ (weekend) /)) [5, 6, 0, 1].forEach((d) => days.add(d));
  if (days.size) want.days = days;
  // time of day (kickoff, Eastern): night games, the early window, the late window
  const ET = (h) => new Date(new Date().toLocaleString("en-US", { timeZone: "America/New_York" }));
  if (has(/ (night|nights|nite|primetime|prime time|under the lights|snf|mnf|tnf) /)) want.hours = [19, 24];
  else if (has(/ (early|early window|early games|early slate|1 ?pm|1 oclock|noon|morning|first window) /)) want.hours = [0, 15];
  else if (has(/ (late window|late games|late slate|afternoon|4 ?pm|4 oclock|425|405|second window|late afternoon) /)) want.hours = [15, 19];
  if (has(/ (tonight) /)) want.hours = [ET().getHours() >= 17 ? ET().getHours() : 17, 24];
  if (has(/ (snf) /)) { want.days = new Set([0]); want.league = "nfl"; }
  if (has(/ (mnf) /)) { want.days = new Set([1]); want.league = "nfl"; }
  if (has(/ (tnf) /)) { want.days = new Set([4]); want.league = "nfl"; }
  // bet types
  const kinds = new Set();
  if (has(/ (moneyline|moneylines|money line|ml|to win|winners|straight up) /)) kinds.add("ml");
  if (has(/ (spread|spreads|ats|cover|covers|points|underdog|underdogs|dogs|favorite|favorites|favs) /)) kinds.add("sp");
  if (has(/ (total|totals|over under|o\/u|game total) /) || (has(/ (overs|unders|over|under) /) && !has(/ (prop|props|player|yards|yds|receptions|catches|touchdowns|tds|passing|rushing|receiving) /))) kinds.add("tot");
  if (has(/ (prop|props|player|players|yards|yds|receptions|catches|passing|rushing|receiving|pass tds|touchdown passes) /)) kinds.add("pp");
  if (has(/ (no props|without props|no player) /)) kinds.delete("pp");
  if (kinds.size) want.kinds = kinds;
  if (has(/ (underdog|underdogs|dogs|plus money) /)) want.dog = true;
  if (has(/ (favorite|favorites|favs|chalk) /)) want.fav = true;
  if (has(/ (unders|under) /) && !has(/ (overs|over) /)) want.side = "under";
  else if (has(/ (overs|over) /) && !has(/ (unders|under) /)) want.side = "over";
  // teams on the board: longest phrase first ("ohio state" before "ohio"), each match blanked
  // out so a shorter name can't match inside it; generic words never match a team alone
  const STOP = new Set(["college", "state", "university", "city", "north", "south", "east", "west", "central", "tech", "southern", "northern", "western", "eastern", "international", "the", "team", "teams", "game", "games"]);
  const phrases = [];
  const seenTeam = new Set();
  (DATA.games || []).forEach((g) => {
    if (!g || g.completed || !g.home || !g.away) return;
    [g.home, g.away].forEach((t) => {
      const key = g.league + ":" + t.abbr;
      if (seenTeam.has(key)) return;
      seenTeam.add(key);
      const full = String(t.name || "").toLowerCase().replace(/[’'.&]/g, "").replace(/\s+/g, " ").trim();
      const short = String(t.short || "").toLowerCase().replace(/[’'.&]/g, "").trim();
      const team = { league: g.league, abbr: t.abbr, name: t.name };
      const add = (ph) => { ph = String(ph || "").trim(); if (ph.length >= 4 && !STOP.has(ph)) phrases.push({ ph, team }); };
      add(full);
      add(short);
      if (short && full.endsWith(" " + short)) add(full.slice(0, -short.length - 1));   // location: "ohio state"
      const nick = full.split(" ").pop();
      if (nick && nick.length >= 5 && !STOP.has(nick)) add(nick);
      if (t.abbr && t.abbr.length >= 3 && new RegExp("\\b" + t.abbr + "\\b").test(raw)) phrases.push({ ph: "#abbr#" + t.abbr, team });
    });
  });
  phrases.sort((a, b) => b.ph.length - a.ph.length);
  let rest = q;
  const got = new Map();
  // "without the Chiefs", "no Chiefs game", "except Ohio State": those games stay out;
  // "fade the Chiefs", "against the Chiefs": only legs that need the Chiefs to lose
  want.exclude = []; want.fade = [];
  const exRe = / (without|except|excluding|minus|skip|skipping|avoid|avoiding|leave out|leaving out|not the|no|not|other than|besides) (the )?([a-z0-9 ]+?)(?= (and|or|but|parlay|parlays|ticket|tickets|please|game|games|legs?|this|that|tonight|today|tomorrow|on|for|at|in|with)\b| ?$)/g;
  const fdRe = / (fade|fading|against|bet against|betting against|sweat against|opposite of|opposite|oppose) (the )?([a-z0-9 ]+?)(?= (and|or|but|parlay|parlays|ticket|tickets|please|game|games|legs?|this|that|tonight|today|tomorrow|on|for|at|in|with)\b| ?$)/g;
  [[exRe, want.exclude], [fdRe, want.fade]].forEach(([re, list]) => {
    let mm;
    while ((mm = re.exec(rest))) {
      const seg = " " + mm[3] + " ";
      if (/ (prop|props|player|players|favorite|favorites|favs|chalk|underdog|underdogs|dogs|total|totals|spread|spreads|moneyline|moneylines) /.test(seg)) continue;
      let hit = false;
      phrases.forEach(({ ph, team }) => {
        if (ph.startsWith("#abbr#")) return;
        if (seg.includes(" " + ph + " ") && !list.some((t) => t.league === team.league && t.abbr === team.abbr) && (!want.league || team.league === want.league)) { list.push(team); hit = true; }
      });
      if (hit) rest = rest.replace(mm[0], " ~ ");
    }
  });
  phrases.forEach(({ ph, team }) => {
    const k = team.league + ":" + team.abbr;
    if (ph.startsWith("#abbr#")) { if (!got.has(k)) got.set(k, team); return; }
    const needle = " " + ph + " ";
    if (rest.includes(needle)) { rest = rest.split(needle).join(" ~ "); if (!got.has(k)) got.set(k, team); }
  });
  // a team named in both leagues by one word (e.g. "giants"): keep the league asked for
  want.teams = [...got.values()].filter((t) => !want.league || t.league === want.league);
  const words = new Set(rest.trim().split(" "));
  try {
    const seenP = new Set();
    (typeof nextPropRows === "function" ? nextPropRows() : []).forEach((p) => {
      const name = String(p.name || "").toLowerCase().replace(/[’'.]/g, "");
      const last = name.split(" ").filter((w) => !/^(jr|sr|ii|iii|iv)$/.test(w)).pop() || "";
      if (seenP.has(p.id)) return;
      if ((name.length > 5 && q.includes(" " + name + " ")) || (last.length >= 5 && words.has(last) && !STOP.has(last))) { seenP.add(p.id); want.players.push({ id: String(p.id), name: p.name, game_id: String(p.game_id) }); }
    });
  } catch (e) {}
  // typos: a leftover word one or two letters off a team or player name ("ravns", "jakson")
  want.fixed = []; want.unknown = []; want.missing = [];
  const pWords = new Set();
  want.players.forEach((pl) => String(pl.name || "").toLowerCase().replace(/[’'.]/g, "").split(" ").forEach((w) => pWords.add(w)));
  const left = rest.trim().split(" ").filter((w) => w && w !== "~" && !pWords.has(w));
  const singles = phrases.filter((x) => !x.ph.startsWith("#abbr#") && !x.ph.includes(" "));
  let propRows = [];
  try { propRows = typeof nextPropRows === "function" ? nextPropRows() : []; } catch (e) {}
  left.forEach((w) => {
    if (w.length < 4 || CREATE_KNOWN.has(w) || /\d/.test(w)) return;
    const max = w.length >= 8 ? 2 : 1;
    let best = null;
    singles.forEach((x) => { if (x.ph.length < 5) return; const d = crLev(w, x.ph, max); if (d <= max && d > 0 && (!best || d < best.d || (d === best.d && x.team.league === "nfl" && best.team && best.team.league !== "nfl"))) best = { d, team: x.team }; });
    propRows.forEach((pr) => {
      const last = String(pr.name || "").toLowerCase().replace(/[’'.]/g, "").split(" ").filter((x) => !/^(jr|sr|ii|iii|iv)$/.test(x)).pop() || "";
      if (last.length < 5) return;
      const d = crLev(w, last, max);
      if (d <= max && d > 0 && (!best || d < best.d)) best = { d, player: pr };
    });
    if (best && best.team && (!want.league || best.team.league === want.league) && !want.teams.some((t) => t.league === best.team.league && t.abbr === best.team.abbr)) { want.teams.push(best.team); want.fixed.push([w, best.team.name]); pWords.add(w); }
    else if (best && best.player && !want.players.some((x) => x.id === String(best.player.id))) { want.players.push({ id: String(best.player.id), name: best.player.name, game_id: String(best.player.game_id) }); want.fixed.push([w, best.player.name]); pWords.add(w); }
  });
  // a player named but not on this week's prop board (out, or no game)
  try {
    if (typeof collectNflProps === "function") {
      const onBoard = new Set(propRows.map((x) => String(x.id)));
      const seenM = new Set();
      collectNflProps().forEach((pr) => {
        if (onBoard.has(String(pr.id)) || seenM.has(String(pr.id))) return;
        const name = String(pr.name || "").toLowerCase().replace(/[’'.]/g, "");
        if (name.length > 5 && q.includes(" " + name + " ")) { seenM.add(String(pr.id)); want.missing.push({ name: pr.name, injury: pr.injury || "" }); name.split(" ").forEach((x) => pWords.add(x)); }
      });
    }
  } catch (e) {}
  want.unknown = left.filter((w) => !pWords.has(w) && !CREATE_KNOWN.has(w) && !/^[+\-$]?\d/.test(w) && w.length > 1 && !CREATE_DAYS[w] && !CREATE_WORDS[w]);
  if (want.players.length) { want.kinds = want.kinds || new Set(); want.kinds.add("pp"); }
  want.unknown = (want.unknown || []).filter((w) => !["without", "except", "excluding", "minus", "skip", "skipping", "avoid", "avoiding", "leave", "leaving", "other", "than", "besides", "fade", "fading", "against", "sweat", "opposite", "oppose", "into", "returns", "collect", "profit", "roughly", "close", "like", "even", "money", "odds", "evens", "pickem", "coin", "flip", "night", "nights", "nite", "primetime", "prime", "lights", "early", "window", "slate", "oclock", "noon", "morning", "first", "late", "afternoon", "second", "snf", "mnf", "tnf", "hail", "mary", "only"].includes(w));
  if (!want.legs) {
    const named = want.teams.length + want.players.length;
    if (named) want.legs = Math.max(1, Math.min(6, named));
    else if (want.explicitTarget && want.target) want.legs = want.target <= 2.2 ? 1 : want.target <= 5 ? 2 : want.target <= 12 ? 3 : want.target <= 30 ? 4 : 5;
    else want.legs = want.mode === "long" ? 4 : 2;
    if (want.legs === 1 && named === 1 && want.mode !== "safe" && !want.explicitTarget) want.legs = 2;
  }
  return want;
}
function createLegReason(g, id, pb) {
  const p = g.proj || {}, o = g.odds || {};
  const kind = String(id).split("|")[1], side = String(id).split("|").pop();
  const bits = [];
  if (kind === "sp" || kind === "ml") {
    const our = typeof cfbSideLabel === "function" && p.hashmark_home_spread != null ? cfbSideLabel(g, p.hashmark_home_spread) : "";
    if (our) bits.push(`Our number is ${our}; the line is ${o.details || "—"}.`);
    if (kind === "ml" && p.win_prob_home != null) bits.push(`We have ${side === "home" ? g.home.abbr : g.away.abbr} winning ${Math.round((side === "home" ? p.win_prob_home : p.win_prob_away) * 100)}% of the time before the record check.`);
  } else if (kind === "tot") {
    if (p.hashmark_total != null) bits.push(`Our total is ${Number(p.hashmark_total).toFixed(1)}; the posted total is ${o.total}.`);
  }
  const s = g.situational || {};
  (s.notes || []).filter((n) => /out|injur|weather|wind|rain|rest|travel/i.test(n) && !/line has moved|total has moved/i.test(n)).slice(0, 2).forEach((n) => bits.push(n));
  return bits.join(" ");
}
function createPool(want) {
  const now = Date.now();
  const etDay = (iso) => new Date(new Date(iso).toLocaleString("en-US", { timeZone: "America/New_York" })).getDay();
  const teamHit = (g) => want.teams.find((t) => t.league === g.league && (t.abbr === g.home.abbr || t.abbr === g.away.abbr));
  const legs = [];
  (DATA.games || []).forEach((g) => {
    if (!g || g.completed || !g.home || !g.away) return;
    const kick = Date.parse(g.date);
    if (!(kick > now) || kick - now > 8 * 864e5) return;
    if (want.league && g.league !== want.league) return;
    if (want.days && !want.days.has(etDay(g.date))) return;
    if (want.hours) { const h = new Date(new Date(g.date).toLocaleString("en-US", { timeZone: "America/New_York" })).getHours(); if (h < want.hours[0] || h >= want.hours[1]) return; }
    if ((want.exclude || []).some((t) => t.league === g.league && (t.abbr === g.home.abbr || t.abbr === g.away.abbr))) return;
    const faded = (want.fade || []).find((t) => t.league === g.league && (t.abbr === g.home.abbr || t.abbr === g.away.abbr));
    const named = teamHit(g);
    if ((want.teams.length || want.players.length) && !named && !faded && !want.players.some((pl) => pl.game_id === String(g.id))) return;
    const kinds = want.kinds || new Set(["sp", "tot", "ml", "pp"]);
    const push = (id, extra) => {
      const kind = id.split("|")[1];
      let pb = null, book = null;
      if (kind !== "pp") {
        const bp = typeof bestPriceFor === "function" ? bestPriceFor(id) : null;
        if (bp && bp.best) { book = bp.best.book; pb = pbLeg({ id, book }); }
      }
      pb = pb || pbLeg({ id });
      if (!pb || pb.started) return;
      const side = id.split("|").pop();
      if (named && kind !== "pp" && kind !== "tot") { const ab = side === "home" ? g.home.abbr : g.away.abbr; if (ab !== named.abbr) return; }
      if (faded && kind !== "tot") { const ab = side === "home" ? g.home.abbr : g.away.abbr; if (kind === "pp" || ab === faded.abbr) return; }
      if (kind === "sp" && want.dog && !(pb.line > 0)) return;
      if (kind === "sp" && want.fav && !(pb.line < 0)) return;
      if (kind === "ml" && want.dog && !(pb.price > 0)) return;
      if (kind === "ml" && want.fav && !(pb.price < 0)) return;
      if (kind === "ml" && !(pb.price >= -1000 && pb.price <= (want.mode === "long" || want.mode === "target" ? 1000 : 400))) return;
      if ((kind === "tot" || kind === "pp") && want.side && side !== want.side) return;
      legs.push(Object.assign({ id, gid: String(g.id), g, kind, pb, value: pb.value, win: pb.win, label: pb.label, book: book || pb.priceSource, reason: kind === "pp" ? "" : createLegReason(g, id, pb) }, extra || {}));
    };
    if (kinds.has("sp") && g.odds && g.odds.home_spread != null) { push(g.id + "|sp|home"); push(g.id + "|sp|away"); }
    if (kinds.has("tot") && g.odds && g.odds.total != null) { push(g.id + "|tot|over"); push(g.id + "|tot|under"); }
    if (kinds.has("ml") && (g.odds && (g.odds.home_ml || g.odds.away_ml))) { push(g.id + "|ml|home"); push(g.id + "|ml|away"); }
    if (kinds.has("pp") && g.league === "nfl" && typeof nextPropRows === "function") {
      nextPropRows().filter((p) => String(p.game_id) === String(g.id)).forEach((p) => {
        if (want.players.length && !want.players.some((x) => x.id === String(p.id))) return;
        const L = postedLean(p);
        if (!L || L.price == null || L.fair == null) return;
        const tid = typeof propTicketId === "function" ? propTicketId(p, L) : null;
        if (!tid) return;
        const mean = L.m.mean >= 10 ? Math.round(L.m.mean) : Number(L.m.mean).toFixed(1);
        push(tid, { prop: p, lean: L, reason: `We project ${p.name} for ${mean} ${PROP_LBL[L.m.key] || L.m.label} against ${L.line}; our checked chance on the ${L.take.toLowerCase()} is ${Math.round(L.chance * 100)}%, the books' ${Math.round(L.fair * 100)}%.${p.injury && p.injury !== "ACTIVE" ? " He's listed " + String(p.injury).toLowerCase() + "." : ""}`, player: p.name });
      });
    }
  });
  // best few per game, and the named ones first
  legs.sort((a, b) => b.value - a.value);
  const byGame = new Map();
  legs.forEach((l) => { const arr = byGame.get(l.gid) || []; if (arr.length < 3) { arr.push(l); byGame.set(l.gid, arr); } });
  return [...byGame.values()].flat().sort((a, b) => b.value - a.value).slice(0, 26);
}
// price a set of leg ids at every book that has all of them; the book that pays the most
function createPrice(ids) {
  let best = null;
  const tryBook = (book) => {
    const legs = ids.map((id) => pbLeg(book ? { id, book } : { id }));
    if (legs.some((l) => !l || l.started || (book && l.priceSource !== book))) return;
    const r = pbParlay(legs, 0);
    if (book) all.push({ book, american: r.american, dec: r.decEff, ev: r.ev });
    if (!best || r.ev > best.r.ev) best = { r, legs, book: book || null };
  };
  const all = [];
  tryBook(null);
  const names = new Set();
  ids.forEach((id) => Object.keys((((window.PB_BOOKS || {}).games || {})[id.split("|")[0]]) || {}).forEach((b) => names.add(b)));
  names.forEach(tryBook);
  if (best && !best.book) { const src = [...new Set(best.legs.map((l) => l.priceSource))]; best.book = src.length === 1 && !/standard|typical|estimated/.test(src[0]) ? src[0] : null; }
  if (best) best.all = all.sort((a, b) => b.dec - a.dec);
  return best;
}
function createTickets(want) {
  const pool = createPool(want);
  const gamesIn = new Set(pool.map((l) => l.gid)).size;
  let n = Math.min(want.legs, 6);
  let shrunk = null;
  if (gamesIn && gamesIn < n) { shrunk = { from: n, to: gamesIn }; n = gamesIn; }
  const needGames = new Set([...want.teams.map((t) => (DATA.games || []).filter((g) => !g.completed && g.league === t.league && (g.home.abbr === t.abbr || g.away.abbr === t.abbr) && Date.parse(g.date) > Date.now()).map((g) => String(g.id)).sort()[0]), ...want.players.map((p) => p.game_id)].filter(Boolean));
  const playerLegs = new Set(want.players.map((p) => p.id));
  if (pool.length < n) return { pool, tickets: [], shrunk };
  const score = (dec, chance, ev) => {
    if (want.mode === "safe") return chance * 2 + Math.min(ev, 0.05);
    if (want.mode === "target" || want.mode === "long") return -Math.abs(Math.log(dec) - Math.log(want.target || 4)) * 2 + ev;
    // best value, but a ticket that hits at least about 1 time in 8 (no +5000 lottery tickets)
    const floor = Math.min(0.12, Math.pow(0.5, n) * 0.6);
    return ev - (chance < floor ? 1 + (floor - chance) * 10 : 0);
  };
  // beam search over independent-leg estimates, then price the finalists exactly
  let beam = [[]];
  for (let k = 0; k < n; k++) {
    const next = [];
    beam.forEach((bag) => {
      pool.forEach((l) => {
        if (bag.some((b) => b.gid === l.gid)) return;
        if (bag.length && pool.indexOf(l) <= pool.indexOf(bag[bag.length - 1])) return;
        next.push(bag.concat([l]));
      });
    });
    const est = (bag) => {
      const dec = bag.reduce((a, l) => a * l.pb.dec, 1), chance = bag.reduce((a, l) => a * l.win, 1);
      const ev = bag.reduce((a, l) => a * (1 + l.value), 1) - 1;
      const covered = [...needGames].filter((gid) => bag.some((b) => b.gid === gid)).length;
      const plHit = bag.filter((b) => b.kind === "pp" && playerLegs.size && [...playerLegs].some((pid) => b.id.includes("|pp|" + pid + "|"))).length;
      return score(dec, chance, ev) + covered * 0.5 + plHit * 0.5;
    };
    next.sort((a, b) => est(b) - est(a));
    beam = next.slice(0, 60);
    if (!beam.length) break;
  }
  const tickets = [];
  const seen = new Set();
  beam.filter((bag) => bag.length === n).forEach((bag) => {
    const key = bag.map((l) => l.id).sort().join("~");
    if (seen.has(key)) return;
    seen.add(key);
    if ([...needGames].some((gid) => !bag.some((b) => b.gid === gid)) && needGames.size <= n) return;
    const x = createPrice(bag.map((l) => l.id));
    if (!x) return;
    tickets.push({ bag, x, s: score(x.r.decEff, x.r.pAll, x.r.ev) });
  });
  tickets.sort((a, b) => b.s - a.s);
  // three different tickets where possible
  const out = [], used = new Set();
  tickets.forEach((t) => { if (out.length < 3 && !t.bag.every((l) => used.has(l.id))) { out.push(t); t.bag.forEach((l) => used.add(l.id)); } });
  return { pool, tickets: out, shrunk };
}
function createUnderstood(want) {
  const chips = [];
  chips.push(want.legs + (want.legs === 1 ? " pick" : "-leg"));
  if (want.league) chips.push(want.league === "nfl" ? "NFL" : "College");
  if (want.days) chips.push([...want.days].map((d) => ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][d]).join(", "));
  if (want.kinds) chips.push([...want.kinds].map((k) => ({ sp: "spreads", tot: "totals", ml: "moneylines", pp: "player props" })[k]).join(" + "));
  if (want.hours) chips.push(want.hours[0] >= 19 ? "night games" : want.hours[1] <= 15 ? "early games" : want.hours[0] >= 17 ? "tonight" : "late-afternoon games");
  (want.exclude || []).forEach((t) => chips.push("not the " + (t.name.split(" ").pop())));
  (want.fade || []).forEach((t) => chips.push("against the " + (t.name.split(" ").pop())));
  if (want.side) chips.push(want.side === "under" ? "unders" : "overs");
  if (want.dog) chips.push("underdogs");
  if (want.fav) chips.push("favorites");
  want.teams.forEach((t) => chips.push(t.name));
  want.players.forEach((p) => chips.push(p.name));
  chips.push(want.mode === "safe" ? "highest chance" : want.mode === "long" || want.mode === "target" ? "aim for " + pbAm(pbAmerican(want.target)) : "best value");
  return chips.map((c) => `<span class="cr-chip">${pbEsc(c)}</span>`).join("");
}
function crLegParts(l) {
  const parts = String(l.id).split("|");
  const kind = parts[1], side = parts[parts.length - 1];
  const g = l.g;
  const team = side === "home" ? g.home : side === "away" ? g.away : null;
  const opp = side === "home" ? g.away : side === "away" ? g.home : null;
  return { kind, side, g, team, opp };
}
function crLineOf(pb) {
  if (pb && Number.isFinite(Number(pb.line))) return Number(pb.line);
  const m = String((pb && pb.label) || "").match(/([+-]?\d+(?:\.\d+)?)\s*$/);
  return m ? Number(m[1]) : null;
}
// one plain sentence: what has to happen for the leg to cash
function crNeeds(l, pb) {
  const { kind, side, g, team, opp } = crLegParts(l);
  const nm = (t) => (t && (t.short || t.abbr)) || "";
  const where = g.neutral ? "against" : side === "home" ? "at home against" : "on the road at";
  if (kind === "ml") return `${nm(team)} have to win ${where} ${nm(opp)}. Any margin counts.`;
  const ln = crLineOf(pb);
  if (ln == null) return "";
  if (kind === "sp") {
    if (Math.abs(ln) < 0.01) return `${nm(team)} have to win; a tie is a push.`;
    if (ln < 0) { const by = Number.isInteger(ln) ? -ln + 1 : Math.ceil(-ln); return `${nm(team)} have to win by ${by} or more${Number.isInteger(ln) ? ` (by exactly ${-ln} is a push)` : ""}.`; }
    const lose = Number.isInteger(ln) ? ln - 1 : Math.floor(ln);
    return `${nm(team)} have to win, or lose by ${lose} or fewer${Number.isInteger(ln) ? ` (by exactly ${ln} is a push)` : ""}.`;
  }
  if (kind === "tot") {
    if (side === "over") { const need = Number.isInteger(ln) ? ln + 1 : Math.ceil(ln); return `The two teams have to score ${need} or more points combined${Number.isInteger(ln) ? ` (exactly ${ln} is a push)` : ""}.`; }
    const need = Number.isInteger(ln) ? ln - 1 : Math.floor(ln);
    return `The two teams have to score ${need} or fewer points combined${Number.isInteger(ln) ? ` (exactly ${ln} is a push)` : ""}.`;
  }
  if (kind === "pp" && l.lean) {
    const L = l.lean, lbl = String(PROP_LBL[L.m.key] || L.m.label || "").toLowerCase();
    return `${l.player} has to finish ${L.take === "Under" ? "under" : "over"} ${L.line} ${lbl}.`;
  }
  return "";
}
function crTeamForm(g, t) {
  if (!t) return "";
  const rows = (window.WEEK_RESULTS || []).filter((r) => r && r.league === g.league && (String(r.homeId) === String(t.id) || String(r.awayId) === String(t.id)) && r.hs != null && r.as != null && Date.parse(r.date) < Date.parse(g.date));
  rows.sort((a, b) => Date.parse(b.date) - Date.parse(a.date));
  const last = rows.slice(0, 3).map((r) => {
    const home = String(r.homeId) === String(t.id);
    const us = Number(home ? r.hs : r.as), them = Number(home ? r.as : r.hs);
    return `${us > them ? "W" : us < them ? "L" : "T"} ${us}-${them} ${home ? "vs" : "at"} ${home ? r.awayAbbr : r.homeAbbr}`;
  });
  if (!t.record && !last.length) return "";
  return `<b>${pbEsc(t.abbr)}${t.record ? " " + pbEsc(t.record) : ""}</b>${last.length ? ": " + pbEsc(last.join(", ")) : ""}`;
}
function crMoveText(l) {
  const { kind, side, g, team } = crLegParts(l);
  const m = typeof lineMove === "function" ? lineMove(g) : null;
  if (!m) return "";
  if (kind === "sp" || kind === "ml") {
    if (m.sp0 == null || m.sp1 == null) return "";
    if (Math.abs(m.sp1 - m.sp0) < 0.25) return `The spread hasn't moved since it opened at ${spLabelOf(g, m.sp0)}.`;
    const toUs = (side === "home") === (m.sp1 < m.sp0);
    return `Opened ${spLabelOf(g, m.sp0)}, now ${spLabelOf(g, m.sp1)}. The market has moved ${toUs ? "toward" : "away from"} ${team.abbr}${toUs ? ", the same way as this pick" : "; our number still likes it at the current price"}.`;
  }
  if (kind === "tot") {
    if (m.t0 == null || m.t1 == null) return "";
    if (Math.abs(m.t1 - m.t0) < 0.25) return `The total hasn't moved since it opened at ${pbTot(m.t0)}.`;
    const toUs = (side === "over") === (m.t1 > m.t0);
    return `Opened ${pbTot(m.t0)}, now ${pbTot(m.t1)}. The market has moved ${toUs ? "the same way as this pick" : "against this pick; our number still likes it at the current total"}.`;
  }
  return "";
}
function crWeather(g) {
  if (g.indoor || (typeof roofedVenue === "function" && roofedVenue(g.venue && (g.venue.name || g.venue)))) return "Indoors, so weather isn't a factor.";
  const w = g.weather;
  if (!w || w.temp_f == null) return "";
  const bits = [`${w.condition || "Forecast"}, ${Math.round(w.temp_f)}°F, wind ${Math.round(w.wind_mph || 0)} mph`];
  if (w.precip_prob >= 30) bits.push(`${Math.round(w.precip_prob)}% chance of rain`);
  const wi = g.weather_impact;
  let s = bits.join(", ") + ".";
  if (wi && wi.note && Math.abs(Number(wi.adj) || 0) >= 1) s += ` ${wi.note} We take ${Math.abs(wi.adj).toFixed(1)} points ${wi.adj < 0 ? "off" : "onto"} the total for it.`;
  return s;
}
function crPropFacts(l, rows) {
  const p = l.prop, L = l.lean;
  if (!p || !L) return;
  const key = L.m.key, line = Number(L.line), under = L.take === "Under";
  const lbl = String(PROP_LBL[key] || L.m.label || "").toLowerCase();
  const mean = L.m.mean >= 10 ? Math.round(L.m.mean) : Number(L.m.mean).toFixed(1);
  rows.push(["Projection", `We project <b>${mean}</b> ${pbEsc(lbl)} against a line of ${line}.`]);
  const pack = window.GAMELOGS && window.GAMELOGS[String(p.id)];
  const logs = pack && (pack.rows || []).filter((r) => Number.isFinite(Number(r[key])));
  if (logs && logs.length) {
    const hit = (r) => under ? Number(r[key]) < line : Number(r[key]) > line;
    const yr = new Date().getFullYear();
    const part = (list, name) => list.length ? `${list.filter(hit).length} of ${name} ${list.length}` : "";
    const season = logs.filter((r) => Number(r.s) === yr);
    const five = logs.slice(0, 5).map((r) => Number(r[key]));
    rows.push(["Track record", `${under ? "Under" : "Over"} ${line} in ${[part(logs.slice(0, 5), "his last"), part(logs.slice(0, 10), "his last"), season.length ? `${season.filter(hit).length} of ${season.length} this season` : ""].filter(Boolean).join(", ")}. Last 5 games: ${five.join(", ")} (avg ${Math.round(five.reduce((a, x) => a + x, 0) / five.length * 10) / 10}).`]);
  }
  try {
    const t = typeof propDefTable === "function" ? propDefTable() : null;
    const d = t && p.opp && t[`${p.opp}|${p.pos}|${key}`];
    if (d) {
      const most = d.rank <= d.of / 2;
      rows.push(["Matchup", `${pbEsc(p.opp)} gives up the ${crOrd(most ? d.rank : d.of - d.rank + 1)} ${most ? "most" : "fewest"} ${PROP_DEF_STAT[key]} to ${pbEsc(p.pos)}s (${Math.round(d.avg * 10) / 10} a game)${(most && !under) || (!most && under) ? ", which helps this pick" : most && under ? ", the one thing working against this under" : ""}.`]);
    }
  } catch (e) {}
  { const n = propOppNote(p, key); if (n) rows.push(["Schedule", pbEsc(n)]); }
  if (p.injury && p.injury !== "ACTIVE") rows.push(["Status", `He's listed ${pbEsc(String(p.injury).toLowerCase())}. If he doesn't play, most books void the leg.`]);
}
function crLegFacts(l, pb) {
  const rows = [];
  const { kind, side, g } = crLegParts(l);
  const p = g.proj || {}, o = g.odds || {};
  const needs = crNeeds(l, pb);
  if (needs) rows.push(["To cash", pbEsc(needs)]);
  if (kind === "pp") crPropFacts(l, rows);
  else {
    if (p.home_points != null && p.away_points != null) rows.push(["Our score", `${pbEsc(g.away.abbr)} ${Math.round(p.away_points)}, ${pbEsc(g.home.abbr)} ${Math.round(p.home_points)}`]);
    if ((kind === "sp" || kind === "ml") && p.hashmark_home_spread != null) {
      const ours = spLabelOf(g, p.hashmark_home_spread), posted = o.home_spread != null ? spLabelOf(g, o.home_spread) : (o.details || "—");
      const gap = o.home_spread != null ? Math.abs(Number(p.hashmark_home_spread) - Number(o.home_spread)) : null;
      rows.push(["Our number", `${pbEsc(ours)} vs the line ${pbEsc(posted)}${gap != null && gap >= 0.5 ? `, ${gap.toFixed(1)} points ${((side === "home") === (Number(p.hashmark_home_spread) < Number(o.home_spread))) ? "in this pick's favor" : "the other way, so the value is in the price"}` : ""}.`]);
    }
    if (kind === "tot" && p.hashmark_total != null && o.total != null) {
      const gap = Number(p.hashmark_total) - Number(o.total);
      rows.push(["Our number", `Our total is ${Number(p.hashmark_total).toFixed(1)} vs ${pbTot(o.total)} posted${Math.abs(gap) >= 0.5 ? `, ${Math.abs(gap).toFixed(1)} points ${gap < 0 ? "lower" : "higher"}` : ""}.`]);
    }
    if (kind === "ml" && p.win_prob_home != null) rows.push(["Win chance", `Our ratings alone have ${pbEsc(side === "home" ? g.home.abbr : g.away.abbr)} winning ${Math.round((side === "home" ? p.win_prob_home : p.win_prob_away) * 100)}% of the time.`]);
    if (p.home_fpi_rank != null && p.away_fpi_rank != null) rows.push(["Power rank", `${pbEsc(g.away.abbr)} ${crOrd(p.away_fpi_rank)}, ${pbEsc(g.home.abbr)} ${crOrd(p.home_fpi_rank)} in ESPN's FPI${g.league === "nfl" ? " (of 32)" : ""}.`]);
    const form = [crTeamForm(g, g.away), crTeamForm(g, g.home)].filter(Boolean);
    if (form.length) rows.push(["Form", form.join("<br>")]);
    const mv = crMoveText(l);
    if (mv) rows.push(["Line move", pbEsc(mv)]);
  }
  if (kind === "tot") { const pt = paceFactText(g); if (pt) rows.push(["Pace", pt]); }
  if (kind === "tot" || kind === "pp") { const w = crWeather(g); if (w) rows.push(["Weather", pbEsc(w)]); }
  const s = g.situational || {};
  const notes = (s.notes || []).filter((n) => /out|injur|doubtful|questionable|weather|wind|rain|rest|travel|short week|bye/i.test(n) && !/line has moved|total has moved/i.test(n)).slice(0, 3);
  if (notes.length) rows.push(["News", notes.map(pbEsc).join(" ")]);
  // price shopping for this one leg
  const bp = kind !== "pp" && typeof bestPriceFor === "function" ? bestPriceFor(l.id) : null;
  if (bp && bp.rows && bp.rows.length > 1) {
    const worst = bp.rows[bp.rows.length - 1];
    rows.push(["Shop it", `Best is ${pbEsc(bp.best.book)} ${kind === "ml" ? "" : (bp.best.line != null ? pbLine(bp.best.line) + " " : "")}${pbAm(bp.best.price)} across ${bp.rows.length} books; the worst is ${pbEsc(worst.book)} ${kind === "ml" ? "" : (worst.line != null ? pbLine(worst.line) + " " : "")}${pbAm(worst.price)}.`]);
  }
  return rows;
}
function crMeter(ours, books) {
  const o = Math.max(0, Math.min(1, Number(ours) || 0)), b = Math.max(0, Math.min(1, Number(books) || 0));
  return `<div class="cr-meter" role="img" aria-label="Our chance ${Math.round(o * 100)}%, the books' ${Math.round(b * 100)}%"><i style="width:${(o * 100).toFixed(1)}%"></i><s style="left:${(b * 100).toFixed(1)}%"></s></div>`;
}
function crLegHtml(l, pb) {
  const facts = crLegFacts(l, pb);
  const val = pb.value;
  return `<li class="cr-leg" data-id="${pbEsc(l.gid)}">
    <div class="cr-leg-top"><b>${pbEsc(pb.label)}</b><span class="cr-px">${pbAm(pb.price)}</span></div>
    <div class="subn">${pbEsc(l.g.short_name)} · ${fmt.when(l.g.date)}</div>
    ${crMeter(pb.win, pb.bookWin)}
    <div class="subn">Our checked chance <b>${Math.round(pb.win * 100)}%</b> · the books' ${Math.round(pb.bookWin * 100)}% · <span class="${val >= 0.005 ? "cr-up" : val <= -0.01 ? "cr-down" : ""}">${(val >= 0 ? "+" : "") + (val * 100).toFixed(1)}% value</span></div>
    ${facts.length ? `<dl class="cr-facts">${facts.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>` : ""}
  </li>`;
}
function crSwapOptions(t) {
  const st = window.__crState;
  if (!st || !st.res) return { weak: null, alts: [] };
  const legs = t.x.legs;
  let wi = 0;
  t.bag.forEach((l, k) => { if ((legs[k] || l.pb).value < (legs[wi] || t.bag[wi].pb).value) wi = k; });
  const weak = t.bag[wi];
  const games = new Set(t.bag.filter((_, k) => k !== wi).map((l) => l.gid));
  const ids = new Set(t.bag.map((l) => l.id));
  // each candidate priced as the whole new ticket; keep the ones that make it a better bet
  // without turning it into a different kind of ticket (no more than 1.6x the payout)
  const alts = [];
  st.res.pool.filter((l) => !ids.has(l.id) && !games.has(l.gid) && l.value > (legs[wi] || weak.pb).value).slice(0, 12).forEach((l) => {
    const bag = t.bag.slice(); bag[wi] = l;
    const x = createPrice(bag.map((b) => b.id));
    if (!x || !(x.r.ev > t.x.r.ev) || x.r.decEff > t.x.r.decEff * 1.6 || x.r.decEff < t.x.r.decEff / 1.6) return;
    alts.push({ l, x });
  });
  alts.sort((a, b) => b.x.r.ev - a.x.r.ev);
  return { weak, wi, alts: alts.slice(0, 3) };
}
function createTicketHtml(t, i) {
  const r = t.x.r, legs = t.x.legs;
  const ev = r.ev;
  const verdict = ev >= 0.03 ? { cls: "good", text: `Good price: +${Math.round(ev * 100)}% value` } : ev >= -0.01 ? { cls: "", text: "About a fair price" } : { cls: "bad", text: `The book has the edge: ${Math.round(ev * 100)}% value` };
  const pbs = t.bag.map((l, k) => legs[k] || l.pb);
  const beat = pbs.filter((pb) => pb.value > 0).length;
  const oneIn = r.pAll > 0 ? 1 / r.pAll : null;
  const idx = (f) => pbs.reduce((b, pb, k) => (f(pb) > f(pbs[b]) ? k : b), 0);
  const strong = idx((pb) => pb.value), safe = idx((pb) => pb.win), risky = idx((pb) => -pb.win);
  const caseRows = [
    ["Strongest edge", `<b>${pbEsc(pbs[strong].label)}</b>: ${(pbs[strong].value >= 0 ? "+" : "") + (pbs[strong].value * 100).toFixed(1)}% value; our chance ${Math.round(pbs[strong].win * 100)}% vs the books' ${Math.round(pbs[strong].bookWin * 100)}%.`],
    ["Safest leg", `<b>${pbEsc(pbs[safe].label)}</b> hits ${Math.round(pbs[safe].win * 100)}% of the time.`],
    ["Biggest risk", `<b>${pbEsc(pbs[risky].label)}</b> is the leg most likely to miss (${Math.round((1 - pbs[risky].win) * 100)}% of the time).`]
  ];
  if (t.bag.length < 2) caseRows.splice(1);
  const why = [t.bag.length === 1 ? (beat ? `It beats its own price${t.x.book ? " at " + t.x.book : ""}.` : `It doesn't beat its own price${t.x.book ? " at " + t.x.book : ""}.`) : `${beat} of ${t.bag.length} legs beat their own price${t.x.book ? " at " + t.x.book : ""}.`];
  if (t.bag.length > 1 && new Set(t.bag.map((l) => l.gid)).size === t.bag.length) why.push(`Every leg is from a different game, so one result doesn't drag the others down with it.`);
  if (ev >= 0.03) why.push(`At ${pbAm(r.american)} the book pays more than a ticket that hits ${pbPct(r.pAll)} of the time is worth (it needs ${pbPct(r.breakEven)}).`);
  else if (ev >= -0.01) why.push(`The price is about right for how often it hits, so this is a fun ticket rather than an edge.`);
  else why.push("The book has the edge on this one, so treat it as a lean, not a pick.");
  const all = (t.x.all || []).filter((b) => Number.isFinite(b.dec));
  const shop = all.length > 1 ? `<div class="cr-books"><span class="lbl">This ticket at each book</span>${all.slice(0, 6).map((b, k) => `<span class="${k === 0 ? "best" : ""}">${pbEsc(b.book)} <b>${pbAm(b.american)}</b></span>`).join("")}${all.length > 1 ? `<span class="subn">Betting $10 at ${pbEsc(all[0].book)} instead of ${pbEsc(all[all.length - 1].book)} pays ${pbMoney(10 * (all[0].dec - all[all.length - 1].dec))} more.</span>` : ""}</div>` : "";
  const sw = t.check ? { alts: [] } : crSwapOptions(t);
  const swap = sw.weak && sw.alts.length ? `<div class="cr-swap"><span class="lbl">Swap the weakest leg (${pbEsc((legs[sw.wi] || sw.weak.pb).label)}) for</span>${sw.alts.map((a) => `<button type="button" data-crswap="${i}|${sw.wi}|${pbEsc(a.l.id)}">${pbEsc(a.l.label)} ${pbAm(a.l.pb.price)} <em>ticket ${pbAm(a.x.r.american)}, ${(a.x.r.ev >= 0 ? "+" : "") + Math.round(a.x.r.ev * 100)}% value</em></button>`).join("")}</div>` : "";
  return `<article class="parlay-card ready cr-ticket" data-cri="${i}">
    <div class="td-mkt">${t.cmpTitle ? t.cmpTitle + " · " + t.bag.map((l, k) => (legs[k] || l.pb).label).join(" + ") : t.check ? (t.bag.length === 1 ? "Your bet" : "Your ticket · " + t.bag.length + "-leg") : (i === 0 ? "Best match" : "Another option") + " · " + t.bag.length + "-leg"}${t.swapped ? " · edited" : ""}</div>
    <div class="parlay-odds">${pbAm(r.american)}</div>
    <div class="subn">$10 pays ${pbMoney(10 * r.decEff)}${t.x.book ? " at " + pbEsc(t.x.book) : ""} · hits about ${pbPct(r.pAll)} of the time${oneIn ? ` (1 in ${oneIn < 10 ? oneIn.toFixed(1) : Math.round(oneIn)})` : ""}, the price needs ${pbPct(r.breakEven)}</div>
    ${crMeter(r.pAll, r.breakEven)}
    <div class="ready-val ${verdict.cls}">${verdict.text}</div>
    ${sizeHtml(kellyUnits(r.pAll, null, { dec: r.decEff, cap: t.bag.length > 1 ? 1 : 2 }))}
    <p class="subn" style="color:var(--ink);margin:8px 0 6px"><b>Why take it:</b> ${pbEsc(why.join(" "))}</p>
    <dl class="cr-facts cr-case">${caseRows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>
    ${shop}
    <ul class="parlay-legs cr-legs${t.bag.length === 1 ? " one" : ""}">${t.bag.map((l, k) => crLegHtml(l, pbs[k])).join("")}</ul>
    ${swap}
    <div class="cr-actions">
      <button type="button" class="cr-act save${crIsSaved(t) ? " done" : ""}" data-crsave="${i}"${crIsSaved(t) ? " disabled" : ""}>${crIsSaved(t) ? "★ Saved to My bets" : "☆ Save to My bets"}</button>
      <button type="button" class="cr-act" data-crshare="${pbEsc("t=" + t.bag.map((l) => encodeURIComponent(l.id)).join("~"))}">Share ticket</button>
    </div>
    <button type="button" class="ready-open" data-openpb="${t.bag.map((l) => l.id).join("~")}">Open in parlay builder</button>
  </article>`;
}
// ---- Create your own: words we understand, typo matching, and the search box helpers -------
const CREATE_KNOWN = new Set(("hedge hedging lock cash cashout guarantee insure hit hits won cashed covered left remaining still pending open last live later already then collect collects pays payout risked why explain case thoughts think break breakdown sell talk reasoning reason wrong model like a an the and or with for on at of to in into me my i im want need give get show find make build create bet bets betting wager parlay parlays parley parleys ticket tickets slip leg legs team teams pick picks piece way game games best good great top value ev plus positive edge smart sharp safe safest likely lock locks sure high chance low risk conservative longshot long shot lotto big payout money huge moonshot dart nfl pro sunday monday thursday saturday friday tuesday wednesday night snf mnf tnf college cfb ncaa ncaaf football today tonight tomorrow weekend this next week weeks moneyline moneylines line lines ml win winner winners straight up spread spreads ats cover covers points point pts total totals over under overs unders ou o u prop props player players yards yds yard receptions reception catches passing rushing receiving pass rush rec tds td touchdown touchdowns no without underdog underdogs dogs dog favorite favorites favs fav chalk around about odds pays pay return turn from off dollars dollar bucks is it should take bad any some that what who which can you please one two three four five six single double triple only just also check grade rate how would do does will be are am so up down vs versus against something even pk pickem than more less most least").split(" "));
function crLev(a, b, max) {
  a = String(a); b = String(b);
  if (Math.abs(a.length - b.length) > max) return max + 1;
  let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    let lo = i;
    for (let j = 1; j <= b.length; j++) {
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      if (cur[j] < lo) lo = cur[j];
    }
    if (lo > max) return max + 1;
    prev = cur;
  }
  return prev[b.length];
}
function crNorm(x) { return " " + String(x || "").toLowerCase().replace(/[’']/g, "").replace(/[^a-z0-9+\-. ]/g, " ").replace(/\s+/g, " ").trim() + " "; }
// every team with a game coming up (its next one), and every player on the prop board
function crIndex() {
  const sig = (DATA.games || []).length + "|" + Math.floor(Date.now() / 60000) + "|" + ((window.__WEEK_PLAYERS || []).length);
  if (crIndex.c && crIndex.c.sig === sig) return crIndex.c.v;
  const now = Date.now(), teams = new Map();
  // upcoming games, plus ones that kicked off in the last 5 hours and aren't final (live: for hedges)
  (DATA.games || []).filter((g) => g && !g.completed && g.home && g.away && Date.parse(g.date) > now - 5 * 3600e3 && Date.parse(g.date) - now < 9 * 864e5)
    .sort((a, b) => Date.parse(a.date) - Date.parse(b.date))
    .forEach((g) => [g.home, g.away].forEach((t) => {
      const k = g.league + ":" + t.abbr;
      if (teams.has(k)) return;
      const full = String(t.name || "").toLowerCase().replace(/[’'.&]/g, "").replace(/\s+/g, " ").trim();
      const short = String(t.short || "").toLowerCase().replace(/[’'.&]/g, "").trim();
      const keys = [full, short];
      if (short && full.endsWith(" " + short)) keys.push(full.slice(0, -short.length - 1));
      const nick = full.split(" ").pop();
      if (nick && nick.length >= 5) keys.push(nick);
      teams.set(k, { league: g.league, abbr: t.abbr, name: t.name, short: t.short || t.abbr, g, side: g.home === t ? "home" : "away", keys: [...new Set(keys.filter((x) => x && x.length >= 3))] });
    }));
  let players = [];
  try { players = (typeof nextPropRows === "function" ? nextPropRows() : []).map((p) => { const name = String(p.name || "").toLowerCase().replace(/[’'.]/g, ""); const parts = name.split(" ").filter((x) => !/^(jr|sr|ii|iii|iv)$/.test(x)); return { p, name, first: parts[0] || "", last: parts[parts.length - 1] || "" }; }); } catch (e) {}
  const v = { teams: [...teams.values()], players };
  crIndex.c = { sig, v };
  return v;
}
function crFindTeam(q, raw) {
  const idx = crIndex();
  let best = null;
  idx.teams.forEach((t) => t.keys.forEach((k) => { if (q.includes(" " + k + " ") && (!best || k.length > best.len || (k.length === best.len && t.league === "nfl" && best.t.league !== "nfl"))) best = { t, len: k.length }; }));
  if (!best) idx.teams.forEach((t) => { if (t.abbr && t.abbr.length >= 2 && new RegExp("(^|[^A-Za-z])" + t.abbr + "([^A-Za-z]|$)").test(raw)) best = best || { t, len: 0 }; });
  if (!best) {
    q.trim().split(" ").filter((w) => w.length >= 4 && !CREATE_KNOWN.has(w)).forEach((w) => {
      const max = w.length >= 8 ? 2 : 1;
      idx.teams.forEach((t) => t.keys.filter((k) => !k.includes(" ") && k.length >= 5).forEach((k) => { const d = crLev(w, k, max); if (d <= max && (!best || d < best.d || (d === best.d && t.league === "nfl" && best.t.league !== "nfl"))) best = { t, d, fixed: [w, t.name] }; }));
    });
  }
  return best;
}
function crFindPlayer(q) {
  const idx = crIndex();
  let hit = idx.players.find((x) => x.name.length > 5 && q.includes(" " + x.name + " "));
  if (hit) return { p: hit.p };
  const words = q.trim().split(" ");
  const byLast = idx.players.filter((x) => x.last.length >= 4 && words.includes(x.last));
  if (byLast.length === 1) return { p: byLast[0].p };
  if (byLast.length > 1) { const both = byLast.find((x) => words.includes(x.first)); if (both) return { p: both.p }; }
  let best = null;
  words.filter((w) => w.length >= 5 && !CREATE_KNOWN.has(w)).forEach((w) => {
    const max = w.length >= 8 ? 2 : 1;
    idx.players.forEach((x) => { if (x.last.length < 5) return; const d = crLev(w, x.last, max); if (d <= max && (!best || d < best.d)) best = { p: x.p, d, fixed: [w, x.p.name] }; });
  });
  return best;
}
const CR_STATS = [["pass_td", /pass(ing)? ?(td|tds|touchdown)|td pass|touchdown pass/], ["pass_yds", /pass/], ["rush_yds", /rush/], ["rec_yds", /(receiving|rec yds|rec yards|rec yard)/], ["rec", /(recept|catches| rec )/]];
// A bet someone already has in mind: "Bills -3, Lamar under 224.5, over 47.5". Each piece
// becomes one leg; a piece with only a total ("over 47.5") belongs to the game before it.
function crParseSlip(text) {
  const raw = String(text || "");
  const segs = raw.split(/\s*(?:,|;|\n|\s\+\s|\s&\s|\sand\s|\splus\s|\swith\s|\salso\s)\s*/i).map((x) => x.trim()).filter(Boolean);
  const all = crNorm(raw);
  const globalMl = / (moneyline|moneylines|money line|ml|to win|straight up) /.test(all);
  const globalSp = / (spread|spreads|ats) /.test(all);
  const legs = [], bare = [], miss = [], fixed = [];
  let lastG = null, explicit = 0;
  segs.forEach((segRaw) => {
    const q = crNorm(segRaw);
    const ou = q.match(/ (over|under|o|u) ?(\d{1,3}(?:\.\d+)?)? /);
    const hasOu = ou && (ou[2] != null || / (over|under) /.test(q));
    const take = ou && /^(over|o)$/.test(ou[1]) ? "over" : "under";
    const num = ou && ou[2] != null ? Number(ou[2]) : null;
    const pl = crFindPlayer(q);
    if (pl && pl.p && hasOu) {
      const p = pl.p;
      const dk = typeof dkFor === "function" ? dkFor(p.game_id, p.id) : {};
      let stat = (CR_STATS.find(([, re]) => re.test(q)) || [])[0] || null;
      if (!stat) {
        const avail = ["pass_yds", "rush_yds", "rec_yds", "rec", "pass_td"].filter((k) => dk[k] != null);
        if (num != null && avail.length) stat = avail.sort((a, b) => Math.abs(dk[a] - num) - Math.abs(dk[b] - num))[0];
        else { try { const L = postedLean(p); stat = L && L.m.key; } catch (e) {} }
        stat = stat || (p.pos === "QB" ? "pass_yds" : p.pos === "RB" ? "rush_yds" : "rec_yds");
      }
      if (pl.fixed) fixed.push(pl.fixed);
      legs.push({ id: `${p.game_id}|pp|${p.id}|${stat}|${take}`, seg: segRaw, userLine: num, player: p });
      explicit++; lastG = pbGame(p.game_id); return;
    }
    const tm = crFindTeam(q, segRaw);
    if (tm && tm.t) {
      const t = tm.t, g = t.g, side = t.side;
      if (tm.fixed) fixed.push(tm.fixed);
      lastG = g;
      const spm = q.match(/ ([+-]\d{1,2}(?:\.5)?|pk|pick ?em|even) /);
      if (hasOu) { legs.push({ id: `${g.id}|tot|${take}`, seg: segRaw, userLine: num }); explicit++; return; }
      if (/ (ml|moneyline|money line|to win|win|wins|straight up|su) /.test(q)) { legs.push({ id: `${g.id}|ml|${side}`, seg: segRaw }); explicit++; return; }
      if (spm || / (spread|cover|covers|ats) /.test(q)) {
        const ln = spm ? (/pk|pick|even/.test(spm[1]) ? 0 : Number(spm[1])) : null;
        legs.push({ id: `${g.id}|sp|${side}`, seg: segRaw, userLine: ln }); explicit++; return;
      }
      const un = q.match(/ (\d{1,2}(?:\.5)?) /);
      if (un && Number(un[1]) <= 40 && !/ (leg|legs|team|teams|pick|picks|to 1|way) /.test(q)) {
        const cur = pbLeg({ id: `${g.id}|sp|${side}` });
        const sign = cur && cur.line < 0 ? -1 : 1;
        legs.push({ id: `${g.id}|sp|${side}`, seg: segRaw, userLine: sign * Number(un[1]) }); explicit++; return;
      }
      if (globalMl) { legs.push({ id: `${g.id}|ml|${side}`, seg: segRaw }); return; }
      if (globalSp) { legs.push({ id: `${g.id}|sp|${side}`, seg: segRaw }); return; }
      bare.push(segRaw); return;
    }
    if (hasOu && num != null && lastG && !pl) { legs.push({ id: `${lastG.id}|tot|${take}`, seg: segRaw, userLine: num }); explicit++; return; }
    if (/\d/.test(q) && / (over|under|o|u|[+-]\d)/.test(q)) {
      const off = (DATA.games || []).flatMap((g) => g && g.home && g.away ? [g.home, g.away] : []).find((t) => { const sh = String(t.short || "").toLowerCase(); const full = String(t.name || "").toLowerCase().replace(/[’'.&]/g, ""); return (sh.length >= 4 && q.includes(" " + sh + " ")) || (full && q.includes(" " + full + " ")); });
      if (off) miss.push({ seg: segRaw, why: `The ${off.short || off.name} don't have a game on the board in the next week.` });
      else miss.push({ seg: segRaw, why: `I couldn't tell which team or player "${segRaw}" is.` });
    }
  });
  const seen = new Set();
  const uniq = legs.filter((l) => !seen.has(l.id) && seen.add(l.id));
  const check = uniq.length >= 1 && explicit >= 1 && !bare.length;
  return { check, legs: uniq, bare, miss, fixed };
}
function crMakeLeg(id) {
  const parts = String(id).split("|");
  const gid = parts[0], kind = parts[1];
  const g = pbGame(gid);
  if (!g) return null;
  let pb = null, book = null;
  if (kind !== "pp") {
    const bp = typeof bestPriceFor === "function" ? bestPriceFor(id) : null;
    if (bp && bp.best) { book = bp.best.book; pb = pbLeg({ id, book }); }
  }
  pb = pb || pbLeg({ id });
  if (!pb || pb.started) return null;
  const leg = { id, gid: String(gid), g, kind, pb, value: pb.value, win: pb.win, label: pb.label, book: book || pb.priceSource, reason: "" };
  if (kind === "pp") {
    let p = null;
    try { p = nextPropRows().find((x) => String(x.id) === String(parts[2])); } catch (e) {}
    if (p) {
      const m = (marketsFor(p) || []).find((x) => x.key === parts[3]);
      leg.prop = p; leg.player = p.name;
      if (m) leg.lean = { m, line: pb.line, take: parts[4] === "over" ? "Over" : "Under" };
    }
  }
  return leg;
}
function createCheck(slip) {
  const notes = [];
  const ids = [];
  slip.legs.forEach((s) => {
    const l = crMakeLeg(s.id);
    if (!l) { notes.push(`I couldn't price "${s.seg}" right now: there's no line posted for it yet${s.player ? " (player prop prices post about a day before kickoff)" : ""}, or the game has started.`); return; }
    ids.push(s.id);
  });
  slip.miss.forEach((m) => notes.push(pbEsc(m.why)));
  const typed = {};
  slip.legs.forEach((s) => { if (s.userLine != null) typed[s.id] = s; });
  window.__crState = { check: true, ids, notes, typed, fixed: slip.fixed, res: { pool: [], tickets: [] } };
  createCheckRender();
}
function crBetter(t) {
  const out = { drops: [], swaps: [], pool: [] };
  const ev0 = t.x.r.ev, ids = t.bag.map((l) => l.id);
  if (ids.length >= 2) ids.forEach((id, k) => {
    const rest = ids.filter((_, j) => j !== k);
    const x = createPrice(rest);
    if (x && x.r.ev >= ev0 + 0.01) out.drops.push({ k, label: t.x.legs[k] ? t.x.legs[k].label : t.bag[k].label, x });
  });
  out.drops.sort((a, b) => b.x.r.ev - a.x.r.ev);
  t.bag.forEach((l, k) => {
    if (l.kind === "pp") return;
    if (t.bag.some((o, j) => j !== k && o.gid === l.gid)) return;   // never suggest a leg that fights another leg in the same game
    const mine = t.x.legs[k] || l.pb;
    let best = null;
    ["sp|home", "sp|away", "tot|over", "tot|under", "ml|home", "ml|away"].forEach((suffix) => {
      const id = l.gid + "|" + suffix;
      if (ids.includes(id)) return;
      const c = crMakeLeg(id);
      if (!c || c.value < mine.value + 0.015) return;
      if (c.kind === "ml" && !(c.pb.price >= -600 && c.pb.price <= 500)) return;
      const bag = ids.slice(); bag[k] = id;
      const x = createPrice(bag);
      if (!x || x.r.ev < ev0 + 0.01) return;
      if (!best || x.r.ev > best.x.r.ev) best = { k, c, x, mine };
    });
    if (best) { out.swaps.push(best); out.pool.push(best.c); }
  });
  out.swaps.sort((a, b) => b.x.r.ev - a.x.r.ev);
  return out;
}
function createCheckRender() {
  const out = document.getElementById("createOut");
  const st = window.__crState;
  if (!out || !st) return;
  window.__readyPriceCache = new Map();
  const legs = st.ids.map(crMakeLeg).filter(Boolean);
  const allNotes = (st.notes || []).slice();
  const fixedHtml = (st.fixed || []).length ? `<div class="cr-understood">${st.fixed.map(([a, b]) => `<span class="cr-chip fix">"${pbEsc(a)}" read as ${pbEsc(b)}</span>`).join("")}</div>` : "";
  const notesHtml0 = allNotes.length ? `<div class="cr-notes">${allNotes.map((n) => `<p>${n}</p>`).join("")}</div>` : "";
  if (!legs.length) { out.innerHTML = fixedHtml + notesHtml0 + `<div class="empty">Nothing left to check. Try a bet like "Bills -3, over 47.5".</div>`; return; }
  const x = createPrice(legs.map((l) => l.id));
  if (!x) { out.innerHTML = fixedHtml + notesHtml0 + `<div class="empty">No book has prices for all of those legs together right now.</div>`; return; }
  const t = { bag: legs, x, check: true };
  legs.forEach((l, k) => {
    const ty = st.typed && st.typed[l.id], pl = x.legs[k];
    if (ty && pl && pl.line != null && Math.abs(Number(pl.line) - ty.userLine) >= 0.25) allNotes.push(`You typed "${pbEsc(ty.seg)}". The line${x.book ? " at " + pbEsc(x.book) : ""} is <b>${pbEsc(pl.label)}</b> now, so that's what this is priced at.`);
  });
  const notesHtml = allNotes.length ? `<div class="cr-notes">${allNotes.map((n) => `<p>${n}</p>`).join("")}</div>` : "";
  const b = crBetter(t);
  st.res = { pool: b.pool, tickets: [t] };
  const r = x.r, n = legs.length, what = n === 1 ? "bet" : "ticket";
  const games = new Set(legs.map((l) => l.gid)).size;
  let take;
  if (r.ev >= 0.03) take = `<b class="cr-up">Bet it.</b> This ${what} is a good price${x.book ? " at " + pbEsc(x.book) : ""}: +${Math.round(r.ev * 100)}% value. It hits about ${pbPct(r.pAll)} of the time and the price only needs ${pbPct(r.breakEven)}.`;
  else if (r.ev >= -0.01) take = `<b>About fair.</b> The price is about right for how often this ${what} hits (${pbPct(r.pAll)}), so there's no real edge either way${b.drops.length || b.swaps.length ? "; the changes below make it better" : ""}.`;
  else take = `<b class="cr-down">Pass, or fix it.</b> The book has the edge on this ${what}: ${Math.round(r.ev * 100)}% value. It hits about ${pbPct(r.pAll)} of the time but the price needs ${pbPct(r.breakEven)}.`;
  if (games < n) take += ` Two or more legs are from the same game. Books price same-game parlays lower than this, so expect a smaller payout there.`;
  const fixes = [];
  b.drops.slice(0, 2).forEach((d) => fixes.push(`<li><span>Drop <b>${pbEsc(d.label)}</b>: the ticket becomes ${pbAm(d.x.r.american)}${d.x.book ? " at " + pbEsc(d.x.book) : ""} with ${(d.x.r.ev >= 0 ? "+" : "") + Math.round(d.x.r.ev * 100)}% value.</span><button type="button" data-crdrop="${d.k}">Drop it</button></li>`));
  b.swaps.slice(0, 3).forEach((w) => fixes.push(`<li><span>In ${pbEsc(w.c.g.short_name)}, <b>${pbEsc(w.c.label)}</b> ${pbAm(w.c.pb.price)} (${(w.c.value >= 0 ? "+" : "") + (w.c.value * 100).toFixed(1)}% value) is a better bet than your ${pbEsc(w.mine.label)} (${(w.mine.value >= 0 ? "+" : "") + (w.mine.value * 100).toFixed(1)}%). The ticket becomes ${pbAm(w.x.r.american)} with ${(w.x.r.ev >= 0 ? "+" : "") + Math.round(w.x.r.ev * 100)}% value.</span><button type="button" data-crswap="0|${w.k}|${pbEsc(w.c.id)}">Swap it in</button></li>`));
  const fixHtml = fixes.length ? `<div class="cr-fix"><div class="lbl">Make it better</div><ul>${fixes.join("")}</ul></div>` : (r.ev < 0.03 ? "" : "");
  out.innerHTML = crSearchBar() + fixedHtml + `<div class="cr-take">${take}</div>` + notesHtml + fixHtml + createTicketHtml(t, 0) +
    `<p class="subn cr-foot">Priced at the best current line across the books. To build new tickets instead, ask for something like "3 leg NFL parlay at +600".</p>`;
}
function crHedgeExample() {
  try {
    const now = Date.now();
    const gs = (DATA.games || []).filter((x) => x && !x.completed && x.league === "nfl" && x.odds && x.odds.home_spread != null && Date.parse(x.date) > now).sort((a, b) => Date.parse(a.date) - Date.parse(b.date));
    if (gs.length < 3) return "";
    const nm = (g) => (Number(g.odds.home_spread) <= 0 ? g.home : g.away).short;
    const last = gs[gs.length - 1], fav = Number(last.odds.home_spread) <= 0 ? last.home : last.away, ln = Number(last.odds.home_spread) <= 0 ? Number(last.odds.home_spread) : -Number(last.odds.home_spread);
    return `Hedge: ${nm(gs[0])} hit, ${nm(gs[1])} hit, ${fav.short} ${pbLine(ln)} left, $50 at +600`;
  } catch (e) { return ""; }
}
function crCompareExample() {
  try {
    const now = Date.now();
    const g = (DATA.games || []).filter((x) => x && !x.completed && x.league === "nfl" && x.odds && x.odds.home_spread != null && Date.parse(x.date) > now).sort((a, b) => Date.parse(a.date) - Date.parse(b.date))[1];
    if (!g) return "";
    const fav = Number(g.odds.home_spread) <= 0 ? g.home : g.away;
    const ln = Number(g.odds.home_spread) <= 0 ? Number(g.odds.home_spread) : -Number(g.odds.home_spread);
    return `${fav.short} ${pbLine(ln)} or ${fav.short} to win?`;
  } catch (e) { return ""; }
}
function crCheckExample() {
  try {
    const now = Date.now();
    const gs = (DATA.games || []).filter((g) => g && !g.completed && g.league === "nfl" && g.odds && g.odds.home_spread != null && g.odds.total != null && Date.parse(g.date) > now).sort((a, b) => Date.parse(a.date) - Date.parse(b.date)).slice(0, 2);
    if (gs.length < 2) return "";
    const a = gs[0], b = gs[1];
    const fav = Number(a.odds.home_spread) <= 0 ? a.home : a.away;
    const ln = Number(a.odds.home_spread) <= 0 ? Number(a.odds.home_spread) : -Number(a.odds.home_spread);
    return `${fav.short} ${pbLine(ln)}, ${b.home.short} game over ${pbTot(b.odds.total)}`;
  } catch (e) { return ""; }
}
// ---- compare: "Bills -3 or Bills to win?", "Henry over 85.5 or under", "Chiefs ML vs Chiefs -9.5" --
function crParseCompare(text) {
  let raw = String(text || "").replace(/\?/g, " ");
  raw = raw.replace(/^\s*(why|explain|compare|case for|the case for)\s+/i, "").replace(/^\s*(which|what|whats|what's|which one|which bet)\s+(is|would be|one is|s)?\s*(the )?(better|best|smarter|safer|stronger)\s*(bet|play|pick|option|choice)?\s*[:,-]?\s*/i, "")
    .replace(/^\s*(should i (take|bet|play|do)|compare|do i (take|want|like)|is it|better)\s+/i, "")
    .replace(/\s+(which (is|one is) (better|best)|whats better|what's better|which should i take|which one|or not)\s*$/i, "");
  const parts = raw.split(/\s+(?:or|vs\.?|versus|v\.)\s+/i).map((x) => x.trim()).filter(Boolean);
  if (parts.length !== 2 && parts.length !== 3) return null;
  const sides = parts.map((seg) => ({ seg, slip: crParseSlip(seg) }));
  // a bare "under" / "over 44" on one side is the other side's total or prop flipped
  sides.forEach((sd, i) => {
    if (sd.slip.legs.length) return;
    const m = crNorm(sd.seg).match(/^ (over|under|o|u|the over|the under) ?(\d{1,3}(?:\.\d+)?)? $/);
    if (!m) return;
    const other = sides.find((o, j) => j !== i && o.slip.legs.length === 1 && /\|(tot|pp)\|/.test(o.slip.legs[0].id));
    if (!other) return;
    const id = other.slip.legs[0].id.replace(/\|(over|under)$/, "|" + (/^(over|o|the over)$/.test(m[1]) ? "over" : "under"));
    sd.slip = { check: true, legs: [{ id, seg: sd.seg, userLine: m[2] != null ? Number(m[2]) : null, player: other.slip.legs[0].player }], bare: [], miss: [], fixed: [] };
  });
  // a bare team ("Bills") stands for its spread and its moneyline
  sides.forEach((sd) => {
    if (sd.slip.legs.length || sd.slip.bare.length !== 1) return;
    const t = crFindTeam(crNorm(sd.seg), sd.seg);
    if (!t || !t.t) return;
    sd.slip = { check: true, legs: [{ id: `${t.t.g.id}|sp|${t.t.side}`, seg: sd.seg }], bare: [], miss: [], fixed: t.fixed ? [t.fixed] : [], also: `${t.t.g.id}|ml|${t.t.side}` };
  });
  if (!sides.every((sd) => sd.slip.legs.length)) return null;
  const out = [];
  sides.forEach((sd) => { out.push({ seg: sd.seg, ids: sd.slip.legs.map((l) => l.id), typed: sd.slip.legs.filter((l) => l.userLine != null), fixed: sd.slip.fixed }); if (sd.slip.also) out.push({ seg: sd.seg + " to win", ids: [sd.slip.also], typed: [], fixed: [] }); });
  const seen = new Set();
  const uniq = out.filter((o) => { const k = o.ids.slice().sort().join("~"); if (seen.has(k)) return false; seen.add(k); return true; });
  return uniq.length >= 2 ? uniq.slice(0, 4) : null;
}
function createCompare(sides) {
  const out = document.getElementById("createOut");
  if (!out) return;
  window.__readyPriceCache = new Map();
  const cols = [], notes = [];
  sides.forEach((sd) => {
    const legs = sd.ids.map(crMakeLeg).filter(Boolean);
    if (legs.length !== sd.ids.length) { notes.push(`I couldn't price "${pbEsc(sd.seg)}" right now: no line is posted for it yet, or the game has started.`); return; }
    const x = createPrice(legs.map((l) => l.id));
    if (!x) { notes.push(`No book has a price for "${pbEsc(sd.seg)}" right now.`); return; }
    (sd.fixed || []).forEach(([a, b]) => notes.push(`I read "${pbEsc(a)}" as ${pbEsc(b)}.`));
    sd.typed.forEach((ty) => { const k = sd.ids.indexOf(ty.id); const pl = x.legs[k]; if (pl && pl.line != null && Math.abs(Number(pl.line) - ty.userLine) >= 0.25) notes.push(`You typed "${pbEsc(ty.seg)}". The line${x.book ? " at " + pbEsc(x.book) : ""} is <b>${pbEsc(pl.label)}</b> now, so that's what this is priced at.`); });
    cols.push({ seg: sd.seg, t: { bag: legs, x, check: true } });
  });
  window.__crState = { compare: true, ids: [], notes, res: { pool: [], tickets: [] } };
  if (cols.length < 2) { out.innerHTML = crSearchBar() + (notes.length ? `<div class="cr-notes">${notes.map((n) => `<p>${n}</p>`).join("")}</div>` : "") + `<div class="empty">I need two bets I can price to compare them. Try "Bills -3 or Bills to win".</div>`; return; }
  cols.sort((a, b) => b.t.x.r.ev - a.t.x.r.ev);
  window.__crState.res.tickets = cols.map((c) => c.t);
  const best = cols[0], next = cols[1];
  const r = (c) => c.t.x.r;
  const lbl = (c) => c.t.x.legs.map((l) => l.label).join(" + ");
  const gap = r(best).ev - r(next).ev;
  const sameSide = cols.every((c) => c.t.bag.length === 1 && c.t.bag[0].gid === best.t.bag[0].gid);
  const safest = cols.slice().sort((a, b) => r(b).pAll - r(a).pAll)[0];
  let verdict = `<b class="cr-up">Take ${pbEsc(lbl(best))}</b> at ${pbAm(r(best).american)}${best.t.x.book ? " (" + pbEsc(best.t.x.book) + ")" : ""}: ${(r(best).ev >= 0 ? "+" : "") + (r(best).ev * 100).toFixed(1)}% value against ${(r(next).ev >= 0 ? "+" : "") + (r(next).ev * 100).toFixed(1)}% for ${pbEsc(lbl(next))}.`;
  if (gap < 0.01) verdict = `<b>It's close.</b> ${pbEsc(lbl(best))} edges it, ${(r(best).ev >= 0 ? "+" : "") + (r(best).ev * 100).toFixed(1)}% value to ${(r(next).ev >= 0 ? "+" : "") + (r(next).ev * 100).toFixed(1)}% for ${pbEsc(lbl(next))}. ${safest !== best ? `${pbEsc(lbl(safest))} hits more often (${pbPct(r(safest).pAll)} vs ${pbPct(r(best).pAll)}), so take it if you'd rather cash more and win less.` : "It also hits more often, so it's the better bet both ways."}`;
  else if (safest !== best) verdict += ` ${pbEsc(lbl(safest))} hits more often (${pbPct(r(safest).pAll)} vs ${pbPct(r(best).pAll)}) but pays too little for it.`;
  else verdict += ` It also hits more often (${pbPct(r(best).pAll)} vs ${pbPct(r(next).pAll)}).`;
  if (r(best).ev < -0.01) verdict += ` Neither beats its price, so the honest answer is to pass on both; if you're betting one anyway, this is the one.`;
  const row = (name, f) => `<tr><th scope="row">${name}</th>${cols.map((c, i) => `<td class="${i === 0 ? "win" : ""}">${f(c, i)}</td>`).join("")}</tr>`;
  const table = `<div class="cr-cmp-wrap"><table class="cr-cmp">
    <thead><tr><th></th>${cols.map((c, i) => `<th class="${i === 0 ? "win" : ""}">${i === 0 ? "<em>Better bet</em>" : ""}${pbEsc(lbl(c))}</th>`).join("")}</tr></thead>
    <tbody>
      ${row("Price", (c) => `<b>${pbAm(r(c).american)}</b>${c.t.x.book ? `<small>${pbEsc(c.t.x.book)}</small>` : ""}`)}
      ${row("$10 pays", (c) => pbMoney(10 * r(c).decEff))}
      ${row("Our chance", (c) => `<b>${pbPct(r(c).pAll)}</b><small>books' ${pbPct(c.t.x.legs.reduce((a, l) => a * (l.bookWin || 0), 1))}</small>`)}
      ${row("Price needs", (c) => pbPct(r(c).breakEven))}
      ${row("Value", (c) => `<b class="${r(c).ev >= 0.005 ? "cr-up" : r(c).ev <= -0.01 ? "cr-down" : ""}">${(r(c).ev >= 0 ? "+" : "") + (r(c).ev * 100).toFixed(1)}%</b>`)}
      ${row("Bet size", (c) => unitsText(kellyUnits(r(c).pAll, null, { dec: r(c).decEff, cap: c.t.bag.length > 1 ? 1 : 2 })))}
      ${row("To cash", (c) => c.t.bag.map((l, k) => pbEsc(crNeeds(l, c.t.x.legs[k] || l.pb))).join("<br>"))}
    </tbody></table></div>`;
  const notesHtml = notes.length ? `<div class="cr-notes">${notes.map((n) => `<p>${n}</p>`).join("")}</div>` : "";
  const corr = sameSide ? `<p class="subn">Both ride the same game, so they win and lose together most of the time. The one with more value is the better single bet; don't play both.</p>` : "";
  out.innerHTML = crSearchBar() + `<div class="cr-understood"><span class="subn">Comparing:</span> ${cols.map((c) => `<span class="cr-chip">${pbEsc(lbl(c))}</span>`).join("")}</div>` + notesHtml + `<div class="cr-take">${verdict}</div>` + table + corr +
    cols.map((c, i) => createTicketHtml(Object.assign(c.t, { cmpTitle: i === 0 ? "Better bet" : "The other one" }), i)).join("") +
    `<p class="subn cr-foot">Priced at the best current line across the books. Value is our checked chance against the price; it's the number that decides, because a bet that hits more often can still pay too little.</p>`;
}
// ---- hedge: "hedge Bills, Lions hit, Chiefs -9.5 tonight, $50 at +600" ------------------------
function crFlipId(id) {
  return String(id).replace(/\|(home|away|over|under)$/, (m0, sd) => "|" + ({ home: "away", away: "home", over: "under", under: "over" })[sd]);
}
function crParseHedge(text) {
  let raw = String(text || "").replace(/\?/g, " ").replace(/\s+/g, " ").trim();
  const low = " " + raw.toLowerCase() + " ";
  const kw = / (hedge|hedging|hedge it|lock in|lock up|lock it in|cash out|cashout|guarantee|insure) /.test(low);
  const hitSeg = /(hit|hits|won|cashed|came in|covered|good|in the books|✓)/i, leftSeg = /(left|tonight|remaining|still|pending|open|to go|last leg|last|live|not yet|tbd|later|tomorrow|sunday|monday|thursday|saturday)/i;
  if (!kw && !(hitSeg.test(raw) && leftSeg.test(raw))) return null;
  const out = { stake: null, payout: null, odds: null, hit: [], left: [], miss: [], notes: [], live: null };
  let m;
  // "live Jets +3.5 -110", "live line: under 41 -105", "live KC ML -400", "Jets live +3.5 at -110"
  const lm = raw.match(/(?:^|[\s,;])(?:live|in[- ]game|right now|now)\s*(?:line|odds|price|is|at)?\s*[:-]?\s*([^,;]+?)(?=\s*(?:,|;|$))/i) || raw.match(/(?:^|[\s,;])([a-z][a-z .'&]*?)\s+live\s+([^,;]+?)(?=\s*(?:,|;|$))/i);
  if (lm) {
    const seg = lm.length > 2 ? (lm[1] + " " + lm[2]) : lm[1];
    let txt = seg.replace(/\b(line|odds|price|at)\b/gi, " ");
    let price = null;
    const pm = txt.match(/(?:^|\s)([+-]\d{3,5})(?=\s|$)/);
    if (pm) { price = Number(pm[1]); txt = txt.replace(pm[0], " "); }
    const ls = crParseSlip(txt.replace(/\s+/g, " ").trim());
    let lg = ls.legs[0];
    if (!lg && ls.bare.length === 1) { const t = crFindTeam(crNorm(txt), txt); if (t && t.t) lg = { id: `${t.t.g.id}|ml|${t.t.side}`, seg: txt }; }
    if (lg && (price != null || lg.userLine != null)) { out.live = { id: lg.id, line: lg.userLine != null ? lg.userLine : null, price, seg: seg.trim() }; raw = raw.replace(lm[0], " "); }
  }
  if ((m = raw.match(/\$\s?(\d+(?:\.\d+)?)\s*(?:to win|wins|to make|for a shot at)\s*\$?\s?(\d+(?:\.\d+)?)/i))) { out.stake = Number(m[1]); out.payout = Number(m[1]) + Number(m[2]); raw = raw.replace(m[0], " "); }
  else if ((m = raw.match(/(?:pays|paying|payout of|payout|returns|would pay|collect)\s*\$?\s?(\d+(?:\.\d+)?)/i))) { out.payout = Number(m[1]); raw = raw.replace(m[0], " "); }
  if ((m = raw.match(/\$\s?(\d+(?:\.\d+)?)/))) { if (out.stake == null) out.stake = Number(m[1]); raw = raw.replace(m[0], " "); }
  if ((m = raw.match(/(?:^|\s)(?:at\s+)?([+-]\d{3,5})(?=\s|$|,)/))) { out.odds = Number(m[1]); raw = raw.replace(m[0], " "); }
  if (out.stake != null && out.payout == null && out.odds != null) out.payout = out.stake * pbDec(out.odds);
  if (out.stake == null && out.payout != null && out.odds != null) out.stake = out.payout / pbDec(out.odds);
  raw = raw.replace(/^\s*(hedge|hedging|lock in|lock up|lock it in|cash out|cashout|guarantee|insure)\s*(my|this|the|a)?\s*(parlay|ticket|bet|slip)?\s*[:,-]?\s*/i, "").replace(/\s+(hedge|hedge it|lock in|lock it in|cash out)\s*$/i, "");
  const segs = raw.split(/\s*(?:,|;|\n|\s\+\s|\s&\s|\sand\s|\splus\s|\swith\s|\salso\s|\sthen\s)\s*/i).map((x) => x.trim()).filter(Boolean);
  const parsed = segs.map((seg) => {
    const isHit = hitSeg.test(seg) && !/not hit|hasnt hit|hasn't hit/i.test(seg);
    const isLeft = leftSeg.test(seg) && !isHit;
    const clean = seg.replace(/\b(hit|hits|won|cashed|came in|covered|good|in the books|left|tonight|remaining|still|pending|open|to go|last leg|last|live|not yet|tbd|later|already|is|are|has|have|the|my|parlay|ticket|leg|legs|needs|need|just|only)\b/gi, " ").replace(/\s+/g, " ").trim();
    return { seg, clean, isHit, isLeft };
  });
  const anyMarked = parsed.some((x) => x.isHit || x.isLeft);
  parsed.forEach((x, i) => {
    if (!x.clean) return;
    const slip = crParseSlip(x.clean);
    let leg = slip.legs[0] || null;
    if (!leg && slip.bare.length === 1) { const t = crFindTeam(crNorm(x.clean), x.clean); if (t && t.t) leg = { id: `${t.t.g.id}|sp|${t.t.side}`, seg: x.clean, bare: true }; }
    // an unmarked leg: "Bills, Lions hit" means both hit; one after the last marker is the open one
    let left;
    if (x.isLeft) left = true;
    else if (x.isHit) left = false;
    else if (!anyMarked) left = i === parsed.length - 1;
    else { const next = parsed.slice(i + 1).find((y) => y.isHit || y.isLeft); left = !next; }
    if (!leg) { if (left) out.miss.push(x.seg); return; }
    (left ? out.left : out.hit).push(Object.assign(leg, { seg: x.seg }));
  });
  return out;
}
function crHedgeFromSaved(h) {
  // a saved ticket with these open legs fills in the stake and the payout
  try {
    const leftIds = new Set(h.left.map((l) => l.id.replace(/\|[^|]+$/, "")));
    const hit = mbLoad().filter((t) => t.src && (t.legs || []).some((lg) => leftIds.has(String(lg.id || "").replace(/\|[^|]+$/, "")) && !lg.result));
    const t = hit.sort((a, b) => String(b.at).localeCompare(String(a.at)))[0];
    if (!t || t.price == null) return null;
    return { stake: t.stake, payout: t.stake * pbDec(t.price), legs: t.legs };
  } catch (e) { return null; }
}
// inverse of the standard normal CDF (Acklam), for turning a win chance into an expected margin
function crInvNorm(p) {
  p = Math.min(0.9999, Math.max(0.0001, p));
  const a = [-39.69683028665376, 220.9460984245205, -275.9285104469687, 138.357751867269, -30.66479806614716, 2.506628277459239];
  const b = [-54.47609879822406, 161.5858368580409, -155.6989798598866, 66.80131188771972, -13.28068155288572];
  const c = [-0.007784894002430293, -0.3223964580411365, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783];
  const d = [0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416];
  const q0 = 0.02425;
  if (p < q0) { const q = Math.sqrt(-2 * Math.log(p)); return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
  if (p > 1 - q0) { const q = Math.sqrt(-2 * Math.log(1 - p)); return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
  const q = p - 0.5, r = q * q;
  return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
}
// Live state of a game from ESPN, read in the visitor's browser (no credits): score, clock,
// ESPN's win probability, and any live lines ESPN shows. Cached 45 seconds per game.
async function crLiveState(g) {
  const memo = crLiveState.m || (crLiveState.m = new Map());
  const hit = memo.get(String(g.id));
  if (hit && Date.now() - hit.at < 45000) return hit.v;
  const sport = g.league === "nfl" ? "nfl" : "college-football";
  const v = { ok: false, state: null, period: null, clock: null, home: null, away: null, wpHome: null, odds: null, at: Date.now() };
  try {
    const sm = await getJSON(`https://site.web.api.espn.com/apis/site/v2/sports/football/${sport}/summary?event=${g.id}`);
    const comp = ((sm.header || {}).competitions || [])[0] || {};
    const st = comp.status || (sm.header || {}).status || {};
    v.state = ((st.type || {}).state) || null;
    v.period = st.period != null ? Number(st.period) : null;
    v.clock = st.displayClock || null;
    v.detail = (st.type || {}).shortDetail || (st.type || {}).detail || "";
    (comp.competitors || []).forEach((c) => { if (c.homeAway === "home") v.home = Number(c.score); else if (c.homeAway === "away") v.away = Number(c.score); });
    const wp = sm.winprobability || [];
    if (wp.length && wp[wp.length - 1].homeWinPercentage != null) v.wpHome = Number(wp[wp.length - 1].homeWinPercentage);
    const pc = (sm.pickcenter || [])[0];
    if (pc) v.odds = crReadEspnOdds(pc, "ESPN");
    v.ok = true;
  } catch (e) {}
  if (g.league === "nfl" || g.league === "cfb") {
    try {
      const lg = g.league === "nfl" ? "nfl" : "college-football";
      const d = await getJSON(`https://sports.core.api.espn.com/v2/sports/football/leagues/${lg}/events/${g.id}/competitions/${g.id}/odds?limit=20`);
      const items = (d.items || []).slice();
      items.sort((a, b) => (/live/i.test(((b.provider || {}).name || "")) ? 1 : 0) - (/live/i.test(((a.provider || {}).name || "")) ? 1 : 0));
      for (const it of items) { const o = crReadEspnOdds(it, ((it.provider || {}).name) || "ESPN"); if (o && (o.homeSpread != null || o.homeMl != null || o.total != null)) { v.odds = o; break; } }
    } catch (e) {}
  }
  memo.set(String(g.id), { at: Date.now(), v });
  return v;
}
function crReadEspnOdds(it, name) {
  const num = (x) => { if (x == null) return null; if (typeof x === "object") x = x.american != null ? x.american : x.value; const n = pbParseAmerican ? pbParseAmerican(x) : Number(x); return Number.isFinite(n) ? n : null; };
  const H = it.homeTeamOdds || {}, A = it.awayTeamOdds || {};
  const Hc = H.current || {}, Ac = A.current || {}, C = it.current || {};
  let hs = null;
  if (Hc.pointSpread && Hc.pointSpread.american != null) hs = Number(String(Hc.pointSpread.american).replace("PK", "0"));
  else if (it.spread != null) hs = H.favorite ? -Math.abs(Number(it.spread)) : A.favorite ? Math.abs(Number(it.spread)) : Number(it.spread);
  const o = {
    book: name,
    homeSpread: Number.isFinite(hs) ? hs : null,
    homeSpreadPrice: num(Hc.spread) != null ? num(Hc.spread) : num(H.spreadOdds),
    awaySpreadPrice: num(Ac.spread) != null ? num(Ac.spread) : num(A.spreadOdds),
    homeMl: num(Hc.moneyLine) != null ? num(Hc.moneyLine) : num(H.moneyLine),
    awayMl: num(Ac.moneyLine) != null ? num(Ac.moneyLine) : num(A.moneyLine),
    total: C.total && C.total.american != null ? Number(String(C.total.american).replace(/[ou]/i, "")) : it.overUnder != null ? Number(it.overUnder) : null,
    overPrice: num(C.over) != null ? num(C.over) : num(it.overOdds),
    underPrice: num(C.under) != null ? num(C.under) : num(it.underOdds)
  };
  return o;
}
function crClockFrac(ls, league) {
  // share of regulation left (0..1); overtime counts as a sliver
  if (!ls || ls.state !== "in" || !ls.period) return null;
  const m = String(ls.clock || "0:00").match(/(\d+):(\d+)/);
  const left = m ? Number(m[1]) + Number(m[2]) / 60 : 0;
  if (ls.period > 4) return 0.05;
  return Math.max(0.02, ((4 - ls.period) * 15 + left) / 60);
}
// the hedge on the leg's other side: from a typed live line, ESPN's live line, or the best
// pre-game price; and the distribution of the leg's final number that decides both bets
async function createHedge(h) {
  const out = document.getElementById("createOut");
  if (!out) return;
  const token = (createHedge.n = (createHedge.n || 0) + 1);
  window.__readyPriceCache = new Map();
  const notes = [];
  h.miss.forEach((m) => notes.push(`I couldn't tell which bet "${pbEsc(m)}" is.`));
  const saved = (h.stake == null || h.payout == null) && h.left.length ? crHedgeFromSaved(h) : null;
  if (saved) { if (h.stake == null) h.stake = saved.stake; if (h.payout == null) h.payout = saved.payout; notes.push(`Stake and payout taken from your saved ticket in My bets (${pbMoney(saved.stake)} to collect ${pbMoney(saved.payout)}).`); }
  window.__crState = { hedge: true, ids: [], notes, res: { pool: [], tickets: [] } };
  const notesHtml = () => notes.length ? `<div class="cr-notes">${notes.map((n) => `<p>${n}</p>`).join("")}</div>` : "";
  const lbl = (id, fb) => { const pb = pbLeg({ id }); return pb ? pb.label : fb; };
  const head = `<div class="cr-understood"><span class="subn">Hedging:</span> ${h.hit.map((l) => `<span class="cr-chip">${pbEsc(lbl(l.id, l.seg))} ✓</span>`).join("")}${h.left.map((l) => `<span class="cr-chip warn">${pbEsc(lbl(l.id, l.seg))} left</span>`).join("")}${h.stake != null ? `<span class="cr-chip">${pbMoney(h.stake)} risked</span>` : ""}${h.payout != null ? `<span class="cr-chip">collects ${pbMoney(h.payout)}</span>` : ""}${h.live ? `<span class="cr-chip fix">live: ${pbEsc(h.live.seg)}</span>` : ""}</div>`;
  if (!h.left.length) { out.innerHTML = crSearchBar() + head + notesHtml() + `<div class="empty">Which leg is still open? Mark it with "left" or "tonight", like "Bills hit, Lions hit, Chiefs -9.5 tonight".</div>`; return; }
  if (h.left.length > 1) { out.innerHTML = crSearchBar() + head + notesHtml() + `<div class="cr-take"><b>Wait for one leg.</b> A clean hedge needs exactly one leg left; you have ${h.left.length} open (${h.left.map((l) => pbEsc(lbl(l.id, l.seg))).join(", ")}). Betting against one of them now doesn't lock anything, because the others can still lose. Come back when one is left and ask again with the stake and the odds, like "hedge Chiefs -9.5 left, $50 at +600".</div>`; return; }
  if (h.stake == null || h.payout == null) { out.innerHTML = crSearchBar() + head + notesHtml() + `<div class="cr-take"><b>I need two numbers:</b> what you risked and what the ticket collects if the last leg hits. Add them like <b>"$50 at +600"</b> or <b>"$50 to win $300"</b>. If you saved the ticket in My bets I'll read them from there.</div>`; return; }
  const legId = h.left[0].id;
  const parts = legId.split("|"), kind = parts[1], side = parts[parts.length - 1];
  const g = pbGame(parts[0]);
  if (!g || kind === "pp") { out.innerHTML = crSearchBar() + head + notesHtml() + `<div class="empty">${kind === "pp" ? "Player prop hedges aren't supported yet: there's no live prop line to price the other side." : "I couldn't find that game."}</div>`; return; }
  // the leg as you have it (your number if you typed one)
  let legPb = h.left[0].userLine != null && kind !== "ml" ? pbLeg({ id: legId, line: h.left[0].userLine }) : null;
  legPb = legPb || pbLeg({ id: legId });
  if (!legPb) { out.innerHTML = crSearchBar() + head + notesHtml() + `<div class="empty">That game has no line posted, so I can't price it.</div>`; return; }
  const started = Date.parse(g.date) <= Date.now() || legPb.started;
  const team = side === "home" ? g.home : side === "away" ? g.away : null, oppTeam = side === "home" ? g.away : side === "away" ? g.home : null;
  // live state (only matters once the game is on)
  let ls = null;
  if (started) {
    out.innerHTML = crSearchBar() + head + notesHtml() + `<div class="cr-take">Checking ESPN for the live score and line…</div>`;
    try { ls = await crLiveState(g); } catch (e) { ls = null; }
    if (token !== createHedge.n) return;
    if (ls && ls.state === "post") { out.innerHTML = crSearchBar() + head + notesHtml() + `<div class="cr-take"><b>That game is over</b>${ls.home != null ? ` (${pbEsc(g.away.abbr)} ${ls.away}, ${pbEsc(g.home.abbr)} ${ls.home})` : ""}, so there's nothing left to hedge.</div>`; return; }
  }
  const live = started && ls && ls.state === "in";
  // the hedge's line and price
  const opSide = ({ home: "away", away: "home", over: "under", under: "over" })[side];
  const opId = crFlipId(legId);
  const legLine = kind === "ml" ? 0 : Number(legPb.line);
  let hLine = null, hPrice = null, hBook = null, src = "", estimated = false;
  if (h.live) {
    const lp = h.live.id.split("|"), lSide = lp[lp.length - 1], lKind = lp[1];
    if (lp[0] !== String(g.id) || lKind !== kind) notes.push(`The live line you typed ("${pbEsc(h.live.seg)}") isn't for this leg's market, so I left it out.`);
    else {
      const same = lSide === side;
      let ln = h.live.line, pr = h.live.price;
      if (pr == null) pr = -110;
      if (same) {
        // you typed your own side's live line: the other side is the mirror, at an estimated price
        if (kind === "sp" && ln != null) ln = -ln;
        const dOpp = 1 / Math.max(0.05, 1.045 - 1 / pbDec(pr));
        pr = pbAmerican(dOpp); estimated = true;
        notes.push(`You typed your own side's live line, so the other side's price (${pbAm(pr)}) is an estimate from it. Check your app for the real number.`);
      }
      hLine = kind === "ml" ? 0 : ln; hPrice = pr; hBook = "your book"; src = "the live line you typed";
    }
  }
  if (hPrice == null && live && ls.odds) {
    const o = ls.odds;
    if (kind === "ml") { const pr = opSide === "home" ? o.homeMl : o.awayMl; if (pr != null) { hLine = 0; hPrice = pr; } }
    else if (kind === "sp" && o.homeSpread != null) { hLine = opSide === "home" ? o.homeSpread : -o.homeSpread; hPrice = (opSide === "home" ? o.homeSpreadPrice : o.awaySpreadPrice) || -110; }
    else if (kind === "tot" && o.total != null) { hLine = o.total; hPrice = (opSide === "over" ? o.overPrice : o.underPrice) || -110; }
    if (hPrice != null) { hBook = o.book; src = `ESPN's live line${o.book && o.book !== "ESPN" ? " (" + pbEsc(o.book) + ")" : ""}, as of ${new Date(ls.at).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}`; }
  }
  if (hPrice == null && !started) {
    const opp = crMakeLeg(opId);
    if (opp) {
      let op = opp.pb, book = opp.book && !/standard|typical|estimated/.test(opp.book) ? opp.book : null;
      const bp0 = typeof bestPriceFor === "function" ? bestPriceFor(opId) : null;
      if (bp0 && bp0.rows && kind !== "ml") {
        const want = kind === "sp" ? -legLine : legLine;
        const sameL = bp0.rows.filter((r) => r.line != null && Math.abs(Number(r.line) - want) < 0.01).sort((a, b) => pbDec(b.price) - pbDec(a.price));
        if (sameL.length) { const at = pbLeg({ id: opId, book: sameL[0].book }); if (at && !at.started) { op = at; book = sameL[0].book; } }
      }
      hLine = kind === "ml" ? 0 : Number(op.line); hPrice = op.price; hBook = book; src = "the best pre-game price";
    }
  }
  if (hPrice == null) {
    const ex = kind === "ml" ? `live ${oppTeam.short} ML +250` : kind === "sp" ? `live ${oppTeam.short} ${pbLine(-legLine)} -110` : `live ${opSide} ${pbTot(legLine)} -110`;
    out.innerHTML = crSearchBar() + head + notesHtml() + `<div class="cr-take"><b>${started ? "This game is on, and I need the live line." : "I couldn't find a price for the other side."}</b> ${live ? `ESPN ${ls.odds ? "doesn't show a live line for it right now" : "isn't showing live odds for this game"}. ` : started && (!ls || !ls.ok) ? "I couldn't reach ESPN for the live score and line just now. " : ""}Add the price from your sportsbook app for the other side, like <b>"${pbEsc(ex)}"</b>, and ask again.${live && ls.home != null ? `<br><br>Right now: ${pbEsc(g.away.abbr)} ${ls.away}, ${pbEsc(g.home.abbr)} ${ls.home}, ${pbEsc(ls.detail || "")}.` : ""}</div>`;
    return;
  }
  // the leg's final number (team margin for sides, combined points for totals): a normal curve
  const nfl = g.league === "nfl";
  let mu, sigma, chanceSrc;
  const frac = live ? crClockFrac(ls, g.league) : 1;
  if (kind === "tot") {
    sigma = (nfl ? 13 : 16) * Math.sqrt(frac);
    const pts = live && ls.home != null ? ls.home + ls.away : 0;
    if (live && ls.odds && ls.odds.total != null) { mu = ls.odds.total; chanceSrc = `ESPN's live total of ${pbTot(ls.odds.total)}`; }
    else if (live) { const pre = Number((g.odds || {}).total) || (nfl ? 44 : 52); mu = pts + pre * frac; chanceSrc = `the score so far plus the pre-game scoring pace for the time left`; }
    else { mu = legLine + (side === "over" ? 1 : -1) * sigma * crInvNorm(legPb.win); chanceSrc = "our checked chance"; }
  } else {
    sigma = (nfl ? 13.4 : 16) * Math.sqrt(frac);
    const cm = live && ls.home != null ? (side === "home" ? ls.home - ls.away : ls.away - ls.home) : 0;
    if (live && ls.wpHome != null) {
      const wp = side === "home" ? ls.wpHome : 1 - ls.wpHome;
      mu = sigma * crInvNorm(wp);
      chanceSrc = `ESPN's live win probability (${Math.round(wp * 100)}% for ${pbEsc(team.abbr)})`;
    } else if (live && ls.odds && ls.odds.homeSpread != null) { mu = -(side === "home" ? ls.odds.homeSpread : -ls.odds.homeSpread); chanceSrc = `ESPN's live spread`; }
    else if (live) { mu = cm; chanceSrc = "the current score"; }
    else { const a0 = kind === "ml" ? 0 : -legLine; mu = a0 + sigma * crInvNorm(legPb.win); chanceSrc = "our checked chance"; }
  }
  const P = (x) => normCdf(x);
  // leg wins when the number clears a, hedge wins when it stays under b (in the leg side's terms)
  let a, b;
  if (kind === "tot") { if (side === "over") { a = legLine; b = Number(hLine); } else { a = -legLine; b = -Number(hLine); mu = -mu; } }
  else { a = kind === "ml" ? 0 : -legLine; b = kind === "ml" ? 0 : Number(hLine); }
  const pLeg = 1 - P((a - mu) / sigma), pHedge = P((b - mu) / sigma);
  const pBoth = b > a ? Math.max(0, P((b - mu) / sigma) - P((a - mu) / sigma)) : 0;
  const pNone = a > b ? Math.max(0, P((a - mu) / sigma) - P((b - mu) / sigma)) : 0;
  const S = h.stake, Pay = h.payout, d = pbDec(hPrice);
  const full = Pay / d, lockAmt = Pay - S - full;
  const outc = (H) => ({ legOnly: Pay - S - H, hedgeOnly: H * (d - 1) - S, both: Pay - S + H * (d - 1), none: -S - H });
  const evOf = (H) => { const o = outc(H); return (pLeg - pBoth) * o.legOnly + (pHedge - pBoth) * o.hedgeOnly + pBoth * o.both + pNone * o.none; };
  const rows = [0, 0.25, 0.5, 0.75, 1].map((f) => { const H = full * f; return Object.assign({ f, H, ev: evOf(H) }, outc(H)); });
  const hLabel = kind === "ml" ? `${oppTeam.abbr} to win` : kind === "sp" ? `${oppTeam.abbr} ${pbLine(Number(hLine))}` : `${opSide === "over" ? "Over" : "Under"} ${pbTot(hLine)}`;
  const legLabel = legPb.label;
  const gap = kind !== "ml" && Math.abs(a - b) >= 0.25;
  const unit = kind === "tot" ? "points" : "";
  const legName = team ? team.short : "the game";
  const fmtRange = () => {
    if (kind === "tot") { const lo = Math.min(a, b), hi = Math.max(a, b); const L = side === "over" ? [lo, hi] : [-hi, -lo]; return `${Math.floor(L[0]) + 1} to ${Math.ceil(L[1]) - 1} total points`; }
    const lo = Math.min(a, b), hi = Math.max(a, b);
    const f = (x) => x >= 0 ? `win by ${x}` : `lose by ${-x}`;
    const L = Math.floor(lo) + 1, H2 = Math.ceil(hi) - 1;
    if (L === H2) return `the ${legName} ${f(L)}`;
    if (L > 0) return `the ${legName} win by ${L} to ${H2}`;
    if (H2 < 0) return `the ${legName} lose by ${-H2} to ${-L}`;
    return `the final margin lands between the ${legName} losing by ${-L} and winning by ${H2}`;
  };
  let take;
  const pLegTxt = `${Math.round(pLeg * 100)}%`;
  if (lockAmt > 0) {
    take = `<b class="cr-up">Bet ${pbMoney(full)} on ${pbEsc(hLabel)}</b> at ${pbAm(hPrice)}${hBook ? " (" + pbEsc(hBook) + ")" : ""} and you're up <b>${pbMoney(lockAmt)}</b> ${gap ? "if one of the two wins" : "no matter what"}.`;
    if (pBoth > 0.005) take += ` There's also a <b>middle</b>: if ${pbEsc(fmtRange())}, <b>both win</b> and you're up ${pbMoney(outc(full).both)} (about ${Math.round(pBoth * 100)}% of the time).`;
    if (pNone > 0.005) take += ` <b>Watch the gap:</b> if ${pbEsc(fmtRange())}, <b>both lose</b> and you're down ${pbMoney(S + full)} (about ${Math.round(pNone * 100)}% of the time), so the lock isn't a lock. Get the hedge at ${kind === "sp" ? pbEsc(oppTeam.abbr + " " + pbLine(legLine * -1)) : pbTot(legLine)} if a book has it.`;
    const ride = rows[0].ev, hedged = rows[4].ev;
    if (ride > hedged + Math.max(5, Math.abs(hedged) * 0.5)) take += pNone > 0.05 ? `<br><br>At this number the hedge isn't worth it: <b>riding averages ${pbMoney(ride)}</b> against ${pbMoney(hedged)} hedged, because of the gap. A hedge line closer to yours fixes that; check other books.` : `<br><br>By the numbers, <b>letting it ride is worth more on average</b> (${pbMoney(ride)} vs ${pbMoney(hedged)}), with ${pbEsc(legLabel)} at ${pLegTxt}. Ride it if ${pbMoney(S)} isn't money you'd miss; hedge or half-hedge if you'd rather bank it.`;
    else if (ride > hedged) take += `<br><br>Letting it ride averages ${pbMoney(ride)}, only a little more than hedging (${pbMoney(hedged)}), so the hedge is the sensible play unless you like the sweat.`;
    else take += `<br><br>${pLeg < 0.5 ? `With ${pbEsc(legLabel)} at only ${pLegTxt}, hedging` : `Even with ${pbEsc(legLabel)} at ${pLegTxt}, the hedge price is good enough that hedging`} (${pbMoney(hedged)} on average) beats riding it (${pbMoney(ride)}). <b>Hedge it.</b>`;
  } else {
    take = `<b class="cr-down">There's no profit to lock.</b> ${pbEsc(hLabel)} at ${pbAm(hPrice)} pays too little against a ${pbMoney(Pay)} payout: a full hedge of ${pbMoney(full)} guarantees a <b>loss of ${pbMoney(-lockAmt)}</b> either way. Your real choices are to let it ride (${pLegTxt} to collect ${pbMoney(Pay)}, worth ${pbMoney(rows[0].ev)} on average) or hedge part of it to shrink the worst case.`;
  }
  if (kind !== "ml" && Number.isInteger(Number(hLine)) && Number.isInteger(legLine) && Math.abs(a - b) < 0.01) take += `<br><br><small>If it lands exactly on the number, both bets push and you get your stakes back.</small>`;
  const liveBox = live ? `<div class="cr-live-box"><b>Live</b> ${pbEsc(g.away.abbr)} ${ls.away != null ? ls.away : "–"}, ${pbEsc(g.home.abbr)} ${ls.home != null ? ls.home : "–"} · ${pbEsc(ls.detail || ("Q" + ls.period + " " + (ls.clock || "")))}${ls.wpHome != null ? ` · ESPN win chance: ${pbEsc(g.home.abbr)} ${Math.round(ls.wpHome * 100)}%` : ""}<button type="button" class="cr-act" data-crrelive="1">Update</button></div>` : "";
  const srcLine = `<p class="subn">Hedge price from ${src}${estimated ? " (estimated)" : ""}. The chance of ${pbEsc(legLabel)} (${pLegTxt}) comes from ${chanceSrc}${live ? ", with the spread of outcomes narrowing as the clock runs" : ""}.${live && !h.live ? ` For your book's exact price, add it like "live ${pbEsc(hLabel)} ${pbAm(hPrice)}".` : ""}</p>`;
  const cols = gap ? ["If only your leg wins", pBoth > 0 ? "If both win" : "If both lose", "If only the hedge wins"] : [`If ${pbEsc(legLabel)} hits`, "If it misses"];
  const table = `<div class="cr-cmp-wrap"><table class="cr-cmp cr-hedge">
    <thead><tr><th>Hedge</th><th>Bet on ${pbEsc(hLabel)}</th>${cols.map((c) => `<th>${c}</th>`).join("")}<th>Average</th></tr></thead>
    <tbody>${rows.map((r) => {
      const cells = gap ? [r.legOnly, pBoth > 0 ? r.both : r.none, r.hedgeOnly] : [r.legOnly, r.hedgeOnly];
      return `<tr><th scope="row">${r.f === 0 ? "None" : r.f === 1 ? "Full" : Math.round(r.f * 100) + "%"}</th><td>${r.H ? pbMoney(r.H) : "—"}</td>${cells.map((v) => `<td class="${v >= 0 ? "cr-up" : "cr-down"}">${v >= 0 ? "+" : ""}${pbMoney(v)}</td>`).join("")}<td>${r.ev >= 0 ? "+" : ""}${pbMoney(r.ev)}</td></tr>`;
    }).join("")}</tbody></table></div>
    <p class="subn">Profit after everything settles, counting the ${pbMoney(S)} already risked.</p>`;
  const books = !started ? (() => { const bp = typeof bestPriceFor === "function" ? bestPriceFor(opId) : null; return bp && bp.rows && bp.rows.length > 1 ? `<div class="cr-books"><span class="lbl">The other side at each book</span>${bp.rows.slice(0, 6).map((r, k) => `<span class="${k === 0 ? "best" : ""}">${pbEsc(r.book)} <b>${r.line != null && kind !== "ml" ? pbLine(r.line) + " " : ""}${pbAm(r.price)}</b></span>`).join("")}<span class="subn">A better price shrinks the hedge and grows the lock.</span></div>` : ""; })() : "";
  const hedgeCard = `<article class="parlay-card ready cr-ticket">
    <div class="td-mkt">The hedge${live ? " · live" : ""}</div>
    <div class="cr-leg-top"><b class="cr-ex-label">${pbEsc(hLabel)}</b><span class="cr-px">${pbAm(hPrice)}${hBook ? " <small>" + pbEsc(hBook) + "</small>" : ""}</span></div>
    <div class="subn">${lockAmt > 0 ? `Bet <b>${pbMoney(full)}</b> to lock ${pbMoney(lockAmt)}, or <b>${pbMoney(full / 2)}</b> for a half hedge (${pbMoney(rows[2].legOnly)} if your leg hits, ${pbMoney(rows[2].hedgeOnly)} if it misses).` : `A full hedge is ${pbMoney(full)} and locks a loss of ${pbMoney(-lockAmt)}.`}</div>
    ${books}
    <div class="cr-actions"><button type="button" class="cr-act" data-crshare="${pbEsc("q=" + encodeURIComponent(String((document.getElementById("createInput") || {}).value || "").trim()))}">Share</button>${live ? `<button type="button" class="cr-act" data-crrelive="1">Update live</button>` : ""}</div>
  </article>`;
  let legCard = "";
  if (!started) {
    const leg = crMakeLeg(legId);
    if (leg) { const facts = crLegFacts(leg, legPb); legCard = `<article class="parlay-card ready cr-ticket cr-explain"><div class="td-mkt">The leg you need · ${pbEsc(g.short_name)}</div><div class="cr-leg-top"><b class="cr-ex-label">${pbEsc(legLabel)}</b><span class="cr-px">${pLegTxt} to hit</span></div><div class="subn">${pbEsc(fmt.when(g.date))}</div>${crMeter(legPb.win, legPb.bookWin)}${facts.length ? `<dl class="cr-facts">${facts.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>` : ""}</article>`; }
  }
  out.innerHTML = crSearchBar() + head + liveBox + notesHtml() + `<div class="cr-take">${take}</div>` + srcLine + table + hedgeCard + legCard +
    `<p class="subn cr-foot">${live ? "Live lines move every play. Check your app before you bet, and re-run this with the price you see." : "Prices are the best we have across the books right now and move until kickoff."}</p>`;
  window.__crState.hedgeQ = h;
}
// ---- explain: "Why Bills -3?", "why not the Ravens?", "case for the under in the Lions game" -----
// ---- questions about the site's own picks ------------------------------------------------
// "what did the model see in the ladder pick", "why the college play of the day", "explain
// yesterday's ladder", "why this week's teaser", "best alt line": the pick as it was saved, with
// what the model saw in each leg and a check of where it stands at the prices now.
function crParsePick(text) {
  const t = " " + String(text || "").toLowerCase().replace(/[’']/g, "'").replace(/[?!.,]/g, " ").replace(/\s+/g, " ") + " ";
  let what = null;
  if (/\bladder\b/.test(t)) what = "ladder";
  else if (/\b(play|pick|bet|lock) of the day\b|\bpotd\b|\bp\.o\.t\.d\b/.test(t)) what = "potd";
  else if (/\bteasers?\b/.test(t) && !/\b\d+\s*(leg|team)\b|\bbuild\b|\bmake\b/.test(t)) what = "teaser";
  else if (/\balt(ernate)?\s*lines?\b|\balts\b/.test(t)) what = "alt";
  if (!what) return null;
  const league = /\b(college|cfb|ncaa|ncaaf|ncaa football)\b/.test(t) ? "cfb" : /\bnfl\b/.test(t) ? "nfl" : null;
  const when = /\byesterday\b|\blast night\b/.test(t) ? "yesterday" : /\b(last|previous|latest finished|most recent)\b/.test(t) ? "last" : /\btomorrow\b|\bnext\b/.test(t) ? "next" : "now";
  return { what, league, when, raw: String(text || "").trim() };
}
function crPickLegLine(l, pb) {
  const v = (x) => (x >= 0 ? "+" : "−") + Math.abs(x * 100).toFixed(1) + "%";
  return `our checked chance ${Math.round(pb.win * 100)}%, the books' ${Math.round(pb.bookWin * 100)}%, so ${pbAm(pb.price)} is ${v(pb.value)} value`;
}
// where a saved leg stands now, at the same line and book
function crPickNow(id, line, book) {
  const kind = String(id).split("|")[1];
  let pb = null;
  try { pb = pbLeg(Object.assign({ id }, (kind === "sp" || kind === "tot") && line != null ? { line: Number(line) } : {}, book ? { book } : {})); } catch (e) { pb = null; }
  if (book && pb && pb.priceSource !== book) { try { pb = pbLeg(Object.assign({ id }, (kind === "sp" || kind === "tot") && line != null ? { line: Number(line) } : {})); } catch (e) { pb = null; } }
  return pb && !pb.started ? pb : null;
}
function crPickLadder(q) {
  const rows = ladderRows().slice().sort((a, b) => String(a.day).localeCompare(String(b.day)));
  const today = potdDayKey(new Date().toISOString());
  let row = null, live = false;
  if (q.when === "yesterday") row = rows.filter((r) => r.day < today).pop() || null;
  else if (q.when === "last") row = rows.filter((r) => r.result).pop() || null;
  let passNote = "";
  if (q.when !== "yesterday" && q.when !== "last") {
    const c = ladderCurrent(); if (c) { row = c.row; live = c.live; }
    try { passNote = ladderPassDays(row ? row.day : null).map(ladderPassHtml).join(""); } catch (e) { passNote = ""; }
  }
  if (!row && passNote) return passNote;
  if (!row) return `<div class="empty">${q.when === "now" || q.when === "next" ? "There's no Ladder ticket for the next game day yet. It's built from 12 hours before the day's first game." : "There's no finished Ladder ticket to look back on yet."}</div>`;
  const legs = row.legs || [];
  const pct = (x) => Math.round(Number(x) * 100) + "%";
  const say = [];
  const dayName = potdDayName(row.firstKick || row.day);
  if (row.tier === "light") say.push(`No ticket on ${pbEsc(dayName)} cleared the Ladder's bar, so this is the light-day ticket: the closest to a fair price with no leg more than 5% under its price, tracked at half a unit for the record rather than a bet we'd push.`);
  else say.push(`Of every 2- and 3-leg ticket from different games on ${pbEsc(dayName)}, this one had the most value at a single book${row.book ? " (" + pbEsc(row.book) + ")" : ""}. Each leg had to beat its own price by at least ${Math.round(LADDER_MIN_LEG * 100)}%, and the ticket had to hit at least ${Math.round(LADDER_MIN_CHANCE * 100)}% of the time.`);
  say.push(`The legs are in different games, so their chances multiply: ${legs.map((l) => pct(l.win)).join(" × ")} = <b>${pbPct(row.chance)}</b>. At ${pbAm(row.american)} the ticket needs ${pbPct(row.breakEven)}, so it was ${(row.ev >= 0 ? "+" : "−") + Math.abs(row.ev * 100).toFixed(1)}% value when it was ${row.locked ? "locked" : "picked"}.`);
  const legCards = legs.map((l) => {
    const started = Date.parse(l.kick) <= Date.now();
    const now = started ? null : crPickNow(l.id, l.line, row.book);
    const lines = [`<b>${pbEsc(l.label)}</b> ${pbAm(l.price)} · ${pbEsc(l.game || "")} · ${LADDER_CAT[l.cat] || ""}`,
      `<span>What the model saw: our checked chance ${pct(l.win)}, the books' ${pct(l.bookWin)}, so ${pbAm(l.price)} was ${(l.value >= 0 ? "+" : "−") + Math.abs(l.value * 100).toFixed(1)}% value.${l.why && !/checked chance/.test(l.why) ? " " + l.why : ""}</span>`];
    if (l.alt) lines.push(`<span class="alt-note">Taken at an alternate line: ${pbEsc(l.alt.label)} ${pbAm(l.alt.price)} was the pick, and this book's ${pbEsc(l.label)} was the same bet worth more.</span>`);
    if (l.result) lines.push(`<span><b>${l.result === "HIT" ? "Hit" : l.result === "MISS" ? "Missed" : l.result === "PUSH" ? "Pushed" : "Void"}</b>${l.final ? " · " + pbEsc(l.final) : ""}</span>`);
    else if (now) lines.push(`<span>Now: ${pbEsc(now.label)} ${pbAm(now.price)}${now.priceSource && !/standard|typical|estimated/.test(now.priceSource) ? " at " + pbEsc(now.priceSource) : ""}, ${crPickLegLine(l, now)}${now.value >= l.value + 0.01 ? ". Better than when it was picked." : now.value <= l.value - 0.02 ? ". Worse than when it was picked; the market has moved against it." : ". About where it was."}</span>`);
    else if (started) lines.push(`<span>In play or finished; waiting on the final.</span>`);
    let clv = "";
    try { clv = row.locked ? ladderClvText(l) : ""; } catch (e) {}
    const ask = !started && l.kind !== "pp" ? `<button type="button" class="cr-link" data-crex="${pbEsc("Why " + l.label)}">Full case for this leg</button>` : "";
    return `<li data-id="${pbEsc(String(l.game_id))}">${lines.join("<br>")}${clv}${ask}</li>`;
  }).join("");
  const res = row.result ? `<p class="cr-take"><b>${row.result === "HIT" ? "It hit" : row.result === "MISS" ? "It missed" : "It pushed"}:</b> ${row.units >= 0 ? "+" : "−"}${Math.abs(row.units).toFixed(2)}u.${row.result === "MISS" ? ` A ${pbPct(row.chance)} ticket misses ${pbPct(1 - row.chance)} of the time, so one miss says little; the Ladder is judged on the run of tickets and on whether they beat the closing prices.` : ""}</p>` : "";
  return passNote + `<article class="parlay-card ready cr-ticket cr-explain cr-pickq">
    <div class="td-mkt">${row.result ? "The Ladder ticket" : live ? "The Ladder's pick right now" : "Today's Ladder ticket"} · ${pbEsc(dayName)}</div>
    <div class="cr-leg-top"><b class="cr-ex-label">${row.n}-leg · ${pbAm(row.american)}</b><span class="cr-px">${row.book ? pbEsc(row.book) : ""}</span></div>
    <div class="subn">Checked chance ${pbPct(row.chance)} · needs ${pbPct(row.breakEven)} · ${(row.ev >= 0 ? "+" : "−") + Math.abs(row.ev * 100).toFixed(1)}% value · ${row.result ? "graded" : row.locked ? "locked" : "not locked yet, it can still change"}</div>
    <div class="cr-take">${say.join(" ")}</div>
    ${res}
    <div class="lbl">Leg by leg</div>
    <ul class="parlay-legs cr-pick-legs">${legCards}</ul>
    ${!row.result ? `<button type="button" class="ready-open" data-openpb="${pbEsc(legs.map((l) => l.alt ? l.id + "@" + l.line + "@" + (row.book || "") : l.id).join("~"))}">Open in parlay builder</button>` : ""}
    <button type="button" class="cr-link" data-crgo="ladder">See the Ladder page</button>
  </article>`;
}
function crPickPotdOne(lg, q) {
  const name = lg === "nfl" ? "NFL" : "College";
  const rows = potdPublished(lg);
  const today = potdDayKey(new Date().toISOString());
  let r = null, bet = null;
  if (q.when === "yesterday") r = rows.find((x) => (x.day || potdDayKey(x.kick)) < today) || null;
  else if (q.when === "last") r = rows.find((x) => x.result) || null;
  else {
    r = rows.slice().reverse().find((x) => !x.result && Date.parse(x.kick) > Date.now() - 4 * 3600000) || null;
    if (!r) { try { bet = potdPick(lg); } catch (e) { bet = null; } }
  }
  if (!r && !bet) return `<article class="parlay-card ready cr-explain cr-pickq"><div class="td-mkt">${name} play of the day</div><div class="cr-take">${q.when === "now" || q.when === "next" ? (lg === "cfb" ? "No college game coming up qualifies: the play is an under on a total of 58 or more, or where the forecast takes 1.5+ points off the total, priced at the best book and only when it beats that price. Passing on a day is part of the rule." : "No NFL bet left this week beats its price yet: no side, total, moneyline or player prop, so there's no play of the day. It's picked from the next game, or the best of a day with 4 or more games, and player prop prices come in about a day before each kickoff, so check back then.") : "There's no finished play to look back on yet."}</div></article>`;
  const g = pbGame(r ? r.id : bet.g.id);
  const line = r ? r.line : bet.line;
  const why = r ? r.why : bet.why;
  const price = r ? potdPrice(r) : bet.price != null ? Number(bet.price) : -110;
  const book = r ? r.book : bet.book;
  const hit = r ? r.hitPct : Math.round(Number(bet.hit) * 100);
  const facts = [];
  if (hit) facts.push(`Our chance ${hit}%${r && r.bookPct ? `, the books' ${r.bookPct}%` : ""}`);
  if (r && r.ours) facts.push(`Our line ${pbEsc(r.ours)}`);
  if (r && r.market) facts.push(`Market ${pbEsc(r.market)}`);
  if (r && r.score) facts.push(`Our score ${pbEsc(r.score)}`);
  const status = r ? (r.result ? `<b>${r.result === "HIT" ? "Hit" : r.result === "MISS" ? "Missed" : r.result === "PUSH" ? "Pushed" : "Void"}</b>${r.final ? " · " + pbEsc(r.final) : ""}` : r.provisional ? "Saved, not locked yet: it can change until 90 minutes before kickoff." : "Locked 90 minutes before kickoff.") : "Our pick right now; it's saved from 12 hours before kickoff and locked 90 minutes before.";
  const rule = lg === "cfb" ? "The college rule since Nov 4: an under on a total of 58 or more (561-458, 55.1%, on 2021-2026 FBS games at the closing total) or where the forecast takes 1.5+ points off, priced at the best book, only when it beats that price." : "Any NFL bet can be the play: a side, a total, a moneyline or a player prop. It's the one that beats its best price by the most, weighted by how that kind of play has done.";
  let deep = "";
  if (g && !pbStarted(g) && lg === "cfb") {
    // the college play stands on the angle's long-run rate, not our power rating, so "now" is
    // the same test at the best price now
    try {
      const c = potdCfbCandidates(g, (gg, b) => b.kind === "Under" && Number((gg.proj || {}).weather_adj_total) <= -1.5)[0];
      deep = c ? `<p class="subn">Where it stands now: ${pbEsc(c.line)} ${pbAm(c.price)}${c.book ? " at " + pbEsc(c.book) : ""}; counted at ${Math.round(c.hit * 100)}% (the angle's long-run rate), it's ${(c.ev * 100).toFixed(1)}% better than the price. It still qualifies.</p>`
        : `<p class="subn">Where it stands now: at the best price on the board it no longer beats the price by enough to qualify${r && r.locked ? ", but it locked before that, so it stands as the play" : ", so it may change or drop before it locks"}.</p>`;
      deep += `<p class="subn">The general bet checker reads this game off our power rating and the market, which isn't what this play stands on, so it will show a thinner edge.</p>`;
    } catch (e) {}
  } else if (g && !pbStarted(g)) {
    try {
      const id = potdLegId(g, line);
      const l = id ? crMakeLeg(id) : null;
      if (l) { const x = createPrice([l.id]); const pb = x ? x.legs[0] : l.pb; if (x) l.book = x.book || l.book; deep = `<p class="subn">Where it stands now: ${pbEsc(pb.label)} ${pbAm(pb.price)}${l.book && !/standard|typical|estimated/.test(l.book) ? " at " + pbEsc(l.book) : ""}, ${crPickLegLine(l, pb)}. <button type="button" class="cr-link" data-crex="${pbEsc("Why " + pb.label)}">Full case for it</button></p>`; }
    } catch (e) {}
  }
  return `<article class="parlay-card ready cr-ticket cr-explain cr-pickq">
    <div class="td-mkt">${name} play of the day · ${pbEsc(g ? g.short_name : (r && r.game) || "")}${g ? " · " + pbEsc(fmt.when(g.date)) : ""}</div>
    <div class="cr-leg-top"><b class="cr-ex-label">${pbEsc(line)}</b><span class="cr-px">${pbAm(price)}${book ? " <small>" + pbEsc(book) + "</small>" : ""}</span></div>
    ${facts.length ? `<div class="subn">${facts.join(" · ")}</div>` : ""}
    <div class="cr-take"><b>What the model saw:</b> ${pbEsc(why || "")}</div>
    <p class="subn">${status}</p>
    ${deep}
    <p class="subn">${rule}</p>
    <button type="button" class="cr-link" data-crgo="${lg === "nfl" ? "nflpotd" : "potd"}">See the ${name.toLowerCase()} play of the day page</button>
  </article>`;
}
function crPickTeaser(q) {
  const T = ((window.GG_LOCKS || {}).teasers || []).slice().sort((a, b) => String(a.firstKick).localeCompare(String(b.firstKick)));
  let row = q.when === "last" || q.when === "yesterday" ? T.filter((r) => r.result).pop() : T.filter((r) => !r.result).pop();
  if (!row) {
    let legs = [];
    try { legs = teaserFinderLegs(); } catch (e) {}
    const t = legs.length >= 2 ? teaserTickets(legs, 2, "-120")[0] : null;
    if (!t) return `<div class="empty">No 2-team teaser qualifies this week yet: a leg has to be a spread of +1.5 to +2.5 or -7.5 to -8.5, so the six points cross both 3 and 7.</div>`;
    row = { legs: t.legs.map(tzLegRow), price: -120, chance: t.pAll, ev: t.ev, live: true };
  }
  const need = Math.sqrt(1 / pbDec(-120));
  return `<article class="parlay-card ready cr-explain cr-pickq">
    <div class="td-mkt">${row.live ? "This week's best teaser right now" : "This week's teaser"}</div>
    <div class="cr-leg-top"><b class="cr-ex-label">${row.legs.map((l) => pbEsc(l.team + " " + pbLine(l.to))).join(" + ")}</b><span class="cr-px">-120</span></div>
    <div class="cr-take"><b>What the model saw:</b> NFL games end on 3 and 7 more than any other margins, and each leg's six points cross both. ${row.legs.map((l) => `${pbEsc(l.team)} ${pbLine(l.from)} → ${pbLine(l.to)}: our checked chance ${Math.round(l.win * 100)}%, the books' ${Math.round(l.bookWin * 100)}%${l.total != null ? `, total ${pbTot(l.total)}${l.total > 49 ? " (above 49, where each point is worth less)" : ""}` : ""}.`).join(" ")} At -120 a leg needs ${(need * 100).toFixed(1)}%; the ticket ${row.chance != null ? `hits ${pbPct(row.chance)} by our chances, ${(row.ev >= 0 ? "+" : "−") + Math.abs(row.ev * 100).toFixed(1)}% value` : ""}.</div>
    ${row.result ? `<p class="subn"><b>${row.result === "HIT" ? "Won" : row.result === "MISS" ? "Lost" : "Push"}</b> · ${row.legs.map((l) => pbEsc(l.team) + " " + (l.result === "HIT" ? "covered" : l.result === "MISS" ? "missed" : "pushed")).join(", ")}</p>` : `<p class="subn">${row.locked ? "Locked 90 minutes before the first leg." : "Saved until 90 minutes before the first leg; it can change until then."}</p>`}
    <button type="button" class="cr-link" data-crgo="parlay:teasers">See the Teaser finder</button>
  </article>`;
}
function crPickAlt() {
  let rows = [];
  try { rows = altFinderRows(); } catch (e) {}
  if (!rows.length) return `<div class="empty">No alternate line beats its price right now${window.PB_ALT ? "" : " (the books' alternate lines are still loading)"}.</div>`;
  return rows.slice(0, 3).map((r) => `<article class="parlay-card ready cr-explain cr-pickq">
    <div class="td-mkt">Alt line · ${pbEsc(r.g.short_name)} · ${pbEsc(fmt.when(r.g.date))}</div>
    <div class="cr-leg-top"><b class="cr-ex-label">${pbEsc(altLabel(r))}</b><span class="cr-px">${pbAm(r.price)} <small>${pbEsc(r.book)}</small></span></div>
    <div class="subn">${Math.round(r.win * 100)}% to hit · +${(r.ev * 100).toFixed(1)}% value · ${r.mev > 0.005 ? "Best price beats the market" : "Our projection"}</div>
    <div class="cr-take"><b>What the model saw:</b> ${altWhy(r)}</div>
  </article>`).join("") + `<button type="button" class="cr-link" data-crgo="parlay:alts">See every alt line</button>`;
}
function createPickExplain(q) {
  const out = document.getElementById("createOut");
  if (!out) return;
  window.__readyPriceCache = new Map();
  window.__crState = { explain: true, ids: [], notes: [], res: { pool: [], tickets: [] } };
  let body = "";
  try {
    if (q.what === "ladder") body = crPickLadder(q);
    else if (q.what === "teaser") body = crPickTeaser(q);
    else if (q.what === "alt") body = crPickAlt();
    else body = (q.league ? [q.league] : ["nfl", "cfb"]).map((lg) => crPickPotdOne(lg, q)).join("");
  } catch (e) { console.error(e); body = `<div class="empty">I couldn't pull that pick up right now. Try again in a moment.</div>`; }
  const what = { ladder: "the Ladder ticket", potd: (q.league === "cfb" ? "the college" : q.league === "nfl" ? "the NFL" : "both") + " play" + (q.league ? "" : "s") + " of the day", teaser: "this week's teaser", alt: "the best alternate lines" }[q.what];
  out.innerHTML = crSearchBar() + `<div class="cr-understood"><span class="subn">About:</span> <span class="cr-chip">${pbEsc(what)}${q.when === "yesterday" ? ", yesterday" : q.when === "last" ? ", the last finished one" : ""}</span></div>` + body;
}
function crParseExplain(text) {
  let raw = String(text || "").replace(/\?/g, " ").replace(/\s+/g, " ").trim();
  let neg = false, m;
  if ((m = raw.match(/^(why not|why no|why skip|why pass on|why pass|why fade|why against|whats wrong with|what's wrong with|talk me out of|why dont you like|why don't you like|why doesnt the model like|why doesn't the model like)\s+(.+)$/i))) { neg = true; raw = m[2]; }
  else if ((m = raw.match(/^(why|explain|the case for|case for|whats the case for|what's the case for|make the case for|tell me about|thoughts on|your thoughts on|what do you think of|what do you think about|break down|breakdown of|break me down|sell me on|sell me|talk me into|reasoning for|reasoning on|reason for|why take|why bet|why play|do you like|you like)\s+(.+)$/i))) raw = m[2];
  else return null;
  if (/\s(or|vs\.?|versus)\s/i.test(raw)) return null;   // "why Bills -3 or Bills ML" is a comparison
  raw = raw.replace(/^(the |a |on |about |of )+/i, "").replace(/\s+(a good bet|a good play|good|worth it|worth a bet|smart|a play|as a bet|as a play|tonight|today|this week|here)$/i, "").trim();
  if (!raw) return null;
  const slip = crParseSlip(raw);
  const legs = [];
  if (slip.legs.length) slip.legs.slice(0, 3).forEach((l) => legs.push({ id: l.id, seg: l.seg, userLine: l.userLine }));
  else {
    const t = crFindTeam(crNorm(raw), raw);
    if (!t || !t.t) return { neg, raw, legs: [], miss: slip.miss };
    const g = t.t.g, side = t.t.side;
    const cands = [`${g.id}|sp|${side}`, `${g.id}|ml|${side}`].map(crMakeLeg).filter(Boolean).sort((a, b) => b.value - a.value);
    if (!cands.length) return { neg, raw, legs: [], miss: [] };
    legs.push({ id: cands[0].id, seg: raw, team: t.t, other: cands[1] ? cands[1].id : null, fixed: t.fixed });
  }
  return { neg, raw, legs, miss: slip.miss, fixed: slip.fixed };
}
// the line or price at which the leg would become a play for us
function crChangeMind(l, pb) {
  const kind = l.kind;
  if (pb.value >= 0.02) return "";
  if (kind === "sp" || kind === "tot") {
    for (let sh = 0.5; sh <= 10; sh += 0.5) {
      const alt = pbLeg({ id: l.id }, { shift: sh });
      if (alt && alt.win - alt.bookWin >= 0.02) return `We'd play it at <b>${pbEsc(alt.label)}</b> or better at a fair price, ${sh} point${sh === 1 ? "" : "s"} from where it is now.`;
    }
    const flip = kind === "sp" ? l.id.replace(/\|(home|away)$/, (m0, sd) => "|" + (sd === "home" ? "away" : "home")) : l.id.replace(/\|(over|under)$/, (m0, sd) => "|" + (sd === "over" ? "under" : "over"));
    const opp = crMakeLeg(flip);
    return `No line fixes this one: moving the line moves the books' chance with ours, and our number sits on the other side of the market's. ${opp ? `The side our number does like is <b>${pbEsc(opp.label)}</b> ${pbAm(opp.pb.price)}, ${(opp.value >= 0 ? "+" : "") + (opp.value * 100).toFixed(1)}% value${opp.value >= 0.02 ? "" : ", though not by enough to be a play either"}.` : ""}`;
  }
  if (kind === "ml") {
    if (!(pb.win > 0.02)) return "";
    const need = pbAmerican(1.02 / pb.win);
    return `We'd want <b>${pbAm(need)}</b> or better on this moneyline; it's ${pbAm(pb.price)} now.`;
  }
  if (kind === "pp") return `We'd want a line ${pb.side === "over" ? "lower" : "higher"} than ${pb.line}, or a better price than ${pbAm(pb.price)}.`;
  return "";
}
function crExplainCard(l, pb, neg, i) {
  const facts = crLegFacts(l, pb);
  const g = l.g, p = g.proj || {};
  const edgePts = l.kind === "sp" && p.hashmark_home_spread != null && g.odds && g.odds.home_spread != null ? (l.pb.side === "home" ? 1 : -1) * (Number(g.odds.home_spread) - Number(p.hashmark_home_spread)) : l.kind === "tot" && p.hashmark_total != null && g.odds && g.odds.total != null ? (pb.side === "over" ? 1 : -1) * (Number(p.hashmark_total) - Number(g.odds.total)) : null;
  const thresh = l.kind === "sp" ? (g.league === "nfl" ? 1.8 : 1.6) : l.kind === "tot" ? (g.league === "nfl" ? 1.6 : 1.5) : null;
  const likes = pb.value >= 0.02, fair = pb.value > -0.01 && !likes;
  const modelPick = l.kind === "sp" || l.kind === "ml" ? (p.pick && p.pick !== "NO PLAY" ? p.pick : null) : l.kind === "tot" ? (p.total_pick && p.total_pick !== "NO PLAY" ? p.total_pick : null) : null;
  const bits = [];
  if (likes) bits.push(`<b class="cr-up">We like ${pbEsc(pb.label)}.</b> Our checked chance is ${Math.round(pb.win * 100)}% and the price (${pbAm(pb.price)}${l.book && !/standard|typical|estimated/.test(l.book) ? " at " + pbEsc(l.book) : ""}) only needs ${Math.round(100 / pbDec(pb.price))}%, so it's +${(pb.value * 100).toFixed(1)}% value.`);
  else if (fair) bits.push(`<b>It's about a fair bet, not a play.</b> Our checked chance is ${Math.round(pb.win * 100)}% and the price needs ${Math.round(100 / pbDec(pb.price))}%; that's ${(pb.value >= 0 ? "+" : "") + (pb.value * 100).toFixed(1)}% value, too thin to call an edge.`);
  else bits.push(`<b class="cr-down">We pass on ${pbEsc(pb.label)}.</b> Our checked chance is ${Math.round(pb.win * 100)}% but the price (${pbAm(pb.price)}) needs ${Math.round(100 / pbDec(pb.price))}%, so the book has the edge: ${(pb.value * 100).toFixed(1)}% value.`);
  if (edgePts != null && thresh != null) {
    const ahead = edgePts >= thresh, toward = edgePts > 0;
    bits.push(`Our number is ${Math.abs(edgePts).toFixed(1)} point${Math.abs(edgePts) === 1 ? "" : "s"} ${toward ? "on this side of" : "on the other side of"} the line; a ${g.league === "nfl" ? "NFL" : "college"} ${l.kind === "sp" ? "side" : "total"} needs ${thresh} to be a play${ahead ? ", and this clears it" : toward ? ", so this falls short" : ""}.`);
  }
  if (l.kind === "ml" && p.win_prob_home != null) bits.push(`Our ratings alone give ${pbEsc(pb.side === "home" ? g.home.abbr : g.away.abbr)} a ${Math.round((pb.side === "home" ? p.win_prob_home : p.win_prob_away) * 100)}% chance to win; the checked chance keeps only as much of that lean as our graded record has backed.`);
  if (modelPick) bits.push(`The model's play in this game is <b>${pbEsc(modelPick)}</b>${pb.label.startsWith(String(modelPick).split(" ")[0]) ? "" : ", not this side"}.`);
  else if (l.kind !== "pp") bits.push(`The model has no play on this ${l.kind === "tot" ? "total" : "side"}.`);
  if (neg && likes) bits.push(`So "why not" has an answer you may not expect: we do like it.`);
  const change = crChangeMind(l, pb);
  const other = l.other ? crMakeLeg(l.other) : null;
  return `<article class="parlay-card ready cr-ticket cr-explain">
    <div class="td-mkt">${neg && !likes ? "Why we pass on" : "The case for"} · ${pbEsc(g.short_name)}</div>
    <div class="cr-leg-top"><b class="cr-ex-label">${pbEsc(pb.label)}</b><span class="cr-px">${pbAm(pb.price)}${l.book && !/standard|typical|estimated/.test(l.book) ? " <small>" + pbEsc(l.book) + "</small>" : ""}</span></div>
    <div class="subn">${pbEsc(fmt.when(g.date))}</div>
    ${crMeter(pb.win, pb.bookWin)}
    <div class="subn">Our checked chance <b>${Math.round(pb.win * 100)}%</b> · the books' ${Math.round(pb.bookWin * 100)}% · <span class="${pb.value >= 0.005 ? "cr-up" : pb.value <= -0.01 ? "cr-down" : ""}">${(pb.value >= 0 ? "+" : "") + (pb.value * 100).toFixed(1)}% value</span> · ${sizeHtml(kellyUnits(pb.win, pb.price, { cap: 2 }))}</div>
    <div class="cr-take">${bits.join(" ")}</div>
    ${change ? `<p class="subn cr-change"><b>What would change our mind:</b> ${change}</p>` : ""}
    ${facts.length ? `<dl class="cr-facts">${facts.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>` : ""}
    ${other ? `<p class="subn">The other way to bet ${pbEsc(l.team ? l.team.short : "it")}: <b>${pbEsc(other.label)}</b> ${pbAm(other.pb.price)}, ${(other.value >= 0 ? "+" : "") + (other.value * 100).toFixed(1)}% value${other.value > pb.value ? " — better than the one above" : ""}. <button type="button" class="cr-link" data-crex="${pbEsc(pb.label + " or " + other.label)}">Compare them</button></p>` : ""}
    <div class="cr-actions">
      <button type="button" class="cr-act save${crIsSaved({ bag: [l] }) ? " done" : ""}" data-crsave="${i}"${crIsSaved({ bag: [l] }) ? " disabled" : ""}>${crIsSaved({ bag: [l] }) ? "★ Saved to My bets" : "☆ Save to My bets"}</button>
      <button type="button" class="cr-act" data-crshare="${pbEsc("t=" + encodeURIComponent(l.id))}">Share</button>
    </div>
    <button type="button" class="ready-open" data-openpb="${pbEsc(l.id)}">Open in parlay builder</button>
  </article>`;
}
function createExplain(ex) {
  const out = document.getElementById("createOut");
  if (!out) return;
  window.__readyPriceCache = new Map();
  const notes = [];
  (ex.fixed || []).forEach(([a, b]) => notes.push(`I read "${pbEsc(a)}" as ${pbEsc(b)}.`));
  (ex.miss || []).forEach((m) => notes.push(pbEsc(m.why)));
  const cards = [], tickets = [];
  ex.legs.forEach((s) => {
    const l = crMakeLeg(s.id);
    if (!l) { notes.push(`I couldn't price "${pbEsc(s.seg)}" right now: no line is posted for it yet, or the game has started.`); return; }
    if (s.other) l.other = s.other;
    if (s.team) l.team = s.team;
    const x = createPrice([l.id]);
    const pb = x ? x.legs[0] : l.pb;
    if (x) l.book = x.book || l.book;
    if (s.userLine != null && pb.line != null && Math.abs(Number(pb.line) - s.userLine) >= 0.25) notes.push(`You typed "${pbEsc(s.seg)}". The line now is <b>${pbEsc(pb.label)}</b>, so that's what this is about.`);
    tickets.push({ bag: [l], x: x || { r: pbParlay([pb], 0), legs: [pb], book: null }, check: true });
    cards.push(crExplainCard(l, pb, ex.neg, cards.length));
  });
  window.__crState = { explain: true, ids: [], notes, res: { pool: [], tickets } };
  const notesHtml = notes.length ? `<div class="cr-notes">${notes.map((n) => `<p>${n}</p>`).join("")}</div>` : "";
  if (!cards.length) { out.innerHTML = crSearchBar() + notesHtml + `<div class="empty">I couldn't tell which bet "${pbEsc(ex.raw)}" is. Try a team and a line, like "why Bills -3", or just a team, like "why not the Ravens".</div>`; return; }
  out.innerHTML = crSearchBar() + `<div class="cr-understood"><span class="subn">${ex.neg ? "Why not:" : "The case for:"}</span> ${tickets.map((t) => `<span class="cr-chip">${pbEsc(t.x.legs[0].label)}</span>`).join("")}</div>` + notesHtml + cards.join("") +
    `<p class="subn cr-foot">Our checked chance is the books' chance moved part of the way toward our number, as far as our graded record backs. Value is that chance against the best current price.</p>`;
}
// ---- suggestions while typing: teams, players and the words we understand ----------------
const CR_WORD_SUG = [["moneyline", "moneyline parlay"], ["safest", "safest 2 leg parlay"], ["longshot", "longshot 4 leg"], ["player", "player prop unders"], ["props", "player prop unders"], ["unders", "unders"], ["overs", "overs"], ["underdogs", "underdogs"], ["weekend", "this weekend"], ["college", "college"], ["nfl", "NFL"], ["sunday", "Sunday"], ["saturday", "Saturday"], ["thursday", "Thursday"], ["monday", "Monday"], ["spread", "spread"], ["parlay", "parlay"]];
function crSuggest(text) {
  const raw = String(text || "");
  if (/\s$/.test(raw)) return [];
  const tailRaw = raw.split(/,|;|\s\+\s|\sand\s|\swith\s/i).pop();
  const words = crNorm(tailRaw).trim().split(" ").filter(Boolean);
  const last = words[words.length - 1] || "";
  if (last.length < 2 || /\d/.test(last)) return [];
  const idx = crIndex();
  const rawTail = (n) => { const m = raw.match(new RegExp("(\\S+(?:\\s+\\S+){" + (n - 1) + "})\\s*$")); return m ? m[1].length : last.length; };
  const out = [];
  const tryN = (n) => {
    if (words.length < n) return null;
    const s = words.slice(-n).join(" ");
    if (s.length < 2) return null;
    const teams = [], players = [];
    idx.teams.forEach((t) => {
      let score = 0;
      t.keys.forEach((k) => { if (k.startsWith(s)) score = Math.max(score, 3); else if (k.split(" ").some((w) => w.startsWith(s))) score = Math.max(score, 2); });
      if (!score && s.toUpperCase() === t.abbr) score = 3;
      if (!score && s.length >= 4) t.keys.forEach((k) => k.split(" ").forEach((w) => { if (w.length >= s.length && crLev(s, w.slice(0, s.length), 1) <= 1) score = Math.max(score, 1); }));
      if (score) teams.push({ t, score });
    });
    idx.players.forEach((x) => {
      let score = 0;
      if (x.name.startsWith(s)) score = 3; else if (x.last.startsWith(s) && s.length >= 3) score = 2;
      else if (s.length >= 4 && x.last.length >= s.length && crLev(s, x.last.slice(0, s.length), 1) <= 1) score = 1;
      if (score) players.push({ x, score });
    });
    const strongT = teams.some((x) => x.score >= 2), strongP = players.some((x) => x.score >= 2);
    return { n, teams: teams.filter((x) => !strongT && !strongP || x.score >= 2).sort((a, b) => b.score - a.score || (a.t.league === "nfl" ? -1 : 1)), players: players.filter((x) => !strongT && !strongP || x.score >= 2).sort((a, b) => b.score - a.score) };
  };
  const hit = (words.length >= 2 && (() => { const h = tryN(2); return h && (h.teams.some((x) => x.score >= 2) || h.players.some((x) => x.score >= 2)) ? h : null; })()) || tryN(1);
  if (!hit) return [];
  const cut = rawTail(hit.n);
  const when = (g) => fmt.when(g.date);
  const add = (label, sub, insert) => { if (out.length < 7 && !out.some((o) => o.insert === insert)) out.push({ label, sub, insert, cut }); };
  const tops = hit.teams.slice(0, 6), pls = hit.players.slice(0, 4);
  if (tops.length && (tops.length <= 2 || tops[0].score > (tops[1] ? tops[1].score : 0)) && (!pls.length || tops[0].score >= pls[0].score)) {
    const t = tops[0].t, g = t.g;
    add(t.name, `${g.short_name} · ${when(g)}`, t.name);
    const ml = crMakeLeg(`${g.id}|ml|${t.side}`), sp = crMakeLeg(`${g.id}|sp|${t.side}`), ov = crMakeLeg(`${g.id}|tot|over`), un = crMakeLeg(`${g.id}|tot|under`);
    const v = (l) => `${pbAm(l.pb.price)}${l.book && !/standard|typical|estimated/.test(l.book) ? " at " + l.book : ""} · ${(l.value >= 0 ? "+" : "") + (l.value * 100).toFixed(1)}% value`;
    if (sp) add(`${t.short} ${pbLine(sp.pb.line)}`, v(sp), `${t.short} ${pbLine(sp.pb.line)}`);
    if (ml) add(`${t.short} to win`, v(ml), `${t.short} to win`);
    if (ov && un) { const pick = ov.value >= un.value ? ov : un; add(`${t.short} game ${pick.label.toLowerCase()}`, `${g.short_name} · ${v(pick)}`, `${t.short} game ${pick.label.toLowerCase()}`); }
    tops.slice(1, 3).forEach(({ t: t2 }) => add(t2.name, `${t2.g.short_name} · ${when(t2.g)}`, t2.name));
  } else {
    pls.forEach(({ x }) => {
      const p = x.p;
      let L = null;
      try { L = postedLean(p); } catch (e) {}
      if (L && L.price != null) {
        const lbl = String(PROP_LBL[L.m.key] || L.m.label || "").toLowerCase();
        add(`${p.name} ${L.take.toLowerCase()} ${L.line} ${lbl}`, `${p.pos || ""} · ${pbAm(L.price)}${L.book ? " at " + L.book : ""} · our lean`, `${p.name} ${L.take.toLowerCase()} ${L.line} ${lbl}`);
      } else add(p.name, `${p.pos || ""} · ${p.opp ? "vs " + p.opp + " · " : ""}props post about a day before kickoff`, p.name);
    });
    tops.slice(0, 7 - out.length).forEach(({ t }) => add(t.name, `${t.g.short_name} · ${when(t.g)}`, t.name));
  }
  if (out.length < 3) CR_WORD_SUG.forEach(([w, ins]) => { if (w.startsWith(last) && w !== last && out.length < 5) out.push({ label: ins, sub: "", insert: ins, cut: last.length }); });
  return out;
}
// what the box will do with the words so far, updated as you type
function crLiveHtml(text) {
  if (!String(text || "").trim()) return "";
  let pq = null;
  try { pq = crParsePick(text); } catch (e) {}
  if (pq) return `<span class="subn">About:</span> <span class="cr-chip">${pbEsc({ ladder: "the Ladder ticket", potd: (pq.league === "cfb" ? "college " : pq.league === "nfl" ? "NFL " : "") + "play of the day", teaser: "this week's teaser", alt: "alternate lines" }[pq.what])}${pq.when === "yesterday" ? ", yesterday" : pq.when === "last" ? ", last finished" : ""}</span>`;
  let hg = null;
  try { hg = crParseHedge(text); } catch (e) {}
  if (hg) return `<span class="subn">Hedging:</span> ${hg.hit.map((l) => { const pb = pbLeg({ id: l.id }); return `<span class="cr-chip">${pbEsc(pb ? pb.label : l.seg)} ✓</span>`; }).join("")}${hg.left.map((l) => { const pb = pbLeg({ id: l.id }); return `<span class="cr-chip warn">${pbEsc(pb ? pb.label : l.seg)} left</span>`; }).join("")}${hg.stake != null ? `<span class="cr-chip">${pbMoney(hg.stake)} risked</span>` : `<span class="cr-chip warn">add the stake, like $50</span>`}${hg.payout != null ? `<span class="cr-chip">collects ${pbMoney(hg.payout)}</span>` : hg.odds == null ? `<span class="cr-chip warn">and the odds, like +600</span>` : ""}${hg.live ? `<span class="cr-chip fix">live: ${pbEsc(hg.live.seg)}</span>` : ""}${hg.miss.map((m) => `<span class="cr-chip warn">Can't read "${pbEsc(m)}"</span>`).join("")}`;
  let ex = null;
  try { ex = crParseExplain(text); } catch (e) {}
  if (ex) return `<span class="subn">${ex.neg ? "Why not:" : "The case for:"}</span> ${ex.legs.length ? ex.legs.map((s) => { const pb = pbLeg({ id: s.id }); return `<span class="cr-chip">${pbEsc(pb ? pb.label : s.seg)}</span>`; }).join("") : `<span class="cr-chip warn">Name a team or a bet</span>`}`;
  let cmp = null;
  try { cmp = crParseCompare(text); } catch (e) {}
  if (cmp) return `<span class="subn">Comparing:</span> ${cmp.map((sd) => `<span class="cr-chip">${pbEsc(sd.ids.map((id) => { const pb = pbLeg({ id }); return pb ? pb.label : sd.seg; }).join(" + "))}</span>`).join("")}`;
  const slip = crParseSlip(text);
  const flag = (arr) => arr.map(([a, b]) => `<span class="cr-chip fix">"${pbEsc(a)}" → ${pbEsc(b)}</span>`).join("");
  if (slip.check) {
    const lbl = slip.legs.map((l) => { const pb = pbLeg({ id: l.id }); const nm = l.player ? l.player.name.split(" ").pop() + " " : ""; return pb ? (l.player ? nm + pb.label.replace(/^.*?(Over|Under)/i, "$1") : pb.label) : l.seg; });
    return `<span class="subn">Checking your ${slip.legs.length === 1 ? "bet" : slip.legs.length + "-leg ticket"}:</span> ${lbl.map((x) => `<span class="cr-chip">${pbEsc(x)}</span>`).join("")}${flag(slip.fixed)}${slip.miss.map((m) => `<span class="cr-chip warn">${pbEsc(/don't have a game/.test(m.why) ? m.why.replace(/\.$/, "") : `Can't read "${m.seg}"`)}</span>`).join("")}`;
  }
  const want = createParse(text);
  const miss = (want.missing || []).map((m) => `<span class="cr-chip warn">${pbEsc(m.name)} isn't on this week's prop board${m.injury && m.injury !== "ACTIVE" ? " (" + pbEsc(String(m.injury).toLowerCase()) + ")" : ""}</span>`).join("");
  if (!/\s$/.test(text)) { const lastW = crNorm(text).trim().split(" ").pop(); want.unknown = (want.unknown || []).filter((w) => w !== lastW); }
  const unk = (want.unknown || []).length ? `<span class="cr-chip warn">Not sure what "${pbEsc(want.unknown.slice(0, 3).join(" "))}" means</span>` : "";
  return `<span class="subn">I'll look for:</span> ${createUnderstood(want)}${flag(want.fixed || [])}${miss}${unk}`;
}
function crWireBox(root) {
  const input = root.querySelector("#createInput"), list = root.querySelector("#createSug"), live = root.querySelector("#createLive");
  let items = [], sel = -1, timer = null;
  const close = () => { clearTimeout(timer); list.hidden = true; list.innerHTML = ""; items = []; sel = -1; input.setAttribute("aria-expanded", "false"); input.removeAttribute("aria-activedescendant"); };
  const draw = () => {
    if (!items.length) return close();
    list.innerHTML = items.map((it, k) => `<li role="option" id="crsug${k}" data-k="${k}" aria-selected="${k === sel}"><b>${pbEsc(it.label)}</b>${it.sub ? `<span>${pbEsc(it.sub)}</span>` : ""}</li>`).join("");
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
    if (sel >= 0) input.setAttribute("aria-activedescendant", "crsug" + sel); else input.removeAttribute("aria-activedescendant");
  };
  const pick = (k) => {
    const it = items[k];
    if (!it) return;
    const v = input.value;
    input.value = v.slice(0, v.length - it.cut) + it.insert + " ";
    close();
    input.focus();
    update();
  };
  const update = () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      try { live.innerHTML = crLiveHtml(input.value); } catch (e) { live.innerHTML = ""; }
      try { items = crSuggest(input.value); } catch (e) { items = []; }
      sel = -1;
      draw();
    }, 110);
  };
  input.addEventListener("input", update);
  input.addEventListener("keydown", (e) => {
    if (list.hidden || !items.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); sel = (sel + 1) % items.length; draw(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); sel = sel <= 0 ? items.length - 1 : sel - 1; draw(); }
    else if (e.key === "Enter" && sel >= 0) { e.preventDefault(); pick(sel); }
    else if (e.key === "Escape") { e.preventDefault(); close(); }
    else if (e.key === "Tab" && items.length) { e.preventDefault(); pick(sel >= 0 ? sel : 0); }
  });
  list.addEventListener("mousedown", (e) => { const li = e.target.closest("li[data-k]"); if (li) { e.preventDefault(); pick(Number(li.dataset.k)); } });
  input.addEventListener("blur", () => setTimeout(close, 150));
  root.__crUpdate = update;
  root.__crClose = close;
}
function renderCreate() {
  const root = document.getElementById("createSection");
  if (!root) return;
  try { ensureAlt(); } catch (e) {}
  if (!root.__built) {
    root.__built = true;
    root.innerHTML = `<div class="cr-wrap">
      <h2 class="cr-h">Create your own</h2>
      <p class="subn">Ask for a parlay in your own words, or type a bet you already have to check it. It's built from this week's board: our number on every side, total and moneyline, every player prop we price, each leg checked against its best price, and the reason for every leg.</p>
      <form class="cr-form" id="createForm" role="search">
        <div class="cr-box">
          <input id="createInput" type="search" autocomplete="off" autocapitalize="off" spellcheck="false" enterkeyhint="search" placeholder="e.g. 3 leg NFL parlay at +600, or why the Ladder pick?" aria-label="Ask for a parlay, check a bet or ask about a pick" role="combobox" aria-expanded="false" aria-controls="createSug" aria-autocomplete="list">
          <ul id="createSug" class="cr-sug" role="listbox" aria-label="Suggestions" hidden></ul>
        </div>
        <button type="submit">Build it</button>
      </form>
      <div id="createLive" class="cr-live" aria-live="polite"></div>
      <div class="cr-ex" id="createEx">${["3 leg NFL parlay at +600", "Safest 2 leg parlay this weekend", "Sunday player prop unders", "College moneyline parlay Saturday", "Longshot 4 leg with underdogs", "$20 to win $200", "Sunday night only", "Parlay without the Chiefs", "What did the model see in the Ladder pick?", "Why the college play of the day?"].map((t) => `<button type="button" data-crex="${pbEsc(t)}">${pbEsc(t)}</button>`).join("")}${(() => { const ex = crCheckExample(); return ex ? `<button type="button" class="cr-ex-check" data-crex="${pbEsc(ex)}">Check: ${pbEsc(ex)}</button>` : ""; })()}${(() => { const ex = crHedgeExample(); return ex ? `<button type="button" class="cr-ex-check" data-crex="${pbEsc(ex)}">${pbEsc(ex)}</button>` : ""; })()}${(() => { const ex = crCompareExample(); return ex ? `<button type="button" class="cr-ex-check" data-crex="${pbEsc("Why " + ex.split(" or ")[0])}">Explain: Why ${pbEsc(ex.split(" or ")[0])}?</button>` : ""; })()}${(() => { const ex = crCompareExample(); return ex ? `<button type="button" class="cr-ex-check" data-crex="${pbEsc(ex)}">Compare: ${pbEsc(ex)}</button>` : ""; })()}</div>
      <div class="cr-recent" id="createRecent"></div>
      <div id="createRecord"></div>
      <div id="createOut"></div>
    </div>`;
    const form = root.querySelector("#createForm"), input = root.querySelector("#createInput");
    form.addEventListener("submit", (e) => { e.preventDefault(); if (root.__crClose) root.__crClose(); createRun(input.value); });
    crWireBox(root);
    root.addEventListener("click", (e) => {
      const ex = e.target.closest("[data-crex]");
      if (ex) { input.value = ex.dataset.crex; if (root.__crUpdate) root.__crUpdate(); createRun(ex.dataset.crex); return; }
      const go = e.target.closest("[data-crgo]");
      if (go) { e.stopPropagation(); const [v, sub] = go.dataset.crgo.split(":"); if (sub) window.__parlayLg = sub; setView(v, { push: true }); window.scrollTo(0, 0); return; }
      const b = e.target.closest("[data-openpb]");
      if (b) { e.stopPropagation(); openInBuilder(b.dataset.openpb); return; }
      const sw = e.target.closest("[data-crswap]");
      if (sw) { e.stopPropagation(); createSwap(sw.dataset.crswap); return; }
      const sh = e.target.closest("[data-crshare]");
      if (sh) { e.stopPropagation(); crShare(sh.dataset.crshare, sh); return; }
      const sv = e.target.closest("[data-crsave]");
      if (sv) { e.stopPropagation(); crSaveTicket(Number(sv.dataset.crsave), sv); return; }
      const rc = e.target.closest("[data-crclear]");
      if (rc) { e.stopPropagation(); try { localStorage.removeItem(CR_RECENT_KEY); } catch (err) {} crRecentDraw(); return; }
      const rl = e.target.closest("[data-crrelive]");
      if (rl) { e.stopPropagation(); if (crLiveState.m) crLiveState.m.clear(); const st = window.__crState; if (st && st.hedgeQ) createHedge(st.hedgeQ); return; }
      const dr = e.target.closest("[data-crdrop]");
      if (dr) { e.stopPropagation(); const st = window.__crState; if (st && st.check) { st.ids.splice(Number(dr.dataset.crdrop), 1); createCheckRender(); } return; }
      const rf = e.target.closest("[data-crref]");
      if (rf) { e.stopPropagation(); createRefine(rf.dataset.crref); return; }
      const li = e.target.closest("li[data-id]");
      if (li) openGame(li.dataset.id);
    });
    try { if (typeof ensurePotdProps === "function") ensurePotdProps(); } catch (e) {}
    try { paceLoad(); } catch (e) {}
  }
  crRecentDraw();
  crRecordDraw();
  if (window.__crPending) { const pend = window.__crPending; window.__crPending = null; crOpenLink(pend); return; }
  setTimeout(() => { try { const i = document.getElementById("createInput"); if (i && !i.value) i.focus({ preventScroll: true }); } catch (e) {} }, 60);
}
function createRun(text) {
  const out = document.getElementById("createOut");
  if (!out) return;
  if (!String(text || "").trim()) { out.innerHTML = `<div class="empty">Type what you want, like "3 leg NFL parlay at +600".</div>`; return; }
  crRemember(text);
  crSetLink("q=" + encodeURIComponent(String(text).trim()));
  let pq = null;
  try { pq = crParsePick(text); } catch (e) { pq = null; }
  if (pq) { createPickExplain(pq); return; }
  let hg = null;
  try { hg = crParseHedge(text); } catch (e) { hg = null; }
  if (hg) { createHedge(hg); return; }
  let ex = null;
  try { ex = crParseExplain(text); } catch (e) { ex = null; }
  if (ex) { createExplain(ex); return; }
  let cmp = null;
  try { cmp = crParseCompare(text); } catch (e) { cmp = null; }
  if (cmp) { createCompare(cmp); return; }
  let slip = null;
  try { slip = crParseSlip(text); } catch (e) { slip = null; }
  if (slip && slip.check) { createCheck(slip); return; }
  let want;
  try { want = createParse(text); } catch (e) { out.innerHTML = `<div class="empty">Something went wrong reading that. Try rewording it.</div>`; return; }
  createShow(want);
}
function createShow(want) {
  const out = document.getElementById("createOut");
  if (!out) return;
  window.__readyPriceCache = new Map();
  let res;
  try { res = createTickets(want); } catch (e) { out.innerHTML = `<div class="empty">Something went wrong building that. Try rewording it.</div>`; return; }
  window.__crState = { want, res };
  const notes = [];
  (want.fixed || []).forEach(([a, b]) => notes.push(`I read "${pbEsc(a)}" as ${pbEsc(b)}.`));
  (want.missing || []).forEach((m) => notes.push(`${pbEsc(m.name)} isn't on this week's prop board${m.injury && m.injury !== "ACTIVE" ? " (listed " + pbEsc(String(m.injury).toLowerCase()) + ")" : ""}, so these tickets are built without him.`));
  if (want.players.length && res.pool && !res.pool.some((l) => l.kind === "pp")) notes.push(`${pbEsc(want.players.map((p) => p.name).join(" and "))}: no prop prices are posted yet (they go up about a day before kickoff), so these tickets use ${want.players.length === 1 ? "his" : "their"} game instead.`);
  if ((want.unknown || []).length) notes.push(`I skipped words I didn't understand: "${pbEsc(want.unknown.join(" "))}".`);
  if (res.shrunk) notes.push(res.shrunk.to === 1 ? `Only one game fits that, so these are single bets from it rather than a ${res.shrunk.from}-leg parlay (legs from one game would ride together).` : `Only ${res.shrunk.to} games fit that, so these are ${res.shrunk.to}-leg tickets instead of ${res.shrunk.from}.`);
  const head = `<div class="cr-understood"><span class="subn">What I looked for:</span> ${createUnderstood(want)}</div>` + (notes.length ? `<div class="cr-notes">${notes.map((n) => `<p>${n}</p>`).join("")}</div>` : "");
  const refine = `<div class="cr-refine"><span class="subn">Change it:</span>${[
    want.mode !== "safe" && ["safer", "Safer"],
    ["bigger", "Bigger payout"],
    want.legs < 6 && ["more", "Add a leg"],
    want.legs > 2 && ["fewer", "One fewer leg"],
    want.mode !== "value" && ["value", "Best value"],
    !want.league && ["nfl", "NFL only"],
    !want.league && ["cfb", "College only"],
    (!want.kinds || want.kinds.has("pp")) && ["noprops", "No player props"]
  ].filter(Boolean).map(([k, t]) => `<button type="button" data-crref="${k}">${t}</button>`).join("")}</div>`;
  if (!res.tickets.length) {
    const why = !res.pool.length ? "Nothing on the board matches that right now (no games left that day, or no lines for those teams or players yet; player prop prices post about a day before each NFL game)." : `Only ${res.pool.length} leg${res.pool.length === 1 ? "" : "s"} matched, from fewer different games than the ticket needs.`;
    out.innerHTML = head + `<div class="empty">${why} Try fewer legs, another day, or a wider ask like "NFL parlay this weekend".</div>` + refine;
    return;
  }
  out.innerHTML = crSearchBar() + head + refine + res.tickets.map(createTicketHtml).join("") + `<p class="subn cr-foot">Prices are the best we have across the books right now and move until kickoff. Our checked chance is the books' chance moved part of the way toward our number, as far as our graded record backs. A parlay misses more often than a single bet, so stake less on it.</p>`;
}
// ---- links, recent searches and saving -----------------------------------------------------
const CR_RECENT_KEY = "gg-create-recent";
function crLinkUrl(param) { return location.origin + location.pathname + "#create?" + param; }
function crSetLink(param) { try { history.replaceState({ view: "create" }, "", "#create?" + param); } catch (e) {} }
function crOpenLink(p) {
  const input = document.getElementById("createInput");
  const go = () => {
    if (p.t) {
      const ids = p.t.split("~").map((x) => { try { return decodeURIComponent(x); } catch (e) { return x; } }).filter(Boolean).slice(0, 8);
      const labels = ids.map((id) => { const pb = pbLeg({ id }); return pb ? pb.label : null; });
      if (input) input.value = labels.filter(Boolean).join(", ");
      createCheck({ legs: ids.map((id, k) => ({ id, seg: labels[k] || "this leg" })), miss: [], fixed: [] });
      crSetLink("t=" + ids.map(encodeURIComponent).join("~"));
    } else if (p.q) {
      if (input) input.value = p.q;
      createRun(p.q);
    }
    const root = document.getElementById("createSection");
    if (root && root.__crUpdate) root.__crUpdate();
  };
  go();
  if (!window.PB_BOOKS) {
    let n = 0;
    const iv = setInterval(() => { n++; if (window.PB_BOOKS || n > 30) { clearInterval(iv); if (window.PB_BOOKS && view === "create") go(); } }, 500);
  }
}
function crSearchBar() {
  const h = (location.hash || "").replace(/^#/, "");
  const param = /^create\?/.test(h) ? h.replace(/^create\?/, "") : "";
  return param ? `<div class="cr-sharebar"><button type="button" class="cr-act" data-crshare="${pbEsc(param)}">Share this search</button><span class="subn">The link opens these tickets, re-priced at that moment.</span></div>` : "";
}
function crShare(param, btn) {
  const url = crLinkUrl(param);
  const done = (msg) => { if (!btn) return; const old = btn.textContent; btn.textContent = msg; btn.classList.add("done"); setTimeout(() => { btn.textContent = old; btn.classList.remove("done"); }, 2200); };
  const copy = () => {
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(() => done("Link copied"), () => fallback());
    else fallback();
  };
  const fallback = () => {
    try {
      const ta = document.createElement("textarea");
      ta.value = url; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      const ok = document.execCommand && document.execCommand("copy");
      ta.remove();
      done(ok ? "Link copied" : "Copy the address bar");
    } catch (e) { done("Copy the address bar"); }
  };
  if (navigator.share && /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent || "")) {
    navigator.share({ title: "Double Gs ticket", text: "Check out this ticket on Double Gs", url }).catch((e) => { if (!e || e.name !== "AbortError") copy(); });
  } else copy();
}
function crRecent() { try { const v = JSON.parse(localStorage.getItem(CR_RECENT_KEY) || "[]"); return Array.isArray(v) ? v.filter((x) => typeof x === "string") : []; } catch (e) { return []; } }
function crRemember(text) {
  const q = String(text || "").trim().replace(/\s+/g, " ");
  if (!q) return;
  const list = [q].concat(crRecent().filter((x) => x.toLowerCase() !== q.toLowerCase())).slice(0, 6);
  try { localStorage.setItem(CR_RECENT_KEY, JSON.stringify(list)); } catch (e) {}
  crRecentDraw();
}
function crRecentDraw() {
  const box = document.getElementById("createRecent");
  if (!box) return;
  const list = crRecent();
  box.innerHTML = list.length ? `<span class="subn">Recent:</span>${list.map((q) => `<button type="button" data-crex="${pbEsc(q)}">${pbEsc(q)}</button>`).join("")}<button type="button" class="cr-clear" data-crclear="1" aria-label="Clear recent searches">Clear</button>` : "";
}
function crTicketKey(ids) { return ids.slice().sort().join("~"); }
function crIsSaved(t) {
  const key = crTicketKey(t.bag.map((l) => l.id));
  try { return mbLoad().some((b) => b.src === "create" && crTicketKey((b.legs || []).map((l) => l.id)) === key && (b.legs || []).every((l) => !l.result)); } catch (e) { return false; }
}
// save to My bets (graded there from the final scores, like a ticket from the builder)
function crSaveTicket(i, btn) {
  const st = window.__crState;
  const t = st && st.res && st.res.tickets[i];
  if (!t || !t.x) return;
  const legs = t.x.legs;
  if (legs.some((l) => !l || l.started)) { if (btn) btn.textContent = "A leg has started"; return; }
  const stake = (typeof PB !== "undefined" && PB.stake) || 10;
  const entry = {
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6), at: new Date().toISOString(), mode: "parlay", src: "create", book: t.x.book || null,
    q: String((document.getElementById("createInput") || {}).value || "").trim().slice(0, 120), ckind: st.explain ? "explain" : st.compare ? "compare" : st.check ? "check" : "built",
    chance: +Number(t.x.r.pAll).toFixed(4), ev: +Number(t.x.r.ev).toFixed(4),
    teaserPts: null, stake, cost: stake, boost: 0, price: t.x.r.american, combos: null,
    legs: legs.map((l, k) => ({ id: l.id, gid: l.gid || t.bag[k].gid, kind: l.kind || t.bag[k].kind, side: l.side, line: l.line, price: l.price, label: l.label, game: l.game || t.bag[k].g.short_name, date: (l.g && l.g.date) || t.bag[k].g.date, league: (l.g && l.g.league) || t.bag[k].g.league, win: l.win }))
  };
  const list = mbLoad(); list.push(entry); mbSave(list);
  if (btn) { btn.textContent = "★ Saved to My bets"; btn.classList.add("done"); btn.disabled = true; }
  const note = document.createElement("p");
  note.className = "subn cr-saved-note";
  note.innerHTML = `Saved: ${pbAm(entry.price)}${entry.book ? " at " + pbEsc(entry.book) : ""}, $${stake} risk. It's graded in <a href="#bets" data-jump="bets">My bets</a> when the games go final.`;
  const card = btn && btn.closest(".cr-ticket");
  if (card && !card.querySelector(".cr-saved-note")) card.querySelector(".cr-actions").after(note);
  crRecordDraw();
}
// ---- the record: every ticket saved from this page, graded from the final scores ----------
// Only tickets you tap Save on count; nothing is tracked just for being built. Kept in this
// browser with the rest of My bets.
function crRecordDraw() {
  const box = document.getElementById("createRecord");
  if (!box) return;
  let list = [];
  try { list = mbLoad().filter((t) => t && t.src === "create"); } catch (e) {}
  if (!list.length) { box.innerHTML = `<div class="cr-rec empty-rec"><b>Your record from here</b><span class="subn">Tap <b>Save to My bets</b> on any ticket you actually play. It's graded from the final scores and your record shows here, like the play of the day.</span></div>`; return; }
  const graded = list.map((t) => ({ t, g: mbGrade(t) }));
  try { mbSave(mbLoad().map((t) => { const h = graded.find((x) => x.t.id === t.id); return h ? h.t : t; })); } catch (e) {}
  const done = graded.filter((x) => ["won", "lost", "push"].includes(x.g.state));
  const open = graded.filter((x) => x.g.state === "open" || x.g.state === "check");
  const w = done.filter((x) => x.g.state === "won").length, l = done.filter((x) => x.g.state === "lost").length, pu = done.filter((x) => x.g.state === "push").length;
  const risk = done.reduce((a, x) => a + (x.t.cost || x.t.stake), 0), profit = done.reduce((a, x) => a + x.g.profit, 0);
  const roi = risk ? profit / risk : 0;
  const expected = done.reduce((a, x) => a + (x.t.ev != null ? x.t.ev * (x.t.cost || x.t.stake) : 0), 0);
  const kinds = { built: "Built here", check: "Checked", compare: "Compared", explain: "Explained" };
  const byKind = Object.keys(kinds).map((k) => { const d = done.filter((x) => x.t.ckind === k && x.g.state !== "push"); if (!d.length) return ""; const kw = d.filter((x) => x.g.state === "won").length, kl = d.filter((x) => x.g.state === "lost").length, kp = d.reduce((a, x) => a + x.g.profit, 0), kr = d.reduce((a, x) => a + (x.t.cost || x.t.stake), 0); return `<span>${kinds[k]} <b>${kw}-${kl}</b> <em class="${kp >= 0 ? "cr-up" : "cr-down"}">${kp >= 0 ? "+" : ""}${pbMoney(kp)}${kr ? " (" + (kp / kr * 100 >= 0 ? "+" : "") + (kp / kr * 100).toFixed(0) + "%)" : ""}</em></span>`; }).filter(Boolean);
  const chip = (st) => ({ won: "Won", lost: "Lost", push: "Push", open: "Open", check: "Mark result" }[st] || st);
  const row = (x) => `<li class="cr-rec-t rec-${x.g.state}"><span class="cr-rec-st">${chip(x.g.state)}${x.g.profit != null ? " " + (x.g.profit >= 0 ? "+" : "") + pbMoney(x.g.profit) : ""}</span><b>${pbEsc(x.t.legs.map((lg) => lg.label).join(" + "))}</b><em>${x.t.price != null ? pbAm(x.t.price) : ""}${x.t.book ? " at " + pbEsc(x.t.book) : ""} · ${pbEsc(fmt.when(x.t.legs[0] && x.t.legs[0].date ? x.t.legs[0].date : x.t.at))}${x.t.q ? ` · "${pbEsc(x.t.q)}"` : ""}</em></li>`;
  const headline = done.length ? `Tickets saved from here are <b>${w}-${l}${pu ? "-" + pu : ""}</b>, <b class="${profit >= 0 ? "cr-up" : "cr-down"}">${profit >= 0 ? "+" : ""}${pbMoney(profit)}</b> on ${pbMoney(risk)} risked (${roi >= 0 ? "+" : ""}${(roi * 100).toFixed(1)}% return).` : `${open.length} ticket${open.length === 1 ? "" : "s"} saved from here, none settled yet.`;
  box.innerHTML = `<div class="cr-rec">
    <div class="cr-rec-head"><b>Your record from here</b><a href="#bets" data-jump="bets">All of My bets</a></div>
    <p class="cr-rec-line">${headline}${done.length >= 5 && Math.abs(expected) > 0.005 ? ` Our prices expected about <b>${expected >= 0 ? "+" : ""}${pbMoney(expected)}</b> on those, so you're running ${profit - expected >= 0 ? "ahead of" : "behind"} the model by ${pbMoney(Math.abs(profit - expected))}.` : ""}</p>
    <div class="cr-rec-stats"><div><b>${w}-${l}${pu ? "-" + pu : ""}</b><span>Record</span></div><div><b class="${profit >= 0 ? "cr-up" : "cr-down"}">${profit >= 0 ? "+" : ""}${pbMoney(profit)}</b><span>Profit</span></div><div><b>${risk ? (roi >= 0 ? "+" : "") + (roi * 100).toFixed(1) + "%" : "—"}</b><span>Return on risk</span></div><div><b>${open.length}</b><span>Open</span></div></div>
    ${byKind.length > 1 ? `<div class="cr-rec-kinds">${byKind.join("")}</div>` : ""}
    ${open.length ? `<div class="lbl">Open</div><ul class="cr-rec-list">${open.slice().reverse().slice(0, 6).map(row).join("")}</ul>` : ""}
    ${done.length ? `<div class="lbl">Settled</div><ul class="cr-rec-list">${done.slice().reverse().slice(0, 5).map(row).join("")}</ul>${done.length > 5 ? `<a class="subn" href="#bets" data-jump="bets">${done.length - 5} more in My bets</a>` : ""}` : ""}
    <p class="subn">Only tickets you save count, graded from the final scores. Player prop legs are marked by hand in My bets. Kept in this browser.</p>
  </div>`;
}
function createRefine(k) {
  const st = window.__crState;
  if (!st) return;
  const w = Object.assign({}, st.want, { teams: st.want.teams.slice(), players: st.want.players.slice(), kinds: st.want.kinds ? new Set(st.want.kinds) : null });
  const best = st.res && st.res.tickets && st.res.tickets[0];
  if (k === "safer") { w.mode = "safe"; w.target = null; }
  else if (k === "bigger") { w.mode = "target"; w.target = Math.max(3, (best ? best.x.r.decEff : (w.target || 4)) * 2); }
  else if (k === "more") { w.legs = Math.min(6, w.legs + 1); if (w.target) w.target = w.target * 1.9; }
  else if (k === "fewer") { w.legs = Math.max(2, w.legs - 1); if (w.target) w.target = Math.max(1.5, w.target / 1.9); }
  else if (k === "value") { w.mode = "value"; w.target = null; }
  else if (k === "nfl" || k === "cfb") { w.league = k; w.teams = w.teams.filter((t) => t.league === k); }
  else if (k === "noprops") { w.kinds = w.kinds || new Set(["sp", "tot", "ml", "pp"]); w.kinds.delete("pp"); w.players = []; }
  createShow(w);
  const o = document.getElementById("createOut");
  if (o) o.scrollIntoView({ behavior: "smooth", block: "start" });
}
function createSwap(spec) {
  const st = window.__crState;
  const [ti, wi, nid] = String(spec).split("|").length > 3 ? (() => { const p = String(spec).split("|"); return [p[0], p[1], p.slice(2).join("|")]; })() : String(spec).split("|");
  const t = st && st.res && st.res.tickets[Number(ti)];
  const alt = st && st.res.pool.find((l) => l.id === nid);
  if (!t || !alt) return;
  if (st.check) { st.ids[Number(wi)] = alt.id; createCheckRender(); return; }
  const bag = t.bag.slice();
  bag[Number(wi)] = alt;
  const x = createPrice(bag.map((l) => l.id));
  if (!x) return;
  st.res.tickets[Number(ti)] = { bag, x, s: t.s, swapped: true };
  const card = document.querySelector(`.cr-ticket[data-cri="${Number(ti)}"]`);
  if (card) card.outerHTML = createTicketHtml(st.res.tickets[Number(ti)], Number(ti));
}
// ==== Bet sizing =========================================================================
// A suggested stake in units (1 unit = 1% of your bankroll): a quarter of the Kelly stake for
// our checked chance at this price, in quarter units, capped at 2 units for a single bet and
// 1 for a parlay (the biggest disagreements with the books are where a model is most often wrong). Full Kelly swings too hard for chances this uncertain; a quarter keeps most of
// the growth with far smaller drawdowns. No edge at the price means no bet.

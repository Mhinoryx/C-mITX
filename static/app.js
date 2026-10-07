"use strict";
const $ = (id) => document.getElementById(id);
let game = null, busy = false, byProximity = true, latestWord = null, refreshing = false;
const format = (n) => n.toLocaleString("fr-FR", {minimumFractionDigits: 2, maximumFractionDigits: 2});
const emoji = (a) => a.won ? "🎯" : a.progress >= 990 ? "🔥" : a.progress >= 900 ? "🥵" : a.progress ? "😎" : a.temperature < 0 ? "🧊" : "🥶";
function message(text = "", error = false) {
  $("message").textContent = text;
  $("message").classList.toggle("error", error);
}
function controls() {
  const disabled = busy || !game || game.won;
  $("word").disabled = disabled;
  $("submit-button").disabled = disabled;
  $("submit-button").textContent = busy ? "Calcul…" : "Proposer ↗";
}
async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {"Content-Type": "application/json", ...options.headers}});
  if (!(response.headers.get("Content-Type") || "").includes("application/json")) {
    throw new Error("Le serveur de jeu n’est pas configuré sur ce site. L’interface est disponible, mais les parties nécessitent le serveur Python.");
  }
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error || "Le serveur ne répond pas. Réessayez.");
    error.refresh = data.refresh;
    throw error;
  }
  return data;
}
function cell(row, text) {
  const el = document.createElement("td");
  el.textContent = text;
  row.append(el);
  return el;
}
function render() {
  if (!game) return;
  $("day-label").textContent = new Intl.DateTimeFormat("fr-FR", {day: "numeric", month: "long", year: "numeric", timeZone: "Europe/Paris"}).format(new Date(game.day + "T12:00:00+02:00"));
  $("attempt-count").textContent = game.attempts.length;
  $("solved-count").textContent = game.solved;
  if (game.thresholds) for (const rank of [1, 900, 990]) if (game.thresholds[rank] !== undefined) $("threshold-" + rank).textContent = format(game.thresholds[rank]) + " °C";
  const rows = [...game.attempts].sort(byProximity ? (a, b) => b.temperature - a.temperature || b.number - a.number : (a, b) => b.number - a.number);
  $("attempts").replaceChildren();
  for (const a of rows) {
    const row = document.createElement("tr");
    row.classList.toggle("latest", a.word === latestWord);
    row.classList.toggle("found", a.won);
    cell(row, a.number);
    cell(row, a.word);
    const temperature = cell(row, format(a.temperature));
    temperature.style.color = a.won ? "#456b4e" : a.progress >= 900 ? "#be6143" : a.progress ? "#7b8c4a" : "#688998";
    const heat = cell(row, "");
    const wrap = document.createElement("div");
    wrap.className = "heat";
    const icon = document.createElement("span");
    icon.className = "heat-emoji";
    icon.textContent = emoji(a);
    wrap.append(icon);
    if (a.progress) {
      const track = document.createElement("div");
      track.className = "progress-track";
      const bar = document.createElement("span");
      bar.className = "progress-bar";
      bar.style.width = a.progress / 10 + "%";
      track.append(bar);
      wrap.append(track);
    }
    const rank = document.createElement("span");
    rank.className = "rank";
    rank.textContent = a.progress ? a.progress + " ‰" : "—";
    wrap.append(rank);
    heat.append(wrap);
    $("attempts").append(row);
  }
  $("empty-state").hidden = rows.length > 0;
  $("victory").hidden = !game.won;
  if (game.won) {
    const found = game.attempts.find(a => a.won);
    $("victory-text").textContent = `Le mot était « ${found.word} ». ${game.attempts.length} essai${game.attempts.length > 1 ? "s" : ""} et ${game.position === 1 ? "1re" : game.position + "e"} découverte du jour.`;
  }
  controls();
  tick();
}
async function loadGame() {
  if (refreshing || busy) return;
  refreshing = true;
  try {
    game = await api("/api/game");
    render();
    message();
  } catch (error) { message(error.message, true); }
  finally { refreshing = false; controls(); }
}
$("guess-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const word = $("word").value.trim();
  if (!word || busy || refreshing || !game || game.won) return;
  busy = true;
  controls();
  message();
  let refresh = false;
  try {
    const result = await api("/api/guess", {method: "POST", body: JSON.stringify({word, day: game.day})});
    latestWord = result.last_word;
    game = {...game, ...result};
    $("word").value = "";
    render();
    message(result.duplicate ? "Vous avez déjà proposé ce mot. Il est surligné dans la liste." : "");
  } catch (error) {
    message(error.message, true);
    refresh = !!error.refresh;
  } finally {
    busy = false;
    controls();
    if (refresh) await loadGame();
    if (!game?.won) $("word").focus();
  }
});
$("sort-button").addEventListener("click", () => {
  byProximity = !byProximity;
  $("sort-button").textContent = byProximity ? "Par proximité ↓" : "Derniers essais ↓";
  render();
});
$("help-button").addEventListener("click", () => $("rules-dialog").showModal());
for (const id of ["close-rules", "start-button"]) $(id).addEventListener("click", () => {$("rules-dialog").close(); if (game && !game.won) $("word").focus();});
$("rules-dialog").addEventListener("click", (event) => {
  if (event.target === $("rules-dialog")) {
    const r = event.target.getBoundingClientRect();
    if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) event.target.close();
  }
});
$("share-button").addEventListener("click", async () => {
  const text = `Cémentix · ${game.day}\n🎯 Trouvé en ${game.attempts.length} essais\n🏆 ${game.position === 1 ? "1re" : game.position + "e"} découverte du jour\n${game.attempts.slice(-8).map(emoji).join("")}`;
  try {
    await navigator.clipboard.writeText(text);
    $("share-button").textContent = "Résultat copié ✓";
    setTimeout(() => {$("share-button").textContent = "Copier mon résultat ↗";}, 2500);
  } catch { message("La copie automatique est indisponible dans ce navigateur.", true); }
});
function tick() {
  if (!game) return;
  const seconds = Math.max(0, Math.ceil((Date.parse(game.next_at) - Date.now()) / 1000));
  $("countdown").textContent = [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, seconds % 60].map(x => String(x).padStart(2, "0")).join(":");
  if (seconds === 0 && !busy && !refreshing) loadGame();
}
setInterval(tick, 1000);
setInterval(() => {if (!busy && document.visibilityState === "visible") loadGame();}, 60000);
document.addEventListener("visibilitychange", () => {if (document.visibilityState === "visible") loadGame();});
loadGame();

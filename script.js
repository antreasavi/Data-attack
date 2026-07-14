const COLORS = ["red-soft", "red-strong", "orange", "blue-strong", "blue-soft"];
const MIN_DELAY_MS = 5000;
const MAX_DELAY_MS = 30000;
const WRONG_PENALTY = 20;

const dropzone = document.getElementById("dropzone");
const dropEl = document.getElementById("drop");
const messageEl = document.getElementById("message");
const boxes = Array.from(document.querySelectorAll(".box"));
const startPoint = document.getElementById("startPoint");
const startBtn = document.getElementById("startBtn");
const resetBtn = document.getElementById("resetBtn");
const logList = document.getElementById("logList");

const scoreEl = document.getElementById("score");
const streakEl = document.getElementById("streak");
const missesEl = document.getElementById("misses");
const lastTimeEl = document.getElementById("lastTime");
const bestTimeEl = document.getElementById("bestTime");
const avgTimeEl = document.getElementById("avgTime");

let running = false;
let scheduleTimer = null;
let activeColor = null;
let dropStartTime = null;
let hitBoxIds = new Set();

let score = 0;
let streak = 0;
let misses = 0;
let bestMs = null;
let correctTimes = [];

function randomDelay() {
  return MIN_DELAY_MS + Math.random() * (MAX_DELAY_MS - MIN_DELAY_MS);
}

function formatMs(ms) {
  if (ms == null) return "-";
  return ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(2)}s`;
}

function updateStats() {
  scoreEl.textContent = score;
  streakEl.textContent = streak;
  missesEl.textContent = misses;
  bestTimeEl.textContent = formatMs(bestMs);
  const avg = correctTimes.length
    ? correctTimes.reduce((a, b) => a + b, 0) / correctTimes.length
    : null;
  avgTimeEl.textContent = formatMs(avg);
}

function setBoxesEnabled(enabled) {
  boxes.forEach((b) => b.classList.toggle("enabled", enabled));
}

function addLog(text, cls) {
  const li = document.createElement("li");
  li.textContent = text;
  li.className = cls;
  logList.prepend(li);
}

function scheduleNextDrop() {
  scheduleTimer = setTimeout(showDrop, randomDelay());
}

function showDrop() {
  if (!running) return;
  activeColor = COLORS[Math.floor(Math.random() * COLORS.length)];
  const zoneW = dropzone.clientWidth;
  const zoneH = dropzone.clientHeight;
  const size = 64;
  const left = Math.random() * (zoneW - size - 20) + 10;
  const landingY = Math.random() * (zoneH - size - 80) + 40;

  messageEl.hidden = true;
  dropEl.hidden = false;
  dropEl.className = `drop ${activeColor}`;
  dropEl.style.left = `${left}px`;
  dropEl.style.setProperty("--landing-y", `${landingY}px`);
  dropEl.style.animation = "none";
  void dropEl.offsetHeight;
  dropEl.style.animation = "";

  setBoxesEnabled(true);
  hitBoxIds = new Set();
  dropStartTime = performance.now();
}

function colorFamily(color) {
  return color === "orange" ? "orange" : color.split("-")[0];
}

function requiredBoxIds(color) {
  if (color === "orange") return ["box-orange"];
  const family = colorFamily(color);
  return family === "red" ? ["box-red-1", "box-red-2"] : ["box-blue-1", "box-blue-2"];
}

function finishRound() {
  activeColor = null;
  hitBoxIds = new Set();
  dropEl.hidden = true;
  setBoxesEnabled(false);
  messageEl.hidden = false;
  messageEl.textContent = "Watch this area...";
  scheduleNextDrop();
}

function handleCorrect(box) {
  const reactionMs = performance.now() - dropStartTime;
  const points = Math.max(0, Math.round(100 - reactionMs / 20));
  score += points;
  streak += 1;
  correctTimes.push(reactionMs);
  if (bestMs === null || reactionMs < bestMs) bestMs = reactionMs;
  lastTimeEl.textContent = formatMs(reactionMs);
  addLog(`${activeColor} matched in ${formatMs(reactionMs)} (+${points})`, "correct");
  requiredBoxIds(activeColor).forEach((id) => {
    const b = document.getElementById(id);
    b.classList.add("flash-correct");
    setTimeout(() => b.classList.remove("flash-correct"), 250);
  });
  updateStats();
  finishRound();
}

function handleWrong(box, clickedFamily) {
  const reactionMs = performance.now() - dropStartTime;
  score -= WRONG_PENALTY;
  streak = 0;
  misses += 1;
  lastTimeEl.textContent = formatMs(reactionMs);
  addLog(`${activeColor} missed, clicked ${clickedFamily} (-${WRONG_PENALTY})`, "wrong");
  box.classList.add("flash-wrong");
  setTimeout(() => box.classList.remove("flash-wrong"), 250);
  updateStats();
  finishRound();
}

function handleBoxClick(box) {
  if (!running || activeColor === null) return;
  const clickedFamily = box.dataset.family;
  const activeFamily = colorFamily(activeColor);

  if (clickedFamily !== activeFamily) {
    handleWrong(box, clickedFamily);
    return;
  }

  if (activeColor === "orange" || !activeColor.endsWith("strong")) {
    handleCorrect(box);
    return;
  }

  hitBoxIds.add(box.id);
  const required = requiredBoxIds(activeColor);
  if (required.every((id) => hitBoxIds.has(id))) {
    handleCorrect(box);
  } else {
    box.classList.add("flash-partial");
    setTimeout(() => box.classList.remove("flash-partial"), 250);
  }
}

boxes.forEach((box) => {
  box.addEventListener("click", () => handleBoxClick(box));
});

startBtn.addEventListener("click", () => {
  if (running) {
    stopGame();
  } else {
    startGame();
  }
});

resetBtn.addEventListener("click", resetGame);

startPoint.addEventListener("mouseenter", () => {
  startPoint.classList.add("armed");
  if (!running) startGame();
});

startPoint.addEventListener("mouseleave", () => {
  startPoint.classList.remove("armed");
});

function startGame() {
  running = true;
  startBtn.textContent = "Stop";
  messageEl.hidden = false;
  messageEl.textContent = "Watch this area...";
  scheduleNextDrop();
}

function stopGame() {
  running = false;
  startBtn.textContent = "Start";
  clearTimeout(scheduleTimer);
  activeColor = null;
  hitBoxIds = new Set();
  dropEl.hidden = true;
  setBoxesEnabled(false);
  messageEl.hidden = false;
  messageEl.textContent = "Paused. Press Start to resume.";
}

function resetGame() {
  stopGame();
  score = 0;
  streak = 0;
  misses = 0;
  bestMs = null;
  correctTimes = [];
  logList.innerHTML = "";
  lastTimeEl.textContent = "-";
  updateStats();
  messageEl.textContent = "Press Start, then watch this area";
}

updateStats();

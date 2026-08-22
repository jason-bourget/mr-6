/* Mr 6 — Knight of Numbers · game logic */
(() => {
  "use strict";

  const QUEST_LENGTH = 5;
  const MAX_HEARTS = 3;
  const SEEN_KEY = "mr6-seen-v1";

  const $ = (id) => document.getElementById(id);

  /* ---------------- inline icons (Storybook Light) ---------------- */

  const HEART_PATH = "M12 20.5C6.5 16.9 3.5 13.4 3.5 9.9 3.5 7.4 5.4 5.5 7.9 5.5c1.6 0 3.1.8 4.1 2.1 1-1.3 2.5-2.1 4.1-2.1 2.5 0 4.4 1.9 4.4 4.4 0 3.5-3 7-8.5 10.6z";
  const heartFull = `<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="${HEART_PATH}"/></svg>`;
  const heartEmpty = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="${HEART_PATH}"/></svg>`;
  const starIcon = (size) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.5l2.9 5.9 6.5.9-4.7 4.6 1.1 6.5-5.8-3-5.8 3 1.1-6.5L2.6 9.3l6.5-.9z"/></svg>`;
  const crownIcon = `<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18h18"/><path d="M4 17l-1.2-8.5L8.5 12 12 5l3.5 7 5.7-3.5L20 17z"/></svg>`;
  const moonIcon = `<svg width="48" height="48" viewBox="0 0 24 24" fill="currentColor"><path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"/></svg>`;

  const state = {
    problems: [],       // all loaded problems
    tier: null,
    quest: [],          // problems for the current quest
    index: 0,           // current battle index
    hearts: MAX_HEARTS,
    missesThisBattle: 0,
    solved: 0,
  };

  /* ---------------- content loading ---------------- */

  async function loadContent() {
    // no-cache so phones pick up each day's new adventures on next open
    const manifest = await (await fetch("content/manifest.json", { cache: "no-cache" })).json();
    const results = await Promise.allSettled(
      manifest.problems.map((p) => fetch("content/" + p).then((r) => r.json()))
    );
    state.problems = results
      .filter((r) => r.status === "fulfilled")
      .map((r) => r.value)
      .filter((p) => p && p.id && typeof p.answer === "number")
      .filter((p) => p.tier === "champion"); // single-level launch: ages 10-13

    $("pool-status").textContent =
      `${state.problems.length} adventures await · new ones forged daily`;
  }

  /* ---------------- seen-problem tracking ---------------- */

  function getSeen() {
    try { return new Set(JSON.parse(localStorage.getItem(SEEN_KEY) || "[]")); }
    catch { return new Set(); }
  }
  function markSeen(id) {
    const seen = getSeen();
    seen.add(id);
    localStorage.setItem(SEEN_KEY, JSON.stringify([...seen]));
  }

  /* ---------------- quest setup ---------------- */

  function shuffle(arr) {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  function buildQuest() {
    const pool = state.problems;
    const seen = getSeen();
    const fresh = shuffle(pool.filter((p) => !seen.has(p.id)));
    const old = shuffle(pool.filter((p) => seen.has(p.id)));
    const quest = fresh.concat(old).slice(0, QUEST_LENGTH);
    // If the whole pool has been seen, clear tier's history so it stays fresh-ish
    if (fresh.length === 0 && pool.length > 0) {
      const remaining = [...seen].filter((id) => !pool.some((p) => p.id === id));
      localStorage.setItem(SEEN_KEY, JSON.stringify(remaining));
    }
    return shuffle(quest);
  }

  function startQuest() {
    state.quest = buildQuest();
    state.index = 0;
    state.hearts = MAX_HEARTS;
    state.solved = 0;
    if (state.quest.length === 0) {
      alert("No adventures found for this path yet — generate some with the story forge!");
      return;
    }
    showScreen("screen-battle");
    renderBattle();
  }

  /* ---------------- battle rendering ---------------- */

  function showScreen(id) {
    document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
    $(id).classList.add("active");
    window.scrollTo({ top: 0 });
  }

  function renderHearts() {
    $("hearts").innerHTML = Array.from({ length: MAX_HEARTS }, (_, i) =>
      i < state.hearts ? heartFull : heartEmpty
    ).join("");
  }

  function renderProgress() {
    $("quest-progress").innerHTML = state.quest.map((_, i) => {
      const cls = i < state.index ? "pip done" : i === state.index ? "pip current" : "pip";
      return `<span class="${cls}"></span>`;
    }).join("");
  }

  function renderBattle() {
    const p = state.quest[state.index];
    state.missesThisBattle = 0;

    renderHearts();
    renderProgress();

    const img = $("battle-image");
    img.src = "content/" + (p.image || "images/placeholder.svg");
    img.onerror = () => { img.onerror = null; img.src = "content/images/placeholder.svg"; };

    $("monster-banner").textContent = p.monster || "A mysterious foe";
    $("battle-title").textContent = p.title;
    $("battle-text").textContent = p.story;
    $("battle-question").textContent = p.question;

    const choicesEl = $("choices");
    choicesEl.innerHTML = "";
    for (const value of buildChoices(p)) {
      const btn = document.createElement("button");
      btn.className = "choice-btn";
      btn.textContent = p.unit ? `${value} ${p.unit}` : String(value);
      btn.addEventListener("click", () => pickChoice(p, value, btn));
      choicesEl.appendChild(btn);
    }

    $("feedback").textContent = "";
    $("feedback").className = "feedback";
    $("hint-box").hidden = true;
    $("hint-text").textContent = p.hint || "";

    $("victory-panel").hidden = true;
    $("answer-area").hidden = false;
  }

  /* ---------------- choices ---------------- */

  function buildChoices(p) {
    const opts = new Set([p.answer]);
    for (const d of p.distractors || []) {
      if (opts.size >= 4) break;
      if (typeof d === "number" && isFinite(d) && Math.abs(d - p.answer) > 0.0001) opts.add(d);
    }
    // Fallback filler for problems without hand-made distractors
    const fillers = [p.answer + 1, p.answer - 1, p.answer * 2, Math.round(p.answer / 2), p.answer + 10];
    for (const f of fillers) {
      if (opts.size >= 4) break;
      if (isFinite(f) && f >= 0 && Math.abs(f - p.answer) > 0.0001 && !opts.has(f)) opts.add(f);
    }
    return shuffle([...opts]);
  }

  /* ---------------- answer handling ---------------- */

  const ENCOURAGE = [
    "So close — steady your sword and try again!",
    "The monster dodged! Take a breath and have another go.",
    "Not quite — even brave knights need two tries.",
  ];

  function pickChoice(p, value, btn) {
    if (btn.disabled || !$("victory-panel").hidden) return;
    const correct = Math.abs(value - p.answer) < 0.001;

    if (correct) {
      btn.classList.add("right");
      document.querySelectorAll(".choice-btn").forEach((b) => (b.disabled = true));
      markSeen(p.id);
      state.solved++;
      setTimeout(() => showVictory(p), 350);
    } else {
      btn.classList.add("wrong");
      btn.disabled = true;
      state.missesThisBattle++;
      state.hearts--;
      renderHearts();
      const card = document.querySelector(".battle-card");
      card.classList.remove("hit");
      void card.offsetWidth; // restart animation
      card.classList.add("hit");

      if (state.hearts <= 0) {
        setTimeout(() => endQuest(false, p), 700);
        return;
      }
      $("feedback").textContent = ENCOURAGE[Math.min(state.missesThisBattle - 1, ENCOURAGE.length - 1)];
      $("feedback").className = "feedback miss";
      $("hint-box").hidden = !p.hint;
    }
  }

  function showVictory(p) {
    $("answer-area").hidden = true;
    $("victory-panel").hidden = false;
    $("victory-heading").textContent =
      state.index + 1 === state.quest.length ? "The Final Blow!" : "Victory!";
    $("victory-text").textContent =
      `The answer was ${p.answer} ${p.unit || ""}. `.trimEnd() + " — " + (p.victory || "The monster is defeated!");
    $("btn-next").textContent =
      state.index + 1 === state.quest.length ? "Claim your triumph" : "Onward";
    renderProgress();
  }

  function nextBattle() {
    state.index++;
    if (state.index >= state.quest.length) {
      endQuest(true);
    } else {
      renderBattle();
    }
  }

  /* ---------------- quest end ---------------- */

  function endQuest(won, failedProblem) {
    showScreen("screen-summary");
    const stars = won ? state.hearts : 0;

    if (won) {
      $("summary-emblem").innerHTML = stars === 3 ? crownIcon : starIcon(48);
      $("summary-title").textContent = stars === 3 ? "Flawless Quest!" : "Quest Complete!";
      $("summary-stars").innerHTML =
        Array.from({ length: MAX_HEARTS }, (_, i) =>
          `<span class="${i < stars ? "" : "dim"}">${starIcon(32)}</span>`).join("");
      $("summary-text").textContent =
        stars === 3
          ? `Mr 6 didn't take a single scratch! ${state.solved} monsters bested, the realm rejoices, and the bards are already writing songs about you.`
          : `Mr 6 triumphed over ${state.solved} monsters! A few bruises, a lot of glory — the village feast is in your honor tonight.`;
    } else {
      $("summary-emblem").innerHTML = moonIcon;
      $("summary-title").textContent = "A Knight's Rest";
      $("summary-stars").innerHTML = "";
      $("summary-text").textContent =
        (failedProblem
          ? `The answer to "${failedProblem.title}" was ${failedProblem.answer} ${failedProblem.unit || ""}. `
          : "") +
        `Mr 6 retreats to the castle to bandage his bruises and sharpen his mind. ` +
        `You defeated ${state.solved} monster${state.solved === 1 ? "" : "s"} — every great knight trains again tomorrow!`;
    }
  }

  /* ---------------- wire up ---------------- */

  $("start-quest").addEventListener("click", () => startQuest());

  $("btn-next").addEventListener("click", nextBattle);
  $("btn-flee").addEventListener("click", () => showScreen("screen-title"));
  $("btn-again").addEventListener("click", () => startQuest());
  $("btn-home").addEventListener("click", () => showScreen("screen-title"));

  loadContent().catch((err) => {
    $("pool-status").textContent =
      "Could not load adventures — run the game with `python -m http.server 8123` from the project folder (see README).";
    console.error(err);
  });
})();

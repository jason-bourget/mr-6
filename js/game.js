/* Mr 6 — Knight of Numbers · daily quest logic
   One quest of 10 per day. One pick per problem. Score at the end. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const resultKey = (date) => `mr6-result-${date}`;

  /* ---------------- inline icons (Storybook Light) ---------------- */

  const starIcon = (size) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.5l2.9 5.9 6.5.9-4.7 4.6 1.1 6.5-5.8-3-5.8 3 1.1-6.5L2.6 9.3l6.5-.9z"/></svg>`;
  const checkIcon = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7"/></svg>`;
  const crossIcon = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l12 12M18 6L6 18"/></svg>`;
  const crownSmall = `<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18h18"/><path d="M4 17l-1.2-8.5L8.5 12 12 5l3.5 7 5.7-3.5L20 17z"/></svg>`;
  const crownIcon = `<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18h18"/><path d="M4 17l-1.2-8.5L8.5 12 12 5l3.5 7 5.7-3.5L20 17z"/></svg>`;
  const shieldIcon = `<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l7 3.2v5.1c0 4.4-2.9 7.8-7 9.7-4.1-1.9-7-5.3-7-9.7V6.2z"/></svg>`;

  const state = {
    date: null,
    problems: [],   // today's 10, in order
    index: 0,
    score: 0,
    picks: [],      // {id, correct}
  };

  /* ---------------- content loading ---------------- */

  async function loadContent() {
    // no-cache so phones pick up each morning's new quest on next open
    const index = await (await fetch("content/days/index.json", { cache: "no-cache" })).json();
    const latest = index.days[index.days.length - 1];
    const day = await (await fetch(`content/days/${latest}.json`, { cache: "no-cache" })).json();
    const results = await Promise.allSettled(
      day.problems.map((p) => fetch("content/" + p, { cache: "no-cache" }).then((r) => r.json()))
    );
    state.date = day.date;
    state.problems = results
      .filter((r) => r.status === "fulfilled")
      .map((r) => r.value)
      .filter((p) => p && p.id && typeof p.answer === "number");

    $("pool-status").textContent = "Ten fresh adventures every morning";
    if (savedResult()) {
      $("start-quest").textContent = "See Today's Result";
    }
  }

  function savedResult() {
    try { return JSON.parse(localStorage.getItem(resultKey(state.date))); }
    catch { return null; }
  }

  /* ---------------- quest flow ---------------- */

  function showScreen(id) {
    document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
    $(id).classList.add("active");
    window.scrollTo({ top: 0 });
  }

  function startQuest() {
    const saved = savedResult();
    if (saved) { showSummary(saved.score); return; }
    if (state.problems.length === 0) {
      $("pool-status").textContent = "Today's quest could not be loaded — try again in a moment.";
      return;
    }
    state.index = 0;
    state.score = 0;
    state.picks = [];
    showScreen("screen-battle");
    renderBattle();
  }

  function renderProgress() {
    $("battle-count").textContent = `Battle ${Math.min(state.index + 1, state.problems.length)} of ${state.problems.length}`;
    const connector = '<span class="road-line"></span>';
    const nodes = state.problems.map((_, i) => {
      const pick = state.picks[i];
      if (pick && pick.correct) return `<span class="road-node done">${checkIcon}</span>`;
      if (pick) return `<span class="road-node miss">${crossIcon}</span>`;
      if (i === state.index) return `<span class="road-node current">${i + 1}</span>`;
      return '<span class="road-node todo"></span>';
    });
    $("quest-road").innerHTML =
      nodes.join(connector) + connector + `<span class="road-crown">${crownSmall}</span>`;
  }

  function renderBattle() {
    const p = state.problems[state.index];
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
      btn.dataset.value = String(value);
      btn.textContent = p.unit ? `${value} ${p.unit}` : String(value);
      btn.addEventListener("click", () => pickChoice(p, value, btn));
      choicesEl.appendChild(btn);
    }

    $("btn-hint").hidden = !p.hint;
    $("hint-box").hidden = true;
    $("hint-text").textContent = p.hint || "";
    $("feedback").textContent = "";
    $("feedback").className = "feedback";

    $("victory-panel").hidden = true;
    $("answer-area").hidden = false;
  }

  /* ---------------- choices ---------------- */

  function shuffle(arr) {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  function buildChoices(p) {
    const opts = new Set([p.answer]);
    for (const d of p.distractors || []) {
      if (opts.size >= 4) break;
      if (typeof d === "number" && isFinite(d) && Math.abs(d - p.answer) > 0.0001) opts.add(d);
    }
    const fillers = [p.answer + 1, p.answer - 1, p.answer * 2, Math.round(p.answer / 2), p.answer + 10];
    for (const f of fillers) {
      if (opts.size >= 4) break;
      if (isFinite(f) && f >= 0 && Math.abs(f - p.answer) > 0.0001 && !opts.has(f)) opts.add(f);
    }
    return shuffle([...opts]);
  }

  function pickChoice(p, value, btn) {
    if (btn.disabled) return;
    const correct = Math.abs(value - p.answer) < 0.001;

    document.querySelectorAll(".choice-btn").forEach((b) => {
      b.disabled = true;
      if (Math.abs(parseFloat(b.dataset.value) - p.answer) < 0.001) b.classList.add("right");
    });
    if (!correct) btn.classList.add("wrong");

    state.picks.push({ id: p.id, correct });
    if (correct) state.score++;
    renderProgress();

    setTimeout(() => showStory(p, correct), 500);
  }

  function showStory(p, correct) {
    $("answer-area").hidden = true;
    $("victory-panel").hidden = false;
    $("victory-heading").textContent = correct ? "Victory!" : "Outfoxed!";
    $("victory-panel").classList.toggle("missed", !correct);

    const praise = $("victory-praise");
    praise.hidden = correct || !p.praise;
    praise.textContent = p.praise || "";

    const hasSolution = Array.isArray(p.solution) && p.solution.length > 0;
    $("solution-box").hidden = !hasSolution;
    if (hasSolution) {
      $("solution-steps").innerHTML = p.solution.map((step, i) =>
        `<div class="solution-step"><span class="step-num">${i + 1}</span><span>${escapeHtml(step)}</span></div>`
      ).join("");
    }

    $("victory-text").textContent =
      (hasSolution ? "" : `The answer was ${p.answer} ${p.unit || ""}. — `.replace(" . ", ". ")) +
      (p.victory || "The monster is defeated!");
    $("btn-next").textContent =
      state.index + 1 === state.problems.length ? "See your score" : "Onward";
  }

  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function nextBattle() {
    state.index++;
    if (state.index >= state.problems.length) {
      finishQuest();
    } else {
      renderBattle();
    }
  }

  /* ---------------- results ---------------- */

  function finishQuest() {
    localStorage.setItem(resultKey(state.date),
      JSON.stringify({ score: state.score, picks: state.picks }));
    $("start-quest").textContent = "See Today's Result";
    showSummary(state.score);
  }

  function showSummary(score) {
    showScreen("screen-summary");
    const total = state.problems.length || 10;

    let emblem, title, text;
    if (score === total) {
      emblem = crownIcon; title = "Flawless Quest!";
      text = "Every single monster out-thought. The bards are tuning their lutes — this day will be sung about.";
    } else if (score >= 7) {
      emblem = starIcon(48); title = "Quest Complete!";
      text = "A mighty showing. The realm sleeps safely tonight, and the wise owl nods with approval.";
    } else if (score >= 4) {
      emblem = starIcon(48); title = "A Good Fight!";
      text = "Some monsters slipped away this time — but every battle taught Mr 6 something. Tomorrow's quest awaits.";
    } else {
      emblem = shieldIcon; title = "The Owl Believes in You";
      text = "A hard day on the quest trail. Read the hints, trust the steps, and come back swinging tomorrow.";
    }

    $("summary-emblem").innerHTML = emblem;
    $("summary-title").textContent = title;
    $("summary-score").textContent = `${score} / ${total}`;
    $("summary-text").textContent = text + " A new quest arrives every morning.";
  }

  /* ---------------- wire up ---------------- */

  $("start-quest").addEventListener("click", startQuest);
  $("btn-hint").addEventListener("click", () => {
    $("hint-box").hidden = false;
    $("btn-hint").hidden = true;
  });
  $("btn-next").addEventListener("click", nextBattle);
  $("btn-flee").addEventListener("click", () => showScreen("screen-title"));
  $("btn-home").addEventListener("click", () => showScreen("screen-title"));

  loadContent().catch((err) => {
    $("pool-status").textContent =
      "Could not load today's quest — check your connection and refresh.";
    console.error(err);
  });
})();

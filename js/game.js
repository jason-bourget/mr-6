/* Mr 6 — Knight of Numbers · daily quest logic
   One quest of 10 per day. One pick per problem. Score at the end. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const resultKey = (date) => `mr6-result-${date}`;
  const rapidKey = (date) => `mr6-rapid-${date}`;

  /* ---------------- inline icons (Storybook Light) ---------------- */

  const starIcon = (size) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.5l2.9 5.9 6.5.9-4.7 4.6 1.1 6.5-5.8-3-5.8 3 1.1-6.5L2.6 9.3l6.5-.9z"/></svg>`;
  const checkIcon = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7"/></svg>`;
  const crossIcon = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l12 12M18 6L6 18"/></svg>`;
  const crownSmall = `<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18h18"/><path d="M4 17l-1.2-8.5L8.5 12 12 5l3.5 7 5.7-3.5L20 17z"/></svg>`;
  const crownIcon = `<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18h18"/><path d="M4 17l-1.2-8.5L8.5 12 12 5l3.5 7 5.7-3.5L20 17z"/></svg>`;
  const shieldIcon = `<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l7 3.2v5.1c0 4.4-2.9 7.8-7 9.7-4.1-1.9-7-5.3-7-9.7V6.2z"/></svg>`;

  const state = {
    date: null,
    problems: [],   // today's thinkers, in order
    index: 0,
    score: 0,
    picks: [],      // {id, correct}
    lastMode: "quest",
    rapid: null,    // {date, image, problems}
    rapidIndex: 0,
    rapidScore: 0,
    rapidStart: 0,
    rapidTimer: null,
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

    // rapid fire day file (optional — mode hides if missing)
    try {
      const rIndex = await (await fetch("content/rapid/index.json", { cache: "no-cache" })).json();
      const rLatest = rIndex.days[rIndex.days.length - 1];
      state.rapid = await (await fetch(`content/rapid/${rLatest}.json`, { cache: "no-cache" })).json();
    } catch { state.rapid = null; }
    $("start-rapid").hidden = !state.rapid || !state.rapid.problems?.length;

    $("pool-status").textContent = "A fresh quest and rapid round every morning";
    updateModeStatuses();
  }

  function savedResult() {
    try { return JSON.parse(localStorage.getItem(resultKey(state.date))); }
    catch { return null; }
  }

  function savedRapid() {
    if (!state.rapid) return null;
    try { return JSON.parse(localStorage.getItem(rapidKey(state.rapid.date))); }
    catch { return null; }
  }

  function fmtTime(secs) {
    const m = Math.floor(secs / 60);
    const s = secs - m * 60;
    return `${m}:${s.toFixed(secs < 60 && m === 0 ? 1 : 0).padStart(m > 0 ? 2 : 1, "0")}`;
  }

  function updateModeStatuses() {
    const q = savedResult();
    $("quest-status").textContent = q
      ? `Best today: ${Math.min(q.best, state.problems.length)} / ${state.problems.length} · play again`
      : "Three thinkers · story battles";
    const r = savedRapid();
    $("rapid-status").textContent = r
      ? `Best today: ${r.score} / 10 in ${fmtTime(r.time)} · beat it`
      : "Ten quick strikes · race the clock";
  }

  /* ---------------- quest flow ---------------- */

  function showScreen(id) {
    document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
    $(id).classList.add("active");
    window.scrollTo({ top: 0 });
  }

  function startQuest() {
    if (state.problems.length === 0) {
      $("pool-status").textContent = "Today's quest could not be loaded — try again in a moment.";
      return;
    }
    state.lastMode = "quest";
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
    const prev = savedResult();
    const prevBest = Math.min(prev ? prev.best || 0 : 0, state.problems.length);
    const best = Math.max(state.score, prevBest);
    const bestPicks = state.score >= prevBest
      ? state.picks.map((p) => p.correct)
      : (prev && prev.bestPicks) || state.picks.map((p) => p.correct);
    localStorage.setItem(resultKey(state.date),
      JSON.stringify({ score: state.score, best, bestPicks, picks: state.picks }));
    updateModeStatuses();
    showSummary(state.score, best);
  }

  function showSummary(score, best) {
    showScreen("screen-summary");
    const total = state.problems.length || 3;
    const frac = score / total;

    let emblem, title, text;
    if (score === total) {
      emblem = crownIcon; title = "Flawless Quest!";
      text = "Every single monster out-thought. The bards are tuning their lutes — this day will be sung about.";
    } else if (frac >= 0.6) {
      emblem = starIcon(48); title = "Quest Complete!";
      text = "A mighty showing. The realm sleeps safely tonight, and the wise owl nods with approval.";
    } else {
      emblem = shieldIcon; title = "The Owl Believes in You";
      text = "These were true thinkers. Read the worked steps, then play again — beating a monster the second time still counts.";
    }

    $("summary-emblem").innerHTML = emblem;
    $("summary-title").textContent = title;
    $("summary-score").textContent = `${score} / ${total}`;
    $("summary-sub").textContent =
      best > score ? `Best today: ${best} / ${total}` : "";
    $("summary-text").textContent = text + " A new quest arrives every morning.";
    $("btn-again").textContent = "Play Again";
    renderShareScroll();
  }

  /* ---------------- rapid fire ---------------- */

  function startRapid() {
    if (!state.rapid) return;
    state.lastMode = "rapid";
    state.rapidIndex = 0;
    state.rapidScore = 0;
    state.rapidPattern = [];
    $("rapid-image").src = "content/" + (state.rapid.image || "images/placeholder.svg");
    showScreen("screen-rapid");
    state.rapidStart = performance.now();
    clearInterval(state.rapidTimer);
    state.rapidTimer = setInterval(() => {
      const secs = (performance.now() - state.rapidStart) / 1000;
      $("rapid-timer").textContent = fmtTime(secs);
    }, 100);
    renderRapid();
  }

  function stopRapidTimer() {
    clearInterval(state.rapidTimer);
    state.rapidTimer = null;
  }

  function renderRapid() {
    const p = state.rapid.problems[state.rapidIndex];
    $("rapid-count").textContent = `${state.rapidIndex + 1} of ${state.rapid.problems.length}`;
    $("rapid-question").textContent = p.q;
    const el = $("rapid-choices");
    el.innerHTML = "";
    for (const value of buildChoices(p)) {
      const btn = document.createElement("button");
      btn.className = "choice-btn rapid-choice";
      btn.dataset.value = String(value);
      btn.textContent = String(value);
      btn.addEventListener("click", () => pickRapid(p, value, btn));
      el.appendChild(btn);
    }
  }

  function pickRapid(p, value, btn) {
    if (btn.disabled) return;
    const correct = Math.abs(value - p.answer) < 0.001;
    document.querySelectorAll(".rapid-choice").forEach((b) => {
      b.disabled = true;
      if (Math.abs(parseFloat(b.dataset.value) - p.answer) < 0.001) b.classList.add("right");
    });
    if (!correct) btn.classList.add("wrong");
    if (correct) state.rapidScore++;
    state.rapidPattern.push(correct);
    setTimeout(() => {
      state.rapidIndex++;
      if (state.rapidIndex >= state.rapid.problems.length) finishRapid();
      else renderRapid();
    }, correct ? 350 : 700);
  }

  function finishRapid() {
    stopRapidTimer();
    const secs = Math.round((performance.now() - state.rapidStart) / 100) / 10;
    const prev = savedRapid();
    const better = !prev || state.rapidScore > prev.score ||
      (state.rapidScore === prev.score && secs < prev.time);
    if (better) {
      localStorage.setItem(rapidKey(state.rapid.date),
        JSON.stringify({ score: state.rapidScore, time: secs, pattern: state.rapidPattern }));
    }
    updateModeStatuses();
    showRapidSummary(state.rapidScore, secs, better, prev);
  }

  function showRapidSummary(score, secs, better, prev) {
    showScreen("screen-summary");
    const total = state.rapid.problems.length;
    const flawlessFast = score === total;
    $("summary-emblem").innerHTML = flawlessFast ? crownIcon : starIcon(48);
    $("summary-title").textContent =
      flawlessFast ? "Lightning Blade!" : score >= 7 ? "Quick Work!" : "Warming Up!";
    $("summary-score").textContent = `${score} / ${total}`;
    $("summary-sub").textContent =
      `in ${fmtTime(secs)}` +
      (better ? " · new best!" : prev ? ` · best: ${prev.score}/10 in ${fmtTime(prev.time)}` : "");
    $("summary-text").textContent =
      "Fast math is a muscle — every round makes it stronger. Race yourself again!";
    $("btn-again").textContent = "Race Again";
    renderShareScroll();
  }

  /* ---------------- share scroll ---------------- */

  function squarePattern(pattern, score, total) {
    if (Array.isArray(pattern) && pattern.length === total) return pattern;
    return Array.from({ length: total }, (_, i) => i < score);
  }

  function friendlyDate(iso) {
    const [y, m, d] = iso.split("-").map(Number);
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return `${months[m - 1]} ${d}`;
  }

  function shareData() {
    const rows = [];
    const q = savedResult();
    if (q) {
      const total = state.problems.length;
      const best = Math.min(q.best, total);
      rows.push({
        label: "Quest", score: `${best}/${total}`,
        pattern: squarePattern(q.bestPicks, best, total),
      });
    }
    const r = savedRapid();
    if (r) {
      rows.push({
        label: "Rapid", score: `${r.score}/10 in ${fmtTime(r.time)}`,
        pattern: squarePattern(r.pattern, r.score, 10),
      });
    }
    return rows;
  }

  function renderShareScroll() {
    const rows = shareData();
    const scroll = $("share-scroll");
    scroll.hidden = rows.length === 0;
    if (!rows.length) return;
    $("share-date").textContent = friendlyDate(state.date);
    $("share-rows").innerHTML = rows.map((row) => `
      <div class="share-row">
        <span class="share-label">${row.label}</span>
        <span class="share-squares">${row.pattern.map((ok) =>
          `<span class="sq ${ok ? "sq-hit" : "sq-miss"}"></span>`).join("")}</span>
        <span class="share-result">${row.score}</span>
      </div>`).join("");
    $("btn-share").textContent = "Share your scroll";
  }

  function shareText() {
    const rows = shareData();
    const lines = [`Mr 6 — Knight of Numbers · ${friendlyDate(state.date)}`];
    for (const row of rows) {
      const squares = row.pattern.map((ok) => (ok ? "🟨" : "⬜")).join("");
      lines.push(`${row.label}: ${squares} ${row.score}`);
    }
    lines.push("https://mr6.vercel.app");
    return lines.join("\n");
  }

  async function doShare() {
    const text = shareText();
    try {
      if (navigator.share) {
        await navigator.share({ text });
        return;
      }
    } catch { /* fall through to clipboard (e.g. user closed the sheet) */ return; }
    let copied = false;
    try {
      await navigator.clipboard.writeText(text);
      copied = true;
    } catch {
      // legacy fallback for browsers that deny the async clipboard
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { copied = document.execCommand("copy"); } catch { copied = false; }
      ta.remove();
    }
    if (copied) {
      $("btn-share").textContent = "Copied!";
      setTimeout(() => { $("btn-share").textContent = "Share your scroll"; }, 1600);
    } else {
      // last resort: show the text so it can be copied by hand
      let ta = document.getElementById("share-fallback");
      if (!ta) {
        ta = document.createElement("textarea");
        ta.id = "share-fallback";
        ta.className = "share-fallback";
        ta.readOnly = true;
        ta.rows = 4;
        $("share-scroll").appendChild(ta);
      }
      ta.value = text;
      ta.hidden = false;
      $("btn-share").textContent = "Select and copy your scroll:";
    }
  }

  /* ---------------- wire up ---------------- */

  $("start-quest").addEventListener("click", startQuest);
  $("start-rapid").addEventListener("click", startRapid);
  $("btn-hint").addEventListener("click", () => {
    $("hint-box").hidden = false;
    $("btn-hint").hidden = true;
  });
  $("btn-next").addEventListener("click", nextBattle);
  $("btn-flee").addEventListener("click", () => showScreen("screen-title"));
  $("btn-rapid-flee").addEventListener("click", () => {
    stopRapidTimer();
    showScreen("screen-title");
  });
  $("btn-again").addEventListener("click", () => {
    if (state.lastMode === "rapid") startRapid();
    else startQuest();
  });
  $("btn-share").addEventListener("click", doShare);
  $("btn-home").addEventListener("click", () => showScreen("screen-title"));

  loadContent().catch((err) => {
    $("pool-status").textContent =
      "Could not load today's quest — check your connection and refresh.";
    console.error(err);
  });
})();

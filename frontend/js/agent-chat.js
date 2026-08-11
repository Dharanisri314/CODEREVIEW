// ════════════════════════════════════════════
//  agent-chat.js  —  Code Review Agent
// ════════════════════════════════════════════

// const BACKEND_URL = "http://localhost:8000";
const BACKEND_URL = "";
const AGENT_ID    = "code_review";


// ── State ─────────────────────────────────────
let currentUser     = null;
let userInitial     = "U";
let sessionId       = "session_" + Date.now();
let reviewsCount    = 0;
let reviewCount     = 0;
let issuesCount     = 0;
const sessionStart  = Date.now();

// ── Stop / Abort state ────────────────────────
let abortController = null;
let isGenerating    = false;

// ── DOM Refs ──────────────────────────────────
const chatWindow = document.getElementById("chatWindow");
const chatInput  = document.getElementById("chatInput");
const sendBtn = document.getElementById("sendBtn");
const stopBtn = document.getElementById("stopBtn");


// Ensure correct initial idle state (stop hidden, send visible)
// Ensure correct initial idle state (stop hidden, send visible).
// Using setProperty(..., "important") so this wins even if agent-chat.css
// has a !important rule on .sc-stop-btn / .sc-send-btn.
if (stopBtn) stopBtn.style.setProperty("display", "none", "important");
if (sendBtn) sendBtn.style.setProperty("display", "flex", "important");


// ── Firestore ref helper ──────────────────────
function statsRef(uid) {
  return firebase.firestore().collection("codeReviews").doc(uid);
}


// ════════════════════════════════════════════
//  Button State Helpers
// ════════════════════════════════════════════
function showStopBtn() {
  isGenerating = true;
  if (sendBtn) sendBtn.style.setProperty("display", "none", "important");
  if (stopBtn) {
    stopBtn.style.setProperty("display", "flex", "important");
    stopBtn.style.alignItems   = "center";
    stopBtn.style.justifyContent = "center";
  }
}

function showSendBtn() {
  isGenerating    = false;
  abortController = null;
  if (stopBtn) stopBtn.style.setProperty("display", "none", "important");
  if (sendBtn) {
    sendBtn.style.setProperty("display", "flex", "important");
    sendBtn.disabled      = false;
  }
}


// ════════════════════════════════════════════
//  Auth Guard
// ════════════════════════════════════════════
firebase.auth().onAuthStateChanged(async (user) => {
  if (!user) { window.location.href = "index.html"; return; }

  currentUser = user;
  userInitial = (user.displayName || user.email || "U")[0].toUpperCase();

  document.querySelectorAll(".sc-msg-avatar--user")
    .forEach(el => el.textContent = userInitial);

  try {
    const snap = await statsRef(user.uid).get();
    if (snap.exists) {
      const data   = snap.data();
      reviewCount  = data.reviewCount       || 0;
      reviewsCount = data.totalInteractions || 0;
      issuesCount  = data.totalIssues       || 0;
      quizAttempts = data.quizAttempts      || 0;
      bestScore    = data.bestQuizScore !== undefined ? data.bestQuizScore : null;
      updateStats();
    }
  } catch (e) {
    console.warn("[agent-chat] Could not load stats:", e);
  }

  try {
    const res = await fetch(`${BACKEND_URL}/memories/${user.uid}/${AGENT_ID}`, {
      headers: {
        "ngrok-skip-browser-warning": "true"
      }
    });
    const data = await res.json();
    if (data.memories && data.memories.length > 0) {
      document.getElementById("welcomeMsg")?.remove();
      addMessage(
        `👋 Welcome back! I remember our previous sessions. Feel free to paste code for review.`,
        "ai"
      );
    }
  } catch (e) {
    console.warn("[agent-chat] Could not load memories:", e);
  }
});


// ════════════════════════════════════════════
//  Code Detection
// ════════════════════════════════════════════
function looksLikeCode(text) {
  return (
    text.includes("```")       ||
    text.includes("def ")      ||
    text.includes("function ") ||
    text.includes("import ")   ||
    text.includes("class ")    ||
    text.includes("const ")    ||
    text.includes("var ")      ||
    text.includes("let ")      ||
    text.includes("SELECT ")   ||
    text.includes("public ")   ||
    text.includes("=>")        ||
    text.includes("{")         ||
    text.length > 200
  );
}


// ════════════════════════════════════════════
//  Message Rendering
// ════════════════════════════════════════════
function addMessage(text, role) {
  const msg = document.createElement("div");
  msg.className = `sc-msg sc-msg--${role}`;

  const avatar = document.createElement("div");
  avatar.className = `sc-msg-avatar sc-msg-avatar--${role}`;
  avatar.textContent = role === "user" ? userInitial : "AI";

  const bubble = document.createElement("div");
  bubble.className = "sc-msg-bubble";
  bubble.innerHTML = role === "ai"
    ? formatAIText(text)
    : escHtml(text).replace(/\n/g, "<br>");

  msg.appendChild(avatar);
  msg.appendChild(bubble);
  chatWindow.appendChild(msg);
  chatWindow.scrollTop = chatWindow.scrollHeight;
  return msg;
}

function formatMarkdownTables(text) {
  // Matches a header row, a separator row (---|---), and 1+ body rows.
  const tableRe = /^\|(.+)\|\r?\n\|[\s:|-]+\|\r?\n((?:\|.*\|\r?\n?)+)/gm;

  return text.replace(tableRe, (match, headerLine, bodyLines) => {
    const splitRow = (line) =>
      line.split("|").slice(1, -1).map(cell => cell.trim());

    const headers = splitRow(headerLine);
    const rows = bodyLines
      .trim()
      .split("\n")
      .filter(line => line.trim())
      .map(line => splitRow(line.trim()));

    // The model sometimes emits a row with more (or fewer) cells than the
    // header — pad everything out to the widest row so every cell still
    // lands inside a bordered <td>/<th> instead of spilling outside the
    // table as unstyled text.
    const colCount = Math.max(headers.length, ...rows.map(r => r.length));
    while (headers.length < colCount) headers.push("");
    rows.forEach(row => { while (row.length < colCount) row.push(""); });

    // Convert a literal "<br>" the model wrote inside a cell (which would
    // otherwise show up as escaped, visible "<br>" text) into a real line
    // break, without un-escaping anything else in the cell.
    const renderCell = (raw) =>
      escHtml(raw).replace(/&lt;br\s*\/?&gt;/gi, "<br>");

    const thStyle = "text-align:left;padding:6px 10px;border-bottom:2px solid rgba(0,0,0,0.15);font-weight:600;vertical-align:top;";
    const tdStyle = "padding:6px 10px;border-bottom:1px solid rgba(0,0,0,0.08);vertical-align:top;word-break:break-word;";

    let html = '<table style="border-collapse:collapse;width:100%;table-layout:fixed;margin:8px 0;font-size:0.9em;"><thead><tr>';
    headers.forEach(h => { html += `<th style="${thStyle}">${renderCell(h)}</th>`; });
    html += "</tr></thead><tbody>";
    rows.forEach(row => {
      html += "<tr>";
      row.forEach(cell => { html += `<td style="${tdStyle}">${renderCell(cell)}</td>`; });
      html += "</tr>";
    });
    html += "</tbody></table>";
    return html;
  });
}

function formatAIText(text) {
  // Note: markdown tables (| col | col |) are intentionally left as plain
  // text here — not converted into an HTML <table> — per product decision
  // to keep review output in a simple text/list format instead.
  return text
    .replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) =>
      `<pre><code class="lang-${lang || 'text'}">${escHtml(code.trim())}</code></pre>`)
    .replace(/`([^`\n]+)`/g, "<code>$1</code>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/^#{1,3}\s+(.+)$/gm, "<strong>$1</strong>")
    .replace(/^[-•]\s+(.+)$/gm, "• $1")
    .replace(/\n/g, "<br>");
}

function escHtml(t) {
  return t
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function showTyping() {
  const msg = document.createElement("div");
  msg.className = "sc-msg sc-msg--ai sc-typing";
  msg.id = "typingIndicator";
  msg.innerHTML = `
    <div class="sc-msg-avatar sc-msg-avatar--ai">AI</div>
    <div class="sc-msg-bubble">
      <span class="sc-typing-dot"></span>
      <span class="sc-typing-dot"></span>
      <span class="sc-typing-dot"></span>
    </div>`;
  chatWindow.appendChild(msg);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function removeTyping() {
  document.getElementById("typingIndicator")?.remove();
}


// ════════════════════════════════════════════
//  Streaming API Call
// ════════════════════════════════════════════
async function streamReview(userMessage, onToken, onDone, onError) {
  abortController = new AbortController();

  // Guarantee onDone / onError fires exactly once, no matter how the
  // stream ends (explicit "done" event, silent connection close, or a
  // network/parse error). Without this guard, a server that just closes
  // the connection after the last token — without ever sending a
  // distinct "done" payload — leaves the caller's Promise unresolved
  // forever, which is what was permanently stuck-ing the Stop button.
  let settled = false;
  const settleDone  = (text) => { if (!settled) { settled = true; onDone(text); } };
  const settleError = (err)  => { if (!settled) { settled = true; onError(err); } };

  let accumulated = "";

  let response;
  try {
    response = await fetch(`${BACKEND_URL}/chat/stream`, {
      method:  "POST",
        headers: {
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true"
      },
      signal:  abortController.signal,
      body: JSON.stringify({
        message:    userMessage,
        user_id:    currentUser?.uid || "guest",
        session_id: sessionId,
      }),
    });
  } catch (err) {
    settleError(err);
    return;
  }

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    settleError(new Error(errData.detail || `Server error ${response.status}`));
    return;
  }

  const reader  = response.body.getReader();
  const decoder = new TextDecoder();
  let   buffer  = "";

  while (true) {
    let done, value;
    try {
      ({ done, value } = await reader.read());
    } catch (err) {
      settleError(err);
      return;
    }

    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop();

    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data: ")) continue;
      try {
        const payload = JSON.parse(line.slice(6));
        if (payload.error) { settleError(new Error(payload.error)); return; }
        if (payload.token) { accumulated += payload.token; onToken(payload.token); }
        if (payload.done)  { settleDone(payload.full || accumulated); return; }
      } catch (e) {
        // Malformed JSON chunk — skip silently
      }
    }
  }

  // Stream/connection ended without an explicit "done" event.
  // Fall back to whatever tokens we've accumulated so the UI still
  // completes cleanly instead of hanging forever.
  settleDone(accumulated);
}


// ════════════════════════════════════════════
//  Save to Firestore via /save
// ════════════════════════════════════════════
async function saveToFirestore(userMessage, aiReply) {
  if (!currentUser) return;
  try {
    await fetch(`${BACKEND_URL}/save`, {
      method:  "POST",
       headers: {
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true"
      },
      body: JSON.stringify({
        user_id:    currentUser.uid,
        session_id: sessionId,
        message:    userMessage,
        reply:      aiReply,
      }),
    });
  } catch (e) {
    console.warn("[agent-chat] /save failed:", e);
  }
}


// ════════════════════════════════════════════
//  Save Stats
// ════════════════════════════════════════════
async function saveStats(isCodeReview) {
  if (!currentUser) return;
  try {
    const payload = {
      totalInteractions: firebase.firestore.FieldValue.increment(1),
      lastActive:        new Date(),
    };
    if (isCodeReview) {
      payload.totalReviews = firebase.firestore.FieldValue.increment(1);
      payload.reviewCount  = reviewCount;
    }
    await statsRef(currentUser.uid).set(payload, { merge: true });
  } catch (e) {
    console.warn("[agent-chat] Could not save stats:", e);
  }
}


// ════════════════════════════════════════════
//  Detect Verdict
// ════════════════════════════════════════════
function detectVerdict(reply) {
  const upper = reply.toUpperCase();
  if (/\bCRITICAL\b/.test(upper) || /\bHIGH\b/.test(upper)) return "FAIL";
  if (/\bMEDIUM\b/.test(upper))                               return "WARN";
  return "PASS";
}


// ════════════════════════════════════════════
//  Count Issues
// ════════════════════════════════════════════
function countIssues(reply) {
  const upper = reply.toUpperCase();
  return (
    (upper.match(/\bCRITICAL\b/g) || []).length +
    (upper.match(/\bHIGH\b/g)     || []).length +
    (upper.match(/\bMEDIUM\b/g)   || []).length +
    (upper.match(/\bLOW\b/g)      || []).length
  );
}


// ════════════════════════════════════════════
//  Verdict Badge
// ════════════════════════════════════════════
function verdictBadge(verdict) {
  const styles = {
    FAIL: { bg: "#fde8e8", color: "#b91c1c", border: "#fca5a5" },
    WARN: { bg: "#fef3c7", color: "#92400e", border: "#fcd34d" },
    PASS: { bg: "#dcfce7", color: "#166534", border: "#86efac" },
  };
  const s = styles[verdict] || styles.PASS;
  return `<span style="
    display:inline-flex;align-items:center;
    padding:2px 10px;border-radius:9999px;
    font-size:0.72rem;font-weight:700;letter-spacing:0.05em;
    margin-left:6px;vertical-align:middle;
    background:${s.bg};color:${s.color};border:1px solid ${s.border};
  ">${verdict}</span>`;
}


// ════════════════════════════════════════════
//  Send Message — streaming version
// ════════════════════════════════════════════
async function sendMessage(text) {
  const trimmed = (text || "").trim();
  if (!trimmed || isGenerating) return;
  if (!currentUser) {
    addMessage("Please log in to use the Code Review Agent.", "ai");
    return;
  }

  chatInput.value        = "";
  chatInput.style.height = "auto";
  showStopBtn();

  addMessage(trimmed, "user");
  showTyping();

  reviewsCount++;
  const isCodeReview = looksLikeCode(trimmed);
  if (isCodeReview) reviewCount++;

  // Fire-and-forget — does NOT block the UI or the stream
  saveStats(isCodeReview).catch(e => console.warn("[agent-chat] saveStats failed:", e));
  updateStats();

  let aiBubble  = null;
  let fullReply = "";

  try {
    await new Promise((resolve) => {
      streamReview(
        trimmed,

        // ── onToken ───────────────────────────────────────────────────
        (token) => {
          if (!aiBubble) {
            removeTyping();
            const msgEl = addMessage("", "ai");
            aiBubble = msgEl.querySelector(".sc-msg-bubble");
          }
          fullReply += token;
          aiBubble.innerHTML   = formatAIText(fullReply);
          chatWindow.scrollTop = chatWindow.scrollHeight;
        },

        // ── onDone ────────────────────────────────────────────────────
        (fullText) => {
          fullReply = fullText || fullReply;

          if (aiBubble) {
            const badge = isCodeReview ? verdictBadge(detectVerdict(fullReply)) : "";
            aiBubble.innerHTML = formatAIText(fullReply) + badge;
          }

          resolve(); // Unblocks the finally block immediately

          saveToFirestore(trimmed, fullReply) // Background — no await
            .catch(e => console.warn("[agent-chat] Background save failed:", e));

          if (isCodeReview) {
            issuesCount += countIssues(fullReply);
            updateStats();

            // ── Auto Quiz: capture this review's content ──────────────
            recordReviewForQuiz(fullReply);
          }
        },

        // ── onError ───────────────────────────────────────────────────
        (err) => {
          removeTyping();

          if (err.name === "AbortError") {
            if (aiBubble) {
              aiBubble.innerHTML =
                formatAIText(fullReply) +
                "<br><span style='opacity:0.5;font-size:0.85em'>⏹️ Stopped</span>";
            } else {
              addMessage("⏹️ Response stopped.", "ai");
            }
            resolve();
            saveToFirestore(trimmed, "⏹️ Response stopped by user.")
              .catch(e => console.warn("[agent-chat] Background save:", e));

          } else {
            const isNetwork =
              err.message.includes("Failed to fetch")        ||
              err.message.includes("NetworkError")           ||
              err.message.includes("ERR_CONNECTION_REFUSED");
            addMessage(
              isNetwork
                ? "⚠️ Cannot reach the backend. Make sure it is running:\n\n`cd backend && uvicorn agent:app --reload --port 8000`"
                : `❌ Error: ${err.message}`,
              "ai"
            );
            console.error("[agent-chat] Stream error:", err);
            resolve();
          }
        }
      );
    });
  } catch (err) {
    // Safety net: if anything throws unexpectedly outside the callbacks
    // above, we still land here instead of leaving the Promise unresolved
    // and the Stop button stuck forever.
    console.error("[agent-chat] Unexpected error in sendMessage:", err);
    removeTyping();
    addMessage(`❌ Unexpected error: ${err.message}`, "ai");
  } finally {
    // Guaranteed to run exactly once, immediately after the request
    // settles (success, error, or abort) — no polling, no delay.
    showSendBtn();
    chatInput.focus();
  }
}


// ════════════════════════════════════════════
//  Stop Button
// ════════════════════════════════════════════
stopBtn?.addEventListener("click", () => {
  if (abortController && isGenerating) {
    abortController.abort();
    showSendBtn(); // Resets button instantly on click
  }
});


// ════════════════════════════════════════════
//  Stats Panel
// ════════════════════════════════════════════
function updateStats() {
  const mins = Math.floor((Date.now() - sessionStart) / 60000);
  const set  = (id, val) => { const e = document.getElementById(id); if (e) e.textContent = val; };
  const bar  = (id, pct) => { const e = document.getElementById(id); if (e) e.style.width  = pct + "%"; };

  set("progressQAsked",   reviewsCount);
  set("progressQuizCount", quizAttempts);
  set("progressQAttempts", issuesCount);
  set("progressTime",     mins + " min");

  bar("fillQAsked",     Math.min(reviewsCount * 20, 100));
  bar("fillQuizCount",  Math.min(quizAttempts * 25, 100));
  bar("fillQAttempts",  Math.min(issuesCount  * 10, 100));
  bar("fillTime",       Math.min(mins         * 20, 100));
}


// ════════════════════════════════════════════
//  Input Events
// ════════════════════════════════════════════
sendBtn?.addEventListener("click", () => sendMessage(chatInput.value));

chatInput?.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage(chatInput.value);
  }
});

chatInput?.addEventListener("input", () => {
  chatInput.style.height = "auto";
  chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + "px";
});


// ════════════════════════════════════════════
//  Suggestion Chips
// ════════════════════════════════════════════
document.querySelectorAll(".sc-suggestion-chip").forEach(chip => {
  chip.addEventListener("click", () => sendMessage(chip.textContent.trim()));
});


// ════════════════════════════════════════════
//  Sidebar Toggle
// ════════════════════════════════════════════
const sidebar        = document.getElementById("sidebar");
const sidebarToggle  = document.getElementById("sidebarToggle");
const mobileMenuBtn  = document.getElementById("mobileMenuBtn");
const sidebarOverlay = document.getElementById("sidebarOverlay");

sidebarToggle?.addEventListener("click", () => sidebar.classList.toggle("collapsed"));

mobileMenuBtn?.addEventListener("click", () => {
  sidebar.classList.add("mobile-open");
  sidebarOverlay.classList.add("visible");
  document.body.style.overflow = "hidden";
});

sidebarOverlay?.addEventListener("click", () => {
  sidebar.classList.remove("mobile-open");
  sidebarOverlay.classList.remove("visible");
  document.body.style.overflow = "";
});


// ════════════════════════════════════════════
//  Logout
// ════════════════════════════════════════════
document.getElementById("logoutBtn")?.addEventListener("click", async () => {
  await firebase.auth().signOut();
  window.location.href = "index.html";
});


// ════════════════════════════════════════════
//  Dark Mode
// ════════════════════════════════════════════
(() => {
  const html   = document.documentElement;
  const toggle = document.querySelector("[data-theme-toggle]");
  let theme    = localStorage.getItem("theme") ||
                 (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");

  html.setAttribute("data-theme", theme);
  if (toggle) {
    toggle.innerHTML = theme === "dark" ? "☀️" : "🌙";
    toggle.addEventListener("click", () => {
      theme = theme === "dark" ? "light" : "dark";
      html.setAttribute("data-theme", theme);
      localStorage.setItem("theme", theme);
      toggle.innerHTML = theme === "dark" ? "☀️" : "🌙";
    });
  }
})();


// Auto stats refresh every 60 seconds
setInterval(updateStats, 60000);


// ════════════════════════════════════════════════════════════════
//  AUTO QUIZ — generated from code review content
// ════════════════════════════════════════════════════════════════
// Unlike AdaptLearn (which builds quizzes from chat *topics* tracked
// on the backend), the Code Review Agent builds quizzes straight from
// the actual review feedback the AI just gave — the issues, risks,
// and best-practice notes it flagged in the last few reviews.

const MAX_REVIEWS_FOR_QUIZ = 3;   // keep the most recent N reviews
const MAX_REVIEW_CHARS     = 4000; // cap per-review length sent to the quiz prompt

let reviewHistory = [];   // stores recent review text (most recent last)
let quizQuestions  = [];
let quizIndex       = 0;
let quizActive      = false;
let currentScore    = 0;
let quizAttempts    = 0;
let bestScore        = null;

const quizQText     = document.getElementById("quizQText");
const quizOptionsEl = document.getElementById("quizOptions");
const quizCounter   = document.getElementById("quizCounter");
const quizResult    = document.getElementById("quizResult");
const quizScore     = document.getElementById("quizScore");
const quizMsg       = document.getElementById("quizMsg");
const quizStartBtn  = document.getElementById("quizStartBtn");
const quizRestartBtn = document.getElementById("quizRestartBtn");
const quizOpts       = [0, 1, 2, 3].map(i => document.getElementById("opt" + i));

function recordReviewForQuiz(reviewText) {
  reviewHistory.push(reviewText.slice(0, MAX_REVIEW_CHARS));
  if (reviewHistory.length > MAX_REVIEWS_FOR_QUIZ) reviewHistory.shift();

  if (!quizActive && quizQText) {
    quizQText.textContent = '✅ New review ready — click "Start Quiz" to test yourself on it!';
  }
}

async function startQuiz() {
  if (!currentUser) return;

  quizResult?.classList.add("hidden");
  quizOptionsEl?.classList.add("hidden");
  quizStartBtn?.classList.add("hidden");
  if (quizCounter) quizCounter.textContent = "";

  if (reviewHistory.length === 0) {
    if (quizQText) quizQText.textContent = "💡 Submit some code for review first, then start the quiz!";
    quizStartBtn?.classList.remove("hidden");
    return;
  }

  if (quizQText) quizQText.textContent = "⏳ Generating quiz from your latest code review...";

  try {
    const res = await fetch(`${BACKEND_URL}/quiz/generate-from-review`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true"
      },
      body: JSON.stringify({
        uid: currentUser.uid,
        review_content: reviewHistory.join("\n\n---\n\n"),
        num_questions: 5
      })
    });

    const data = await res.json();

    if (data.error || !data.questions || data.questions.length === 0) {
      if (quizQText) quizQText.textContent = data.error || "Could not generate a quiz from this review. Try another one!";
      quizStartBtn?.classList.remove("hidden");
      return;
    }

    quizQuestions = data.questions;
    quizIndex     = 0;
    currentScore  = 0;
    quizActive    = true;
    quizAttempts++;
    updateStats();

    quizOptionsEl?.classList.remove("hidden");
    showQuestion();
  } catch (err) {
    if (quizQText) quizQText.textContent = "⚠️ Could not reach backend. Is the server running?";
    quizStartBtn?.classList.remove("hidden");
    console.error("[Quiz]", err);
  }
}

function showQuestion() {
  const q = quizQuestions[quizIndex];
  if (!q) return;

  if (quizQText) quizQText.textContent = `Q${quizIndex + 1}. ${q.question}`;
  if (quizCounter) quizCounter.textContent = `Question ${quizIndex + 1} / ${quizQuestions.length}`;

  const optKeys = ["A", "B", "C", "D"];
  quizOpts.forEach((btn, i) => {
    if (!btn) return;
    btn.textContent = optKeys[i] + ". " + q.options[optKeys[i]];
    btn.disabled = false;
    btn.className = "sc-quiz-opt";
  });
}

function selectAnswer(chosenIndex) {
  if (!quizActive) return;

  const q = quizQuestions[quizIndex];
  const correct = q.correct.trim().toUpperCase();
  const optKeys = ["A", "B", "C", "D"];
  const chosen = optKeys[chosenIndex];

  quizOpts.forEach((btn, i) => {
    if (!btn) return;
    btn.disabled = true;
    if (optKeys[i] === correct) btn.classList.add("correct");
    if (i === chosenIndex && optKeys[i] !== correct) btn.classList.add("wrong");
  });

  if (chosen === correct) currentScore++;

  setTimeout(() => {
    quizIndex++;
    if (quizIndex < quizQuestions.length) showQuestion();
    else endQuiz();
  }, 900);
}

async function endQuiz() {
  quizActive = false;
  quizOptionsEl?.classList.add("hidden");
  if (quizCounter) quizCounter.textContent = "";
  quizResult?.classList.remove("hidden");
  quizStartBtn?.classList.remove("hidden");

  const total = quizQuestions.length;
  if (quizScore) quizScore.textContent = currentScore + " / " + total;

  if (quizMsg) {
    if (currentScore === total) quizMsg.textContent = "Perfect score! 🎉";
    else if (currentScore >= total * 0.8) quizMsg.textContent = "Great job! 🌟";
    else if (currentScore >= total * 0.6) quizMsg.textContent = "Good effort! Keep going 💪";
    else quizMsg.textContent = "Review the feedback again — you'll get it! 📚";
  }

  if (bestScore === null || currentScore > bestScore) bestScore = currentScore;

  if (currentUser) {
    try {
      await statsRef(currentUser.uid).set({
        quizAttempts: firebase.firestore.FieldValue.increment(1),
        bestQuizScore: bestScore,
        lastQuizAt: new Date()
      }, { merge: true });
    } catch (e) {
      console.warn("[Quiz] Could not save quiz result:", e);
    }
  }
}

quizOpts.forEach((btn, i) => btn?.addEventListener("click", () => selectAnswer(i)));
quizStartBtn?.addEventListener("click", startQuiz);
quizRestartBtn?.addEventListener("click", startQuiz);
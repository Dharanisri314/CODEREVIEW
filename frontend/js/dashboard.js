// ════════════════════════════════════════════
//  dashboard.js
// ════════════════════════════════════════════

// const BACKEND_URL = "http://localhost:8000";
const BACKEND_URL = "";


// ── Auth + Load ───────────────────────────────────────────────
auth.onAuthStateChanged(async (user) => {
  if (!user) { window.location.href = "index.html"; return; }

  const nameEl = document.getElementById("userDisplayName");
  if (nameEl) nameEl.textContent = user.displayName || user.email.split("@")[0];

  await Promise.allSettled([
    checkBackendHealth(),
    loadDashboardData(user.uid),
  ]);
});


// ── Backend Health ────────────────────────────────────────────
async function checkBackendHealth() {
  const badge = document.getElementById("backendStatusBadge");
  try {
    const res = await fetch(`${BACKEND_URL}/health`, {
      signal: AbortSignal.timeout(4000)
    });
    if (res.ok) {
      badge.className = "status-badge online";
      badge.innerHTML = dotIcon() + " Backend Online";
    } else throw new Error();
  } catch {
    badge.className = "status-badge offline";
    badge.innerHTML = dotIcon() + " Backend Offline";
  }
}

function dotIcon() {
  return `<svg width="8" height="8" viewBox="0 0 24 24" fill="currentColor">
    <circle cx="12" cy="12" r="10"/>
  </svg>`;
}


// ── Main Dashboard Data ───────────────────────────────────────
async function loadDashboardData(uid) {
  try {
    const res = await fetch(`${BACKEND_URL}/dashboard/${uid}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    // Support nested data.stats or direct object payload
    const statsData = data.stats || data;

    // The backend's /dashboard endpoint doesn't track quiz attempts —
    // those are written straight to Firestore (codeReviews/{uid}) by
    // agent-chat.js's endQuiz(). Pull that field directly from Firestore,
    // the same way agent-chat.js does on load, and merge it in so it
    // isn't silently overwritten with a stale/missing value from the
    // backend response.
    const quizStats = await loadQuizStatsFromFirestore(uid);
    renderStats({ ...statsData, ...quizStats });
    renderActivity(data.recentSessions || data.sessions || []);
  } catch (e) {
    console.warn("[Dashboard] Could not load backend data, attempting Firestore fallback:", e);
    await loadFirestoreStatsFallback(uid);
  }
}


// ── Quiz Stats (authoritative source: Firestore) ────────────────
// Mirrors the exact read agent-chat.js performs on load:
//   quizAttempts = data.quizAttempts || 0;
//   bestScore    = data.bestQuizScore !== undefined ? data.bestQuizScore : null;
async function loadQuizStatsFromFirestore(uid) {
  try {
    const snap = await firebase.firestore().collection("codeReviews").doc(uid).get();
    if (snap.exists) {
      const data = snap.data();
      return {
        quizAttempts: data.quizAttempts || 0,
        bestQuizScore: data.bestQuizScore !== undefined ? data.bestQuizScore : null,
      };
    }
  } catch (err) {
    console.warn("[Dashboard] Could not load quiz stats from Firestore:", err);
  }
  return { quizAttempts: 0, bestQuizScore: null };
}


// ── Firestore Direct Fallback ─────────────────────────────────
async function loadFirestoreStatsFallback(uid) {
  try {
    const docRef = firebase.firestore().collection("codeReviews").doc(uid);
    const snap = await docRef.get();
    if (snap.exists) {
      renderStats(snap.data());
    } else {
      renderFallback();
    }
  } catch (err) {
    console.error("[Dashboard] Firestore fallback error:", err);
    renderFallback();
  }
}


// ── Verdict helpers ───────────────────────────────────────────

// Returns null for empty text — never defaults to "PASS"
function detectVerdict(text) {
  if (!text) return null;
  const upper = text.toUpperCase();
  if (/\bCRITICAL\b/.test(upper) || /\bHIGH\b/.test(upper)) return "FAIL";
  if (/\bMEDIUM\b/.test(upper))                               return "WARN";
  return "PASS";
}

// Count severity keywords in AI reply
function countIssues(text) {
  if (!text) return 0;
  const upper = text.toUpperCase();
  return (
    (upper.match(/\bCRITICAL\b/g) || []).length +
    (upper.match(/\bHIGH\b/g)     || []).length +
    (upper.match(/\bMEDIUM\b/g)   || []).length +
    (upper.match(/\bLOW\b/g)      || []).length
  );
}

// Returns null for chat-only sessions — no verdict badge shown at all
function resolveVerdict(s) {
  const thread = s.thread || [];
  const hasCodeReview = s.hasCodeReview || thread.some(t => t.isCodeReview);

  // Chat-only session → no verdict
  if (!hasCodeReview) return null;

  // Prefer backend-stored verdict (already code-review-filtered by agent.py)
  if (s.verdict && ["FAIL", "WARN", "PASS"].includes(s.verdict)) return s.verdict;

  // Fallback: scan only code-review turns
  const codeText = thread
    .filter(t => t.isCodeReview)
    .map(t => t.aiResponse || "")
    .join(" ");

  return codeText ? detectVerdict(codeText) : null;
}

// Returns 0 for chat-only sessions
function resolveIssueCount(s) {
  const thread = s.thread || [];
  const hasCodeReview = s.hasCodeReview || thread.some(t => t.isCodeReview);

  if (!hasCodeReview) return 0;
  if (typeof s.issueCount === "number" && s.issueCount > 0) return s.issueCount;

  const codeText = thread
    .filter(t => t.isCodeReview)
    .map(t => t.aiResponse || "")
    .join(" ");

  return codeText ? countIssues(codeText) : 0;
}


// ── Verdict constants ─────────────────────────────────────────
const VERDICT_COLOR  = { FAIL: "#ef4444", WARN: "#f59e0b", PASS: "#22c55e" };
const VERDICT_BG     = { FAIL: "#fde8e8", WARN: "#fef3c7", PASS: "#dcfce7" };
const VERDICT_BORDER = { FAIL: "#fca5a5", WARN: "#fcd34d", PASS: "#86efac" };

const VERDICT_ICON = {
  FAIL: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
           <circle cx="12" cy="12" r="10"/>
           <line x1="15" y1="9" x2="9" y2="15"/>
           <line x1="9" y1="9" x2="15" y2="15"/>
         </svg>`,
  WARN: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
           <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
           <line x1="12" y1="9" x2="12" y2="13"/>
           <line x1="12" y1="17" x2="12.01" y2="17"/>
         </svg>`,
  PASS: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
           <circle cx="12" cy="12" r="10"/>
           <polyline points="9 12 11 14 15 10"/>
         </svg>`,
};


// ── Render Stat Cards ─────────────────────────────────────────
function renderStats(stats) {
  if (!stats) return;

  const set = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val ?? "—";
  };

  // Property fallbacks for key variations across backend APIs / Firestore
  const totalReviews = stats.totalInteractions ?? stats.reviewCount ?? stats.total_interactions ?? 0;
  const quizCount    = stats.quizAttempts ?? stats.quizCount ?? stats.quiz_attempts ?? 0;
  const totalIssues  = stats.totalIssues ?? stats.total_issues ?? 0;

  set("statReviews",       totalReviews);
  set("progressQuizCount", quizCount); // Matches HTML element ID
  set("statQuizCount",     quizCount); // Alternative element ID safeguard
  set("statIssues",        totalIssues);
  set("statLastActive",    stats.lastActive ? timeAgo(new Date(stats.lastActive)) : "—");

  const verdictEl = document.getElementById("statVerdict");
  if (verdictEl) {
    const v = stats.lastVerdict || null;
    if (v && ["FAIL", "WARN", "PASS"].includes(v)) {
      verdictEl.textContent = v;
      verdictEl.style.color =
        v === "FAIL" ? "#ef4444" :
        v === "WARN" ? "#f59e0b" : "#22c55e";
    } else {
      verdictEl.textContent = "—";
      verdictEl.style.color = "inherit";
    }
  }
}


// ── Render Recent Activity ────────────────────────────────────
function renderActivity(sessions) {
  const list = document.getElementById("activityList");

  if (!sessions || sessions.length === 0) {
    list.innerHTML = `
      <div class="activity-empty">
        No reviews yet —
        <a href="agent-chat.html" style="color:#3b82f6;text-decoration:none;font-weight:600;">
          start your first code review →
        </a>
      </div>`;
    return;
  }

  list.innerHTML = sessions.slice(0, 10).map((s, i) => {
    const verdict    = resolveVerdict(s);   // null for chat-only sessions
    const issueCount = resolveIssueCount(s);
    const color      = verdict ? VERDICT_COLOR[verdict] : "#94a3b8";

    const cardTitle  = s.sessionTitle || s.lastMessage || "New Session";
    const firstAiMsg = (s.thread || []).find(t => t.aiResponse)?.aiResponse || s.lastMessage || "";
    const msgCount   = (s.thread || []).length;

    // Only render verdict badge when code was reviewed
    const verdictBadge = verdict
      ? `<span style="color:${color}; display:inline-flex; align-items:center; gap:3px; font-weight:600;">
           ${VERDICT_ICON[verdict]} ${verdict}
         </span>`
      : "";

    const issueBadge = issueCount > 0
      ? `<span style="color:#ef4444; font-size:0.68rem;">${issueCount} issue${issueCount > 1 ? "s" : ""}</span>`
      : "";

    return `
    <div class="activity-item activity-item--clickable" data-index="${i}" style="cursor:pointer;">
      <div class="activity-dot" style="background:${color};"></div>
      <div class="activity-body">
        <div class="activity-role">
          <span class="lang-badge">${escHtml(s.language || "Code")}</span>
          ${verdictBadge}
          ${issueBadge}
          <span style="font-size:0.68rem; color:#94a3b8; margin-left:auto;">
            ${msgCount} message${msgCount !== 1 ? "s" : ""} · Click to view
          </span>
        </div>
        <div class="activity-text" style="font-weight:500; color:var(--color-text);">
          ${escHtml(cardTitle.slice(0, 120))}${cardTitle.length > 120 ? "…" : ""}
        </div>
        <div class="activity-preview" style="font-size:0.78rem; color:var(--color-text-muted); margin-top:3px;">
          ${escHtml(firstAiMsg.slice(0, 100))}${firstAiMsg.length > 100 ? "…" : ""}
        </div>
      </div>
      <div class="activity-time">${s.createdAt ? timeAgo(new Date(s.createdAt)) : ""}</div>
    </div>`;
  }).join("");

  list.querySelectorAll(".activity-item--clickable").forEach(el => {
    el.addEventListener("click", () => {
      openReviewModal(sessions[parseInt(el.dataset.index)]);
    });
  });
}


// ── Review Detail Modal ───────────────────────────────────────
function openReviewModal(s) {
  const modal  = document.getElementById("reviewModal");
  const meta   = document.getElementById("modalMeta");
  const thread = document.getElementById("modalThread");

  if (!modal || !meta) {
    console.error("[Dashboard] Modal HTML elements not found.");
    return;
  }

  const verdict    = resolveVerdict(s);   // null for chat-only sessions
  const issueCount = resolveIssueCount(s);
  const color      = verdict ? VERDICT_COLOR[verdict] : "#94a3b8";
  const time       = s.createdAt ? timeAgo(new Date(s.createdAt)) : "";

  const titleEl = document.getElementById("modalSessionTitle");
  if (titleEl) titleEl.textContent = s.sessionTitle || "Code Review Session";

  // Verdict badge — only shown when code was reviewed
  const verdictBadge = verdict
    ? `<span style="
          display:inline-flex; align-items:center; gap:4px;
          padding:2px 10px; border-radius:9999px;
          font-size:0.75rem; font-weight:700; letter-spacing:0.04em;
          background:${VERDICT_BG[verdict]     || "#f1f5f9"};
          color:${color};
          border:1px solid ${VERDICT_BORDER[verdict] || "#e2e8f0"};
        ">
        ${VERDICT_ICON[verdict]} ${verdict}
       </span>`
    : "";

  const issueBadge = issueCount > 0
    ? `<span style="color:#ef4444; font-size:0.8rem;">${issueCount} issue${issueCount > 1 ? "s" : ""}</span>`
    : "";

  meta.innerHTML = `
    <span class="lang-badge">${escHtml(s.language || "Code")}</span>
    ${verdictBadge}
    ${issueBadge}
    ${time ? `<span style="color:#94a3b8; font-size:0.8rem; margin-left:4px;">${time}</span>` : ""}
    <span style="color:#94a3b8; font-size:0.8rem; margin-left:4px;">
      ${(s.thread || []).length} message${(s.thread || []).length !== 1 ? "s" : ""}
    </span>
  `;

  // ── Render full conversation thread ───────────────────────
  const turns = s.thread || [];

  if (thread) {
    if (turns.length === 0) {
      thread.innerHTML = `<div style="color:var(--color-text-muted);padding:16px 0;text-align:center;">No conversation recorded.</div>`;
    } else {
      thread.innerHTML = turns.map((turn, idx) => `
        <div style="margin-bottom:20px;">

          <!-- User bubble -->
          <div style="display:flex; align-items:flex-start; gap:10px; margin-bottom:10px;">
  <div style="
    min-width:42px; height:28px; border-radius:14px; padding:0 6px;
    background:var(--color-primary,#3b82f6); color:#fff;
    display:flex; align-items:center; justify-content:center;
    font-size:0.7rem; font-weight:700; flex-shrink:0;">
    User
  </div>
            <div style="
              background:var(--color-surface-offset,#f1f5f9);
              border-radius:0 10px 10px 10px;
              padding:10px 14px; font-size:0.85rem;
              color:var(--color-text,#1e293b); max-width:100%;
              white-space:pre-wrap; word-break:break-word;">
              ${escHtml(turn.userMessage || "")}
            </div>
          </div>

          <!-- AI bubble -->
          <div style="display:flex; align-items:flex-start; gap:10px;">
            <div style="
              min-width:28px; height:28px; border-radius:50%;
              background:#6366f1; color:#fff;
              display:flex; align-items:center; justify-content:center;
              font-size:0.7rem; font-weight:700; flex-shrink:0;">
              AI
            </div>
            <div style="
              background:var(--color-surface,#fff);
              border:1px solid var(--color-border,#e2e8f0);
              border-radius:0 10px 10px 10px;
              padding:10px 14px; font-size:0.85rem;
              color:var(--color-text,#1e293b); max-width:100%; overflow-x:auto;">
              ${formatModalText(turn.aiResponse || "")}
            </div>
          </div>

          ${idx < turns.length - 1
            ? `<hr style="border:none;border-top:1px solid var(--color-divider,#e2e8f0);margin:16px 0;">`
            : ""}
        </div>
      `).join("");

      thread.scrollTop = 0;
    }
  }

  modal.style.display          = "flex";
  document.body.style.overflow = "hidden";
}

function closeReviewModal() {
  const modal = document.getElementById("reviewModal");
  if (modal) modal.style.display = "none";
  document.body.style.overflow = "";
}


// ── Modal Event Listeners ─────────────────────────────────────
const reviewModal   = document.getElementById("reviewModal");
const modalCloseBtn = document.getElementById("modalCloseBtn");

if (modalCloseBtn) modalCloseBtn.addEventListener("click", closeReviewModal);
if (reviewModal) {
  reviewModal.addEventListener("click", (e) => {
    if (e.target === e.currentTarget) closeReviewModal();
  });
}
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeReviewModal();
});


// ── Format AI text for modal (markdown-like) ─────────────────
function formatModalText(text) {
  return text
    .replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) =>
      `<pre style="background:var(--color-surface-offset,#f1f5f9);padding:12px 14px;border-radius:8px;overflow-x:auto;font-size:0.82rem;margin:8px 0;"><code>${escHtml(code.trim())}</code></pre>`)
    .replace(/`([^`\n]+)`/g, `<code style="background:var(--color-surface-offset,#f1f5f9);padding:1px 5px;border-radius:4px;font-size:0.88em;">$1</code>`)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/^#{1,3}\s+(.+)$/gm, "<strong style='font-size:1rem;display:block;margin-top:10px;'>$1</strong>")
    .replace(/^[-•]\s+(.+)$/gm, "<div style='padding-left:14px;margin:3px 0;'>• $1</div>")
    .replace(/\n/g, "<br>");
}


// ── Fallback when backend is offline ─────────────────────────
function renderFallback() {
  ["statReviews", "progressQuizCount", "statQuizCount", "statIssues", "statLastActive"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = "—";
  });

  const list = document.getElementById("activityList");
  if (list) list.innerHTML = `
    <div class="activity-empty">
      Backend offline — run
      <code style="background:var(--color-surface-offset);padding:2px 6px;border-radius:4px;">
        uvicorn agent:app --reload --port 8000
      </code>
    </div>`;
}


// ── Helpers ───────────────────────────────────────────────────
function escHtml(t = "") {
  return String(t)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function timeAgo(date) {
  const secs = Math.floor((Date.now() - date) / 1000);
  if (secs < 60)    return "Just now";
  if (secs < 3600)  return Math.floor(secs / 60)   + "m ago";
  if (secs < 86400) return Math.floor(secs / 3600)  + "h ago";
  return Math.floor(secs / 86400) + "d ago";
}


// ── Sidebar ───────────────────────────────────────────────────
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


// ── Logout ────────────────────────────────────────────────────
document.getElementById("logoutBtn")?.addEventListener("click", async () => {
  await auth.signOut();
  window.location.href = "index.html";
});


// ── Dark Mode ─────────────────────────────────────────────────
(() => {
  const html   = document.documentElement;
  const toggle = document.querySelector("[data-theme-toggle]");
  let theme    = localStorage.getItem("theme") ||
                 (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  html.setAttribute("data-theme", theme);

  const SUN  = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`;
  const MOON = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;

  if (toggle) {
    toggle.innerHTML = theme === "dark" ? SUN : MOON;
    toggle.addEventListener("click", () => {
      theme = theme === "dark" ? "light" : "dark";
      html.setAttribute("data-theme", theme);
      localStorage.setItem("theme", theme);
      toggle.innerHTML = theme === "dark" ? SUN : MOON;
    });
  }
})();
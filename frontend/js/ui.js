/*
 * ui.js
 * Shared UI helper functions used by auth-login.js and auth-signup.js
 */

// ── Email validator ───────────────────────────────────────
function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

// ── Toast helpers ─────────────────────────────────────────
function showToast(toastId, msgId, message) {
  const toast = document.getElementById(toastId);
  const msg   = document.getElementById(msgId);
  if (!toast || !msg) return;
  msg.textContent = message;
  toast.classList.add("visible");
}

function hideToast(toastId) {
  const toast = document.getElementById(toastId);
  if (toast) toast.classList.remove("visible");
}

// ── Field error helpers ───────────────────────────────────
function showFieldError(inputId, errorId) {
  const input = document.getElementById(inputId);
  const err   = document.getElementById(errorId);
  if (input) input.classList.add("invalid");
  if (err)   err.classList.add("visible");
}

function clearFieldError(inputId, errorId) {
  const input = document.getElementById(inputId);
  const err   = document.getElementById(errorId);
  if (input) input.classList.remove("invalid");
  if (err)   err.classList.remove("visible");
}

// ── Loading state ─────────────────────────────────────────
function setLoading(btnId, loading) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  btn.disabled = loading;
  btn.dataset.original = btn.dataset.original || btn.textContent;
  btn.textContent = loading ? "Please wait…" : btn.dataset.original;
}

// ── Password toggle ───────────────────────────────────────
function togglePwd(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const isHidden = input.type === "password";
  input.type = isHidden ? "text" : "password";
  btn.innerHTML = isHidden
    ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
         <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
         <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
         <line x1="1" y1="1" x2="23" y2="23"/>
       </svg>`
    : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
         <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
         <circle cx="12" cy="12" r="3"/>
       </svg>`;
}

// ── Friendly Firebase error messages ─────────────────────
function friendlyError(code) {
  const map = {
    "auth/email-already-in-use":    "This email is already registered. Try logging in.",
    "auth/invalid-email":           "Please enter a valid email address.",
    "auth/weak-password":           "Password must be at least 6 characters.",
    "auth/user-not-found":          "No account found with this email.",
    "auth/wrong-password":          "Incorrect password. Please try again.",
    "auth/invalid-credential":      "Incorrect email or password. Please try again.",
    "auth/too-many-requests":       "Too many failed attempts. Please try again later.",
    "auth/network-request-failed":  "Network error. Check your connection.",
    "auth/user-disabled":           "This account has been disabled.",
  };
  return map[code] || "Something went wrong. Please try again.";
}

// ── Dark mode toggle (auth pages) ────────────────────────
(function () {
  const html   = document.documentElement;
  const toggle = document.querySelector("[data-theme-toggle]");
  if (!toggle) return;

  let theme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  html.setAttribute("data-theme", theme);

  const SUN  = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="12" r="5"/>
    <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
    <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
  </svg>`;
  const MOON = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
  </svg>`;

  toggle.innerHTML = theme === "dark" ? SUN : MOON;
  toggle.addEventListener("click", () => {
    theme = theme === "dark" ? "light" : "dark";
    html.setAttribute("data-theme", theme);
    toggle.innerHTML = theme === "dark" ? SUN : MOON;
  });
})();
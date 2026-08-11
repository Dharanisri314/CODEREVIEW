// ── Auth Guard + Populate Profile ───────────────────────────
auth.onAuthStateChanged((user) => {
  if (!user) {
    window.location.href = "index.html";
    return;
  }

  // ── Avatar initial letter ────────────────────────────────
  const avatarEl = document.getElementById("profileAvatar");
  const initial  = (user.displayName || user.email || "U")[0].toUpperCase();
  if (avatarEl) avatarEl.textContent = initial;

  // ── Hero name ────────────────────────────────────────────
  const nameEl = document.getElementById("profileName");
  if (nameEl) nameEl.textContent = user.displayName || user.email;

  // ── Detail rows ──────────────────────────────────────────
  set("detailEmail",     user.email || "—");
  set("detailName",      user.displayName || "Not set");
  set("detailUid",       user.uid);
  set("detailVerified",  user.emailVerified ? "✓ Verified" : "✗ Not verified");
  set("detailCreated",   formatDate(user.metadata.creationTime));
  set("detailLastLogin", formatDate(user.metadata.lastSignInTime));

  // Provider (email, google.com, etc.)
  const provider = user.providerData[0]?.providerId || "—";
  set("detailProvider", provider === "password" ? "Email / Password" : provider);
});

function set(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function formatDate(dateString) {
  if (!dateString) return "—";
  const d = new Date(dateString);
  return d.toLocaleDateString("en-IN", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit"
  });
}

// ── Logout ───────────────────────────────────────────────────
document.getElementById("logoutBtn").addEventListener("click", async () => {
  await auth.signOut();
  window.location.href = "index.html";
});

// ── Sidebar Collapse ─────────────────────────────────────────
const sidebar       = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebarToggle");
sidebarToggle.addEventListener("click", () => {
  sidebar.classList.toggle("collapsed");
});

// ── Sidebar Mobile ───────────────────────────────────────────
const mobileMenuBtn  = document.getElementById("mobileMenuBtn");
const sidebarOverlay = document.getElementById("sidebarOverlay");
mobileMenuBtn.addEventListener("click", () => {
  sidebar.classList.add("mobile-open");
  sidebarOverlay.classList.add("visible");
  document.body.style.overflow = "hidden";
});
sidebarOverlay.addEventListener("click", () => {
  sidebar.classList.remove("mobile-open");
  sidebarOverlay.classList.remove("visible");
  document.body.style.overflow = "";
});

// ── Dark Mode Toggle ─────────────────────────────────────────
(function () {
  const html   = document.documentElement;
  const toggle = document.querySelector("[data-theme-toggle]");
  let theme    = window.matchMedia("(prefers-color-scheme: dark)").matches
                 ? "dark" : "light";
  html.setAttribute("data-theme", theme);

  const SUN  = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>`;
  const MOON = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;

  toggle.innerHTML = theme === "dark" ? SUN : MOON;
  toggle.addEventListener("click", () => {
    theme = theme === "dark" ? "light" : "dark";
    html.setAttribute("data-theme", theme);
    toggle.innerHTML = theme === "dark" ? SUN : MOON;
  });
})();
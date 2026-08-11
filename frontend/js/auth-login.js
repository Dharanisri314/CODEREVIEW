/*
 * auth-login.js
 * Handles the Login form → Firebase signInWithEmailAndPassword
 */
document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  // Clear previous alerts
  hideToast("login-alert");
  hideToast("login-success");
  clearFieldError("login-email",    "login-email-err");
  clearFieldError("login-password", "login-pass-err");

  const email    = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;

  // Validate FIRST
  let valid = true;
  if (!isValidEmail(email))  { showFieldError("login-email",    "login-email-err"); valid = false; }
  if (password.length < 6)   { showFieldError("login-password", "login-pass-err");  valid = false; }
  if (!valid) return;

  // Firebase call AFTER validation
  setLoading("login-btn", true);
  try {
    const { user } = await auth.signInWithEmailAndPassword(email, password);
    showToast("login-success", "login-success-msg", "Welcome back, " + user.email);

    // Redirect only on success
    setTimeout(() => {
      window.location.href = "dashboard.html";
    }, 800);

  } catch (err) {
    showToast("login-alert", "login-alert-msg", friendlyError(err.code));
  } finally {
    setLoading("login-btn", false);
  }
});
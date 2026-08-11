/*
 * auth-signup.js
 * Handles the Signup form → Firebase createUserWithEmailAndPassword
 */
document.getElementById("signup-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  // Clear previous alerts
  hideToast("signup-alert");
  hideToast("signup-success");
  clearFieldError("signup-email",    "signup-email-err");
  clearFieldError("signup-password", "signup-pass-err");
  clearFieldError("signup-confirm",  "signup-confirm-err");

  const email    = document.getElementById("signup-email").value.trim();
  const password = document.getElementById("signup-password").value;
  const confirm  = document.getElementById("signup-confirm").value;

  // Validate FIRST
  let valid = true;
  if (!isValidEmail(email))  { showFieldError("signup-email",    "signup-email-err");   valid = false; }
  if (password.length < 6)   { showFieldError("signup-password", "signup-pass-err");    valid = false; }
  if (password !== confirm)  { showFieldError("signup-confirm",  "signup-confirm-err"); valid = false; }
  if (!valid) return;

  // Firebase call AFTER validation
  setLoading("signup-btn", true);
  try {
    const { user } = await auth.createUserWithEmailAndPassword(email, password);
    showToast("signup-success", "signup-success-msg", "Account created! Welcome, " + user.email);

    // Redirect only on success
    setTimeout(() => {
      window.location.href = "dashboard.html";
    }, 800);

  } catch (err) {
    showToast("signup-alert", "signup-alert-msg", friendlyError(err.code));
  } finally {
    setLoading("signup-btn", false);
  }
});
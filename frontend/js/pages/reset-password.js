import { apiFetch, toast } from "../api.js";
import { navigate } from "../app.js";

const RULES = [
  { key: "length",  label: "More than 8 characters", test: v => v.length > 8 },
  { key: "upper",   label: "Uppercase letter",        test: v => /[A-Z]/.test(v) },
  { key: "lower",   label: "Lowercase letter",        test: v => /[a-z]/.test(v) },
  { key: "digit",   label: "Number",                  test: v => /[0-9]/.test(v) },
  { key: "special", label: "Special character",       test: v => /[^A-Za-z0-9]/.test(v) },
];

export async function renderResetPassword() {
  // Token lives in the hash query: #/reset-password?token=xxx
  const hashQuery = window.location.hash.split("?")[1] || "";
  const params = new URLSearchParams(hashQuery);
  const token = params.get("token") || "";

  const container = document.getElementById("auth-container");

  if (!token) {
    container.innerHTML = `
      <div class="auth-page">
        <div class="auth-card">
          <h1 class="auth-title">Invalid link</h1>
          <p class="auth-subtitle">This reset link is invalid or missing a token.</p>
          <a class="btn btn-primary btn-full mt-4" href="#/forgot-password">Request a new link</a>
        </div>
      </div>`;
    return;
  }

  container.innerHTML = `
    <div class="auth-page">
      <div class="auth-card">
        <div class="auth-logo">
          <div class="auth-logo-icon">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/>
            </svg>
          </div>
          <div>
            <div class="auth-logo-text">Brightloop</div>
            <div class="auth-logo-sub">Subscription Manager</div>
          </div>
        </div>
        <h1 class="auth-title">Set a new password</h1>
        <p class="auth-subtitle">Choose a strong password for your account.</p>

        <form id="reset-form" novalidate>
          <div class="form-group">
            <label class="form-label" for="rp-password">New Password <span class="required">*</span></label>
            <input class="form-control" type="password" id="rp-password" name="new_password" placeholder="Create a strong password" autocomplete="new-password" />
            <p class="form-error" id="rp-password-err"></p>
            <ul class="pw-checklist" id="rp-pw-checklist">
              ${RULES.map(r => `<li id="rp-rule-${r.key}">${r.label}</li>`).join("")}
            </ul>
          </div>
          <div class="form-group">
            <label class="form-label" for="rp-confirm">Confirm Password <span class="required">*</span></label>
            <input class="form-control" type="password" id="rp-confirm" name="confirm" placeholder="Repeat your password" autocomplete="new-password" />
            <p class="form-error" id="rp-confirm-err"></p>
          </div>
          <button class="btn btn-primary btn-full" type="submit" id="rp-btn">
            <span class="btn-text">Set Password</span>
          </button>
        </form>
      </div>
    </div>
  `;

  const pwInput = document.getElementById("rp-password");
  pwInput.addEventListener("input", () => {
    const v = pwInput.value;
    RULES.forEach(r => {
      const li = document.getElementById(`rp-rule-${r.key}`);
      if (li) li.classList.toggle("ok", r.test(v));
    });
  });

  const form = document.getElementById("reset-form");
  const btn = document.getElementById("rp-btn");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    ["rp-password-err", "rp-confirm-err"].forEach(id => {
      const el = document.getElementById(id);
      if (el) { el.textContent = ""; el.classList.remove("visible"); }
    });

    const newPass = form.new_password.value;
    const confirm = form.confirm.value;

    let valid = true;
    const failedRules = RULES.filter(r => !r.test(newPass));
    if (failedRules.length > 0) {
      document.getElementById("rp-password-err").textContent = `Password needs: ${failedRules.map(r => r.label.toLowerCase()).join(", ")}`;
      document.getElementById("rp-password-err").classList.add("visible"); valid = false;
    }
    if (newPass !== confirm) {
      document.getElementById("rp-confirm-err").textContent = "Passwords do not match";
      document.getElementById("rp-confirm-err").classList.add("visible"); valid = false;
    }
    if (!valid) return;

    btn.disabled = true;
    btn.querySelector(".btn-text").textContent = "Updating…";

    try {
      await apiFetch("/auth/reset-password", {
        method: "POST",
        body: { token, new_password: newPass }
      });
      toast("Password updated! Please sign in.", "success");
      navigate("/login");
    } catch (err) {
      toast(err.message, "error");
      document.getElementById("rp-password-err").textContent = err.message;
      document.getElementById("rp-password-err").classList.add("visible");
    } finally {
      btn.disabled = false;
      btn.querySelector(".btn-text").textContent = "Set Password";
    }
  });
}

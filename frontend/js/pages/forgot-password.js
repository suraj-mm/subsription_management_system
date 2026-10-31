import { apiFetch, toast } from "../api.js";

export async function renderForgotPassword() {
  const container = document.getElementById("auth-container");
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
        <h1 class="auth-title">Reset your password</h1>
        <p class="auth-subtitle">Enter your email and we'll send you a reset link.</p>

        <form id="forgot-form" novalidate>
          <div class="form-group">
            <label class="form-label" for="fp-email">Email address <span class="required">*</span></label>
            <input class="form-control" type="email" id="fp-email" name="email" placeholder="you@company.com" autocomplete="email" required />
            <p class="form-error" id="fp-email-err"></p>
          </div>
          <button class="btn btn-primary btn-full" type="submit" id="fp-btn">
            <span class="btn-text">Send Reset Link</span>
          </button>
        </form>

        <div id="fp-success" class="alert alert-success mt-4" style="display:none;">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" style="width:16px;height:16px;flex-shrink:0"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
          <span id="fp-success-msg">If the email is registered, a password reset link has been sent.</span>
        </div>

        <div id="fp-debug" class="alert alert-info mt-4" style="display:none;">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" style="width:16px;height:16px;flex-shrink:0"><path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          <div>
            <strong>Dev mode:</strong> <a id="fp-reset-link" href="#" target="_blank" style="word-break:break-all;"></a>
          </div>
        </div>

        <p style="margin-top:20px; text-align:center; font-size:13.5px; color:var(--color-text-muted);">
          <a href="#/login">← Back to sign in</a>
        </p>
      </div>
    </div>
  `;

  const form = document.getElementById("forgot-form");
  const btn = document.getElementById("fp-btn");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = form.email.value.trim();
    const errEl = document.getElementById("fp-email-err");
    errEl.textContent = ""; errEl.classList.remove("visible");

    if (!email) {
      errEl.textContent = "Email is required"; errEl.classList.add("visible"); return;
    }

    btn.disabled = true;
    btn.querySelector(".btn-text").textContent = "Sending…";

    try {
      const data = await apiFetch("/auth/forgot-password", {
        method: "POST",
        body: { email }
      });

      document.getElementById("fp-success").style.display = "flex";

      // Show debug link if backend returns one (DEBUG=true mode)
      if (data.reset_link) {
        const dbg = document.getElementById("fp-debug");
        dbg.style.display = "flex";
        const link = document.getElementById("fp-reset-link");
        link.href = data.reset_link;
        link.textContent = data.reset_link;
      }
    } catch (err) {
      toast(err.message, "error");
    } finally {
      btn.disabled = false;
      btn.querySelector(".btn-text").textContent = "Send Reset Link";
    }
  });
}

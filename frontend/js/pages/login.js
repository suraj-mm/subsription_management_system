import { apiLogin, toast, esc } from "../api.js";
import { setUser, navigate } from "../app.js";

export async function renderLogin() {
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
        <h1 class="auth-title">Welcome back</h1>
        <p class="auth-subtitle">Sign in to your account to continue</p>

        <form id="login-form" novalidate>
          <div class="form-group">
            <label class="form-label" for="email">Email address <span class="required">*</span></label>
            <input class="form-control" type="email" id="email" name="email" placeholder="you@company.com" autocomplete="email" required />
            <p class="form-error" id="email-err"></p>
          </div>
          <div class="form-group">
            <label class="form-label" for="password">Password <span class="required">*</span></label>
            <input class="form-control" type="password" id="password" name="password" placeholder="••••••••••" autocomplete="current-password" required />
            <p class="form-error" id="password-err"></p>
          </div>
          <div style="display:flex; justify-content:flex-end; margin-bottom:16px;">
            <a href="#/forgot-password" style="font-size:13px;">Forgot password?</a>
          </div>
          <button class="btn btn-primary btn-full" type="submit" id="login-btn">
            <span class="btn-text">Sign In</span>
          </button>
        </form>

        <p style="margin-top:20px; text-align:center; font-size:13.5px; color:var(--color-text-muted);">
          Don't have an account? <a href="#/signup">Create one</a>
        </p>
      </div>
    </div>
  `;

  const form = document.getElementById("login-form");
  const btn = document.getElementById("login-btn");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = form.email.value.trim();
    const password = form.password.value;

    // Clear errors
    document.getElementById("email-err").textContent = "";
    document.getElementById("password-err").textContent = "";

    if (!email) { document.getElementById("email-err").textContent = "Email is required"; document.getElementById("email-err").classList.add("visible"); return; }
    if (!password) { document.getElementById("password-err").textContent = "Password is required"; document.getElementById("password-err").classList.add("visible"); return; }

    btn.disabled = true;
    btn.querySelector(".btn-text").textContent = "Signing in…";

    try {
      const data = await apiLogin(email, password);
      localStorage.setItem("bl_token", data.access_token);
      setUser(data.user);
      toast(`Welcome back, ${data.user.name}!`, "success");
      navigate(data.role === "customer" ? "/subscriptions" : "/dashboard");
    } catch (err) {
      toast(err.message, "error");
      document.getElementById("password-err").textContent = err.message;
      document.getElementById("password-err").classList.add("visible");
    } finally {
      btn.disabled = false;
      btn.querySelector(".btn-text").textContent = "Sign In";
    }
  });
}

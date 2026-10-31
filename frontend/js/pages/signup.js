import { apiFetch, toast, esc } from "../api.js";
import { navigate } from "../app.js";

const RULES = [
  { key: "length",   label: "More than 8 characters", test: v => v.length > 8 },
  { key: "upper",    label: "Uppercase letter",        test: v => /[A-Z]/.test(v) },
  { key: "lower",    label: "Lowercase letter",        test: v => /[a-z]/.test(v) },
  { key: "digit",    label: "Number",                  test: v => /[0-9]/.test(v) },
  { key: "special",  label: "Special character",       test: v => /[^A-Za-z0-9]/.test(v) },
];

export async function renderSignup() {
  const container = document.getElementById("auth-container");
  container.innerHTML = `
    <div class="auth-page">
      <div class="auth-card" style="max-width:480px;">
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
        <h1 class="auth-title">Create your account</h1>
        <p class="auth-subtitle">Start managing your subscriptions today</p>

        <form id="signup-form" novalidate>
          <div class="form-group">
            <label class="form-label" for="s-name">Full Name <span class="required">*</span></label>
            <input class="form-control" type="text" id="s-name" name="name" placeholder="Jane Doe" autocomplete="name" required />
            <p class="form-error" id="name-err"></p>
          </div>
          <div class="form-group">
            <label class="form-label" for="s-email">Email address <span class="required">*</span></label>
            <input class="form-control" type="email" id="s-email" name="email" placeholder="you@company.com" autocomplete="email" required />
            <p class="form-error" id="email-err"></p>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label" for="s-company">Company</label>
              <input class="form-control" type="text" id="s-company" name="company" placeholder="Acme Corp" />
            </div>
            <div class="form-group">
              <label class="form-label" for="s-phone">Phone</label>
              <input class="form-control" type="tel" id="s-phone" name="phone" placeholder="+91 98765 43210" />
            </div>
          </div>
          <div class="form-group">
            <label class="form-label" for="s-password">Password <span class="required">*</span></label>
            <input class="form-control" type="password" id="s-password" name="password" placeholder="Create a strong password" autocomplete="new-password" />
            <p class="form-error" id="password-err"></p>
            <ul class="pw-checklist" id="pw-checklist">
              ${RULES.map(r => `<li id="rule-${r.key}">${esc(r.label)}</li>`).join("")}
            </ul>
          </div>
          <div class="form-group">
            <label class="form-label" for="s-confirm">Confirm Password <span class="required">*</span></label>
            <input class="form-control" type="password" id="s-confirm" name="confirm" placeholder="Repeat your password" autocomplete="new-password" />
            <p class="form-error" id="confirm-err"></p>
          </div>
          <button class="btn btn-primary btn-full" type="submit" id="signup-btn">
            <span class="btn-text">Create Account</span>
          </button>
        </form>

        <p style="margin-top:20px; text-align:center; font-size:13.5px; color:var(--color-text-muted);">
          Already have an account? <a href="#/login">Sign in</a>
        </p>
      </div>
    </div>
  `;

  const pwInput = document.getElementById("s-password");
  const checklist = document.getElementById("pw-checklist");

  pwInput.addEventListener("input", () => {
    const v = pwInput.value;
    RULES.forEach(r => {
      const li = document.getElementById(`rule-${r.key}`);
      if (li) li.classList.toggle("ok", r.test(v));
    });
  });

  const form = document.getElementById("signup-form");
  const btn = document.getElementById("signup-btn");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    // Clear errors
    ["name-err", "email-err", "password-err", "confirm-err"].forEach(id => {
      const el = document.getElementById(id);
      if (el) { el.textContent = ""; el.classList.remove("visible"); }
    });

    const name = form.name.value.trim();
    const email = form.email.value.trim();
    const password = form.password.value;
    const confirm = form.confirm.value;

    let valid = true;
    if (!name || name.length < 2) {
      document.getElementById("name-err").textContent = "Name must be at least 2 characters";
      document.getElementById("name-err").classList.add("visible"); valid = false;
    }
    if (!email) {
      document.getElementById("email-err").textContent = "Email is required";
      document.getElementById("email-err").classList.add("visible"); valid = false;
    }

    // Check password rules
    const failedRules = RULES.filter(r => !r.test(password));
    if (failedRules.length > 0) {
      document.getElementById("password-err").textContent = `Password needs: ${failedRules.map(r => r.label.toLowerCase()).join(", ")}`;
      document.getElementById("password-err").classList.add("visible"); valid = false;
    }
    if (password !== confirm) {
      document.getElementById("confirm-err").textContent = "Passwords do not match";
      document.getElementById("confirm-err").classList.add("visible"); valid = false;
    }
    if (!valid) return;

    btn.disabled = true;
    btn.querySelector(".btn-text").textContent = "Creating account…";

    try {
      await apiFetch("/auth/signup", {
        method: "POST",
        body: {
          name,
          email,
          password,
          company: form.company.value.trim() || null,
          phone: form.phone.value.trim() || null,
        }
      });
      toast("Account created! Please sign in.", "success");
      navigate("/login");
    } catch (err) {
      if (err.status === 409) {
        document.getElementById("email-err").textContent = "An account with this email already exists";
        document.getElementById("email-err").classList.add("visible");
      } else {
        toast(err.message, "error");
      }
    } finally {
      btn.disabled = false;
      btn.querySelector(".btn-text").textContent = "Create Account";
    }
  });
}

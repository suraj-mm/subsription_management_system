/* ===========================
   api.js — HTTP layer
   =========================== */

const API_BASE = "";

// ── Token storage ──
export function getToken() { return localStorage.getItem("bl_token"); }
export function setToken(t) { localStorage.setItem("bl_token", t); }
export function removeToken() { localStorage.removeItem("bl_token"); }

// ── Core fetch wrapper ──
export async function apiFetch(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const isFormData = opts.body instanceof URLSearchParams;
  if (!isFormData && opts.body && typeof opts.body === "object" && !(opts.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    opts = { ...opts, body: JSON.stringify(opts.body) };
  }

  const res = await fetch(API_BASE + path, { ...opts, headers });

  if (res.status === 401) {
    removeToken();
    window.location.hash = "#/login";
    throw new ApiError(401, "Session expired. Please log in again.");
  }

  let data;
  const ct = res.headers.get("Content-Type") || "";
  if (ct.includes("application/json")) {
    data = await res.json();
  } else {
    data = await res.text();
  }

  if (!res.ok) {
    const detail = (data && data.detail) ? data.detail : (typeof data === "string" ? data : "Request failed");
    throw new ApiError(res.status, detail, data);
  }

  return data;
}

// ── Form-encoded login (OAuth2 requirement) ──
export async function apiLogin(email, password) {
  const body = new URLSearchParams();
  body.append("username", email);
  body.append("password", password);

  const res = await fetch(API_BASE + "/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body
  });

  const data = await res.json();
  if (!res.ok) {
    const detail = data.detail || "Login failed";
    throw new ApiError(res.status, detail, data);
  }
  return data;
}

// ── Error class ──
export class ApiError extends Error {
  constructor(status, message, data = null) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

// ── Field-level 422 parser ──
// Returns { field: "message" } or null
export function parse422(err) {
  if (err.status !== 422 || !err.data || !err.data.detail) return null;
  const result = {};
  for (const item of err.data.detail) {
    const field = item.loc ? item.loc[item.loc.length - 1] : "error";
    result[field] = item.msg.replace("Value error, ", "");
  }
  return result;
}

// ── Toast ──
let toastContainer = null;

export function toast(msg, type = "default", duration = 4000) {
  if (!toastContainer) {
    toastContainer = document.getElementById("toast-container");
  }
  if (!toastContainer) return;

  const icons = {
    success: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>`,
    error:   `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>`,
    warning: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/></svg>`,
    default: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`
  };

  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.innerHTML = `
    <span class="toast-icon">${icons[type] || icons.default}</span>
    <span class="toast-msg">${esc(msg)}</span>
    <button class="toast-close" aria-label="Close">
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
    </button>
  `;

  el.querySelector(".toast-close").onclick = () => el.remove();
  toastContainer.appendChild(el);

  setTimeout(() => {
    el.style.opacity = "0";
    el.style.transition = "opacity 0.3s";
    setTimeout(() => el.remove(), 300);
  }, duration);
}

// ── Escape HTML ──
export function esc(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// ── Format money ──
export function fmtMoney(val) {
  if (val == null) return "—";
  return "₹" + Number(val).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ── Format date ──
export function fmtDate(val) {
  if (!val) return "—";
  return new Date(val).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

// ── Format datetime ──
export function fmtDatetime(val) {
  if (!val) return "—";
  return new Date(val).toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

// ── Apply 422 field errors to form ──
export function applyFieldErrors(form, errors) {
  // clear previous
  form.querySelectorAll(".form-control.error").forEach(el => el.classList.remove("error"));
  form.querySelectorAll(".form-error").forEach(el => { el.textContent = ""; el.classList.remove("visible"); });

  if (!errors) return;
  for (const [field, msg] of Object.entries(errors)) {
    const input = form.querySelector(`[name="${field}"]`);
    if (input) {
      input.classList.add("error");
      let errEl = input.parentElement.querySelector(".form-error");
      if (!errEl) {
        errEl = document.createElement("p");
        errEl.className = "form-error";
        input.parentElement.appendChild(errEl);
      }
      errEl.textContent = msg;
      errEl.classList.add("visible");
    }
  }
}

// ── Modal helpers ──
export function openModal(id) {
  const m = document.getElementById(id);
  if (m) { m.classList.add("open"); document.body.style.overflow = "hidden"; }
}

export function closeModal(id) {
  const m = document.getElementById(id);
  if (m) { m.classList.remove("open"); document.body.style.overflow = ""; }
}

export function closeAllModals() {
  document.querySelectorAll(".modal-backdrop.open").forEach(m => m.classList.remove("open"));
  document.body.style.overflow = "";
}

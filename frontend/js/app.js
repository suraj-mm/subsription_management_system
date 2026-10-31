/* ===========================
   app.js — Router + Auth State + Sidebar
   =========================== */

import { apiFetch, getToken, removeToken, toast, esc } from "./api.js";

// ── Auth state ──
let _user = null;

export function getUser() { return _user; }
export function setUser(u) { _user = u; }

export async function loadUser() {
  if (!getToken()) return null;
  try {
    _user = await apiFetch("/auth/me");
    return _user;
  } catch {
    removeToken();
    _user = null;
    return null;
  }
}

export function logout() {
  removeToken();
  _user = null;
  navigate("/login");
}

// ── Navigation ──
export function navigate(path) {
  window.location.hash = "#" + path;
}

// ── Icon SVGs ──
const ICONS = {
  dashboard: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></svg>`,
  subscriptions: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 10h16M4 14h16M4 18h16"/></svg>`,
  invoices: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>`,
  payments: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"/></svg>`,
  products: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>`,
  plans: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>`,
  taxes: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z"/></svg>`,
  discounts: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M7 7h.01M17 17h.01M7.586 3H4a1 1 0 00-1 1v3.586a1 1 0 00.293.707l10 10a1 1 0 001.414 0l5-5a1 1 0 000-1.414l-10-10A1 1 0 007.586 3z"/></svg>`,
  templates: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z"/></svg>`,
  customers: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>`,
  staff: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>`,
  profile: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M5.121 17.804A13.937 13.937 0 0112 16c2.5 0 4.847.655 6.879 1.804M15 10a3 3 0 11-6 0 3 3 0 016 0m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`,
  logout: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg>`,
};

// ── Sidebar definition ──
function getSidebarSections(role) {
  const sections = [];

  // All authenticated roles see dashboard and their own data
  sections.push({
    label: "Overview",
    items: [{ label: "Dashboard", icon: "dashboard", path: "/dashboard" }]
  });

  sections.push({
    label: "Subscriptions",
    items: [
      { label: "Subscriptions", icon: "subscriptions", path: "/subscriptions" },
      { label: "Invoices", icon: "invoices", path: "/invoices" },
      { label: "Payments", icon: "payments", path: "/payments" },
    ]
  });

  if (role === "admin" || role === "staff") {
    sections.push({
      label: "Catalog",
      items: [
        { label: "Products", icon: "products", path: "/products" },
        { label: "Plans", icon: "plans", path: "/plans" },
        { label: "Taxes", icon: "taxes", path: "/taxes" },
        { label: "Discounts", icon: "discounts", path: "/discounts" },
        { label: "Templates", icon: "templates", path: "/quotation-templates" },
      ]
    });

    sections.push({
      label: "People",
      items: [
        { label: "Customers", icon: "customers", path: "/customers" },
      ]
    });
  }

  if (role === "admin") {
    sections[sections.length - 1].items.push(
      { label: "Staff", icon: "staff", path: "/staff" }
    );
  }

  sections.push({
    label: "Account",
    items: [
      { label: "My Profile", icon: "profile", path: "/profile" },
    ]
  });

  return sections;
}

export function renderSidebar(currentPath) {
  const user = getUser();
  if (!user) return;

  const sidebar = document.getElementById("sidebar");
  if (!sidebar) return;

  const sections = getSidebarSections(user.role);
  const initials = (user.name || "U").split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase();

  let html = `
    <div class="sidebar-logo">
      <div class="sidebar-logo-icon">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/>
        </svg>
      </div>
      <div>
        <div class="sidebar-logo-text">Brightloop</div>
        <div class="sidebar-logo-sub">Subscription Manager</div>
      </div>
    </div>
  `;

  for (const section of sections) {
    html += `<div class="sidebar-section">
      <div class="sidebar-section-label">${esc(section.label)}</div>
      <ul class="sidebar-nav">`;

    for (const item of section.items) {
      const active = currentPath === item.path ? "active" : "";
      html += `<li>
        <a href="#${item.path}" class="${active}" data-path="${item.path}">
          ${ICONS[item.icon] || ""}
          ${esc(item.label)}
        </a>
      </li>`;
    }

    html += `</ul></div>`;
  }

  html += `
    <div class="sidebar-footer">
      <div class="sidebar-user">
        <div class="sidebar-user-avatar">${esc(initials)}</div>
        <div class="sidebar-user-info">
          <div class="sidebar-user-name">${esc(user.name || user.email)}</div>
          <div class="sidebar-user-role">${esc(user.role)}</div>
        </div>
      </div>
      <ul class="sidebar-nav">
        <li><button id="logout-btn">${ICONS.logout} Sign Out</button></li>
      </ul>
    </div>
  `;

  sidebar.innerHTML = html;

  sidebar.querySelector("#logout-btn")?.addEventListener("click", () => {
    logout();
  });
}

// ── Page registry ──
// Pages register themselves here
const _pages = {};
export function registerPage(path, loader) { _pages[path] = loader; }

// ── Router ──
async function route() {
  const hash = window.location.hash.replace(/^#/, "") || "/";
  const [basePath] = hash.split("?");

  // Extract dynamic segment e.g. /subscriptions/12
  let matchedPath = basePath;
  let params = {};

  // Try exact match first
  if (!_pages[basePath]) {
    // Try to match /thing/:id pattern
    for (const pattern of Object.keys(_pages)) {
      const parts = pattern.split("/");
      const hashParts = basePath.split("/");
      if (parts.length === hashParts.length) {
        const p = {};
        let ok = true;
        for (let i = 0; i < parts.length; i++) {
          if (parts[i].startsWith(":")) {
            p[parts[i].slice(1)] = hashParts[i];
          } else if (parts[i] !== hashParts[i]) {
            ok = false; break;
          }
        }
        if (ok) { matchedPath = pattern; params = p; break; }
      }
    }
  }

  const user = getUser() || await loadUser();

  // Public routes
  const publicPaths = ["/login", "/signup", "/forgot-password", "/reset-password"];
  if (publicPaths.includes(basePath)) {
    if (user && basePath === "/login") {
      navigate(user.role === "customer" ? "/subscriptions" : "/dashboard");
      return;
    }
    showAuth();
    const loader = _pages[basePath];
    if (loader) await loader({ params });
    return;
  }

  // Auth required
  if (!user) { navigate("/login"); return; }

  showApp();
  updateTopbar(basePath);
  renderSidebar(basePath);
  closeMobileSidebar();

  const loader = _pages[matchedPath];
  const content = document.getElementById("page-content");
  if (content) content.innerHTML = `<div class="loading-overlay"><div class="spinner"></div></div>`;

  if (loader) {
    try {
      await loader({ params });
    } catch (e) {
      console.error("Page load error", e);
      if (content) content.innerHTML = `<div class="empty-state"><p>Failed to load page. ${esc(e.message)}</p></div>`;
    }
  } else {
    if (content) content.innerHTML = `<div class="empty-state"><div class="empty-state-title">Page not found</div><p>The page "${esc(basePath)}" doesn't exist.</p></div>`;
  }
}

function showAuth() {
  document.getElementById("app-shell").style.display = "none";
  document.getElementById("auth-container").style.display = "";
}

function showApp() {
  document.getElementById("app-shell").style.display = "";
  document.getElementById("auth-container").style.display = "none";
}

function updateTopbar(path) {
  const titles = {
    "/dashboard": "Dashboard",
    "/subscriptions": "Subscriptions",
    "/invoices": "Invoices",
    "/payments": "Payments",
    "/products": "Products",
    "/plans": "Plans",
    "/taxes": "Taxes",
    "/discounts": "Discounts",
    "/quotation-templates": "Quotation Templates",
    "/customers": "Customers",
    "/staff": "Staff",
    "/profile": "My Profile",
  };
  const el = document.getElementById("topbar-title");
  if (el) {
    const key = Object.keys(titles).find(k => path.startsWith(k)) || path;
    el.textContent = titles[key] || "Brightloop";
  }
}

function closeMobileSidebar() {
  document.getElementById("sidebar")?.classList.remove("open");
  document.getElementById("sidebar-overlay")?.classList.remove("open");
}

// ── Bootstrap ──
export async function initApp() {
  // Hamburger toggle
  document.getElementById("topbar-hamburger")?.addEventListener("click", () => {
    document.getElementById("sidebar")?.classList.toggle("open");
    document.getElementById("sidebar-overlay")?.classList.toggle("open");
  });

  document.getElementById("sidebar-overlay")?.addEventListener("click", closeMobileSidebar);

  // Close modals on backdrop click
  document.addEventListener("click", (e) => {
    if (e.target.classList.contains("modal-backdrop")) {
      e.target.classList.remove("open");
      document.body.style.overflow = "";
    }
  });

  // Hash routing
  window.addEventListener("hashchange", route);
  await route();
}

import { apiFetch, toast, esc } from "../api.js";
import { openModal, closeModal } from "../api.js";

let _staff = [];

export async function renderStaff() {
  const content = document.getElementById("page-content");
  content.innerHTML = `
    <div class="page-header">
      <div class="page-header-text">
        <h1>Staff Management</h1>
        <p>Manage staff accounts (admin only)</p>
      </div>
      <button class="btn btn-primary" id="add-staff-btn">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" style="width:15px;height:15px"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
        Add Staff
      </button>
    </div>
    <div id="staff-table-wrap"><div class="loading-overlay"><div class="spinner"></div></div></div>

    <div class="modal-backdrop" id="staff-modal">
      <div class="modal" style="max-width:420px">
        <div class="modal-header">
          <span class="modal-title">Add Staff Member</span>
          <button class="modal-close" onclick="import('./api.js').then(m=>m.closeModal('staff-modal'))">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
        <div class="modal-body">
          <form id="staff-form" novalidate>
            <div class="form-group">
              <label class="form-label">Full Name <span class="required">*</span></label>
              <input class="form-control" type="text" id="sf-name" name="name" />
              <p class="form-error" id="sf-name-err"></p>
            </div>
            <div class="form-group">
              <label class="form-label">Email <span class="required">*</span></label>
              <input class="form-control" type="email" id="sf-email" name="email" />
              <p class="form-error" id="sf-email-err"></p>
            </div>
            <div class="form-group">
              <label class="form-label">Password <span class="required">*</span></label>
              <input class="form-control" type="password" id="sf-password" name="password" placeholder="Min 9 chars, upper, lower, digit, special" />
              <p class="form-error" id="sf-password-err"></p>
              <p class="form-hint">Must be &gt;8 chars with uppercase, lowercase, digit, and special character.</p>
            </div>
          </form>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="import('./api.js').then(m=>m.closeModal('staff-modal'))">Cancel</button>
          <button class="btn btn-primary" id="save-staff-btn"><span class="btn-text">Create Staff</span></button>
        </div>
      </div>
    </div>
  `;

  document.getElementById("add-staff-btn").addEventListener("click", () => {
    document.getElementById("sf-name").value = "";
    document.getElementById("sf-email").value = "";
    document.getElementById("sf-password").value = "";
    openModal("staff-modal");
  });

  document.getElementById("save-staff-btn").addEventListener("click", saveStaff);
  await refreshTable();
}

async function saveStaff() {
  const btn = document.getElementById("save-staff-btn");
  const name = document.getElementById("sf-name").value.trim();
  const email = document.getElementById("sf-email").value.trim();
  const password = document.getElementById("sf-password").value;

  let valid = true;
  ["sf-name-err", "sf-email-err", "sf-password-err"].forEach(id => {
    const el = document.getElementById(id);
    el.textContent = ""; el.classList.remove("visible");
  });

  if (!name || name.length < 2) { document.getElementById("sf-name-err").textContent = "Name must be ≥ 2 chars"; document.getElementById("sf-name-err").classList.add("visible"); valid = false; }
  if (!email) { document.getElementById("sf-email-err").textContent = "Email required"; document.getElementById("sf-email-err").classList.add("visible"); valid = false; }
  if (!password || password.length <= 8) { document.getElementById("sf-password-err").textContent = "Password must be > 8 chars"; document.getElementById("sf-password-err").classList.add("visible"); valid = false; }
  if (!valid) return;

  btn.disabled = true;
  try {
    await apiFetch("/admin/staff", { method: "POST", body: { name, email, password } });
    toast("Staff member created", "success");
    closeModal("staff-modal");
    await refreshTable();
  } catch (e) {
    if (e.status === 409) {
      document.getElementById("sf-email-err").textContent = "Email already exists";
      document.getElementById("sf-email-err").classList.add("visible");
    } else if (e.status === 422) {
      document.getElementById("sf-password-err").textContent = e.message;
      document.getElementById("sf-password-err").classList.add("visible");
    } else {
      toast(e.message, "error");
    }
  } finally { btn.disabled = false; }
}

async function refreshTable() {
  const wrap = document.getElementById("staff-table-wrap");
  wrap.innerHTML = `<div class="loading-overlay"><div class="spinner"></div></div>`;
  try {
    const data = await apiFetch("/admin/users?role=staff&page=1&size=50");
    _staff = data.items;
    if (!data.items.length) {
      wrap.innerHTML = `<div class="empty-state"><div class="empty-state-title">No staff yet</div><p>Add your first staff member to help manage subscriptions.</p></div>`;
      return;
    }
    const rows = data.items.map(s => `
      <tr>
        <td><div style="font-weight:600">${esc(s.name)}</div><div style="font-size:12px;color:var(--color-text-muted)">${esc(s.email)}</div></td>
        <td><span class="badge badge-staff">Staff</span></td>
        <td><span class="badge badge-${s.is_active ? "active" : "closed"}">${s.is_active ? "Active" : "Inactive"}</span></td>
        <td>${new Date(s.created_at).toLocaleDateString("en-IN")}</td>
        <td class="col-actions">
          <button class="btn btn-xs ${s.is_active ? "btn-danger" : "btn-ghost"} toggle-btn" data-id="${s.id}" data-active="${s.is_active}">${s.is_active ? "Deactivate" : "Activate"}</button>
        </td>
      </tr>`).join("");
    wrap.innerHTML = `<div class="table-wrapper"><table><thead><tr><th>Name / Email</th><th>Role</th><th>Status</th><th>Added</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`;
    wrap.querySelectorAll(".toggle-btn").forEach(btn => btn.addEventListener("click", async () => {
      const isActive = btn.dataset.active === "true";
      try {
        await apiFetch(`/admin/users/${btn.dataset.id}`, { method: "PATCH", body: { is_active: !isActive } });
        toast(isActive ? "Staff deactivated" : "Staff activated", "success");
        await refreshTable();
      } catch (e) { toast(e.message, "error"); }
    }));
  } catch (e) {
    wrap.innerHTML = `<div class="empty-state"><p>Error: ${esc(e.message)}</p></div>`;
  }
}

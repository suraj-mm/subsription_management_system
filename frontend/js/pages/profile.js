import { apiFetch, toast, esc } from "../api.js";
import { getUser, setUser } from "../app.js";

export async function renderProfile() {
  const content = document.getElementById("page-content");
  const user = getUser();

  content.innerHTML = `
    <div class="page-header">
      <div class="page-header-text">
        <h1>My Profile</h1>
        <p>Update your personal information</p>
      </div>
    </div>

    <div style="max-width:560px">
      <div class="card">
        <div class="card-header"><span class="card-title">Account Details</span></div>
        <div class="card-body">
          <div style="display:flex;align-items:center;gap:16px;margin-bottom:24px">
            <div style="width:56px;height:56px;border-radius:50%;background:var(--color-primary);color:#fff;font-size:20px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0">
              ${esc((user?.name || "U").split(" ").map(w=>w[0]).join("").slice(0,2).toUpperCase())}
            </div>
            <div>
              <div style="font-weight:700;font-size:16px">${esc(user?.name || "—")}</div>
              <div style="color:var(--color-text-muted);font-size:13px">${esc(user?.email || "—")}</div>
              <span class="badge badge-${user?.role}">${esc(user?.role || "—")}</span>
            </div>
          </div>

          <form id="profile-form" novalidate>
            <div class="form-group">
              <label class="form-label">Full Name <span class="required">*</span></label>
              <input class="form-control" type="text" id="pf-name" name="name" value="${esc(user?.name || "")}" />
              <p class="form-error" id="pf-name-err"></p>
            </div>
            <div class="form-group">
              <label class="form-label">Email</label>
              <input class="form-control" type="email" value="${esc(user?.email || "")}" disabled />
              <p class="form-hint">Email cannot be changed. Contact admin if needed.</p>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Company</label>
                <input class="form-control" type="text" id="pf-company" name="company" value="${esc(user?.company || "")}" placeholder="Your company name" />
              </div>
              <div class="form-group">
                <label class="form-label">Phone</label>
                <input class="form-control" type="tel" id="pf-phone" name="phone" value="${esc(user?.phone || "")}" placeholder="+91 98765 43210" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Address</label>
              <textarea class="form-control" id="pf-address" name="address" rows="2" placeholder="Your billing address">${esc(user?.address || "")}</textarea>
            </div>
            <button class="btn btn-primary" type="submit" id="save-profile-btn">
              <span class="btn-text">Save Changes</span>
            </button>
          </form>
        </div>
      </div>

      <div class="card" style="margin-top:20px">
        <div class="card-header"><span class="card-title">Password</span></div>
        <div class="card-body">
          <p style="font-size:13.5px;color:var(--color-text-muted);margin-bottom:16px">To change your password, use the forgot password flow.</p>
          <a class="btn btn-secondary" href="#/forgot-password">Change Password</a>
        </div>
      </div>
    </div>
  `;

  document.getElementById("profile-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("save-profile-btn");
    const name = document.getElementById("pf-name").value.trim();
    const nameErr = document.getElementById("pf-name-err");
    nameErr.classList.remove("visible");

    if (!name || name.length < 2) { nameErr.textContent = "Name must be ≥ 2 chars"; nameErr.classList.add("visible"); return; }

    btn.disabled = true;
    btn.querySelector(".btn-text").textContent = "Saving…";

    try {
      const updated = await apiFetch("/auth/me", {
        method: "PATCH",
        body: {
          name,
          company: document.getElementById("pf-company").value.trim() || null,
          phone: document.getElementById("pf-phone").value.trim() || null,
          address: document.getElementById("pf-address").value.trim() || null,
        }
      });
      setUser(updated);
      toast("Profile updated successfully", "success");
      // Re-render to refresh sidebar initials
      await renderProfile();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      btn.disabled = false;
      if (btn.querySelector(".btn-text")) btn.querySelector(".btn-text").textContent = "Save Changes";
    }
  });
}

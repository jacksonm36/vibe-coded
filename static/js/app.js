const API = '/api';

function qs(sel, el = document) { return el.querySelector(sel); }
function qsAll(sel, el = document) { return el.querySelectorAll(sel); }

function apiErrorDetail(detail) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(d => d.msg || JSON.stringify(d)).join('; ');
  if (detail && typeof detail === 'object') return detail.msg || JSON.stringify(detail);
  return null;
}

function showError(e) {
  const msg = e && typeof e === 'object' && e.message ? e.message : (typeof e === 'string' ? e : String(e));
  alert(msg || 'An error occurred');
}

async function fetchJSON(url, opts = {}) {
  const r = await fetch(url, { headers: { 'Content-Type': 'application/json', ...opts.headers }, ...opts });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    const msg = apiErrorDetail(body.detail) || body.detail || r.statusText;
    throw new Error(msg);
  }
  return r.status === 204 ? null : r.json();
}

let currentPage = 'dashboard';
let projects = [];
let inventories = [];
let credentials = [];
let jobTemplates = [];
let jobs = [];

const REFRESH_INTERVAL_MS = 4000;
let refreshIntervalId = null;
let jobPollIntervalId = null;

function clearRefresh() {
  if (refreshIntervalId) {
    clearInterval(refreshIntervalId);
    refreshIntervalId = null;
  }
}

function startRefresh() {
  clearRefresh();
  refreshIntervalId = setInterval(async () => {
    try {
      await loadAll();
      render();
    } catch (err) {
      console.error('Auto-refresh:', err);
    }
  }, REFRESH_INTERVAL_MS);
}

function setPage(page) {
  currentPage = page;
  qsAll('.sidebar-nav a').forEach(a => {
    a.classList.toggle('active', a.dataset.page === page);
  });
  render();
  clearRefresh();
  // Auto-refresh on all main pages so project/credential/template changes
  // and job status updates appear without manual reload.
  startRefresh();
}

function render() {
  const content = qs('#content');
  if (currentPage === 'dashboard') content.innerHTML = renderDashboard();
  else if (currentPage === 'projects') content.innerHTML = renderProjects();
  else if (currentPage === 'inventories') content.innerHTML = renderInventories();
  else if (currentPage === 'credentials') content.innerHTML = renderCredentials();
  else if (currentPage === 'templates') content.innerHTML = renderTemplates();
  else if (currentPage === 'jobs') content.innerHTML = renderJobs();
  bindContentEvents();
}

function bindContentEvents() {
  qsAll('.nav-link').forEach(a => {
    a.onclick = (e) => { e.preventDefault(); setPage(a.dataset.page); };
  });
  qsAll('[data-action]').forEach(el => {
    const action = el.dataset.action;
    const id = el.dataset.id ? parseInt(el.dataset.id, 10) : null;
    el.onclick = () => runAction(action, id, el);
  });
}

// Delegate clicks so modal buttons (e.g. Close) work when added dynamically
document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-action]');
  if (!el || el.closest('#content')) return; // #content uses bindContentEvents
  e.preventDefault();
  const action = el.dataset.action;
  const id = el.dataset.id ? parseInt(el.dataset.id, 10) : null;
  runAction(action, id, el);
});

function runAction(action, id, el) {
  if (action === 'close-modal') { closeModal(); reloadAndRender(); return; }
  if (action === 'create-project') openProjectModal();
  if (action === 'edit-project') openProjectModal(id);
  if (action === 'delete-project') deleteProject(id);
  if (action === 'create-inventory') openInventoryModal();
  if (action === 'edit-inventory') openInventoryModal(id);
  if (action === 'delete-inventory') deleteInventory(id);
  if (action === 'create-credential') openCredentialModal();
  if (action === 'edit-credential') openCredentialModal(id);
  if (action === 'delete-credential') deleteCredential(id);
  if (action === 'create-template') openTemplateModal();
  if (action === 'edit-template') openTemplateModal(id);
  if (action === 'delete-template') deleteTemplate(id);
  if (action === 'launch-job') launchJob(id);
  if (action === 'view-job') viewJob(id);
  if (action === 'delete-job') deleteJob(id);
  if (action === 'delete-job-history') deleteJobHistory();
  if (action === 'pull-project') pullProject(id);
}

function renderDashboard() {
  const recent = jobs.slice(0, 10);
  const running = jobs.filter(j => j.status === 'running').length;
  const failed = jobs.filter(j => j.status === 'failed').length;
  return `
    <h1 class="page-title">Dashboard</h1>
    <div class="dash-cards">
      <div class="dash-card"><h3>${projects.length}</h3><p>Projects</p></div>
      <div class="dash-card"><h3>${jobTemplates.length}</h3><p>Job Templates</p></div>
      <div class="dash-card"><h3>${jobs.length}</h3><p>Total Jobs</p></div>
      <div class="dash-card"><h3>${running}</h3><p>Running</p></div>
      <div class="dash-card"><h3>${failed}</h3><p>Failed</p></div>
    </div>
    <div class="card">
      <div class="card-header">Recent Jobs</div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>ID</th><th>Playbook</th><th>Status</th><th>Started</th><th></th></tr></thead>
          <tbody>
            ${recent.length ? recent.map(j => `
              <tr>
                <td>${j.id}</td>
                <td>${escapeHtml(j.playbook_path)}</td>
                <td><span class="badge badge-${j.status}">${j.status}</span></td>
                <td>${j.started_at ? new Date(j.started_at).toLocaleString() : '—'}</td>
                <td><button class="btn btn-sm btn-secondary" data-action="view-job" data-id="${j.id}">View</button></td>
              </tr>
            `).join('') : '<tr><td colspan="5" class="empty-state">No jobs yet. Create a job template and launch a job.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderProjects() {
  return `
    <h1 class="page-title">Projects</h1>
    <div class="card">
      <div class="card-header">
        Projects
        <button class="btn btn-primary btn-sm" data-action="create-project">+ Add Project</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Name</th><th>Description</th><th>Git repo</th><th>Updated</th><th></th></tr></thead>
          <tbody>
            ${projects.length ? projects.map(p => `
              <tr>
                <td>${escapeHtml(p.name)}</td>
                <td>${escapeHtml(p.description || '—')}</td>
                <td>${p.git_url ? escapeHtml(p.git_url) : '—'}</td>
                <td>${new Date(p.updated_at).toLocaleString()}</td>
                <td>
                  ${p.git_url ? `<button class="btn btn-sm btn-primary" data-action="pull-project" data-id="${p.id}" title="Pull playbooks from Git">Pull</button>` : ''}
                  <button class="btn btn-sm btn-secondary" data-action="edit-project" data-id="${p.id}">Edit</button>
                  <button class="btn btn-sm btn-danger" data-action="delete-project" data-id="${p.id}">Delete</button>
                </td>
              </tr>
            `).join('') : '<tr><td colspan="5" class="empty-state">No projects. Create one to get started.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderInventories() {
  return `
    <h1 class="page-title">Inventories</h1>
    <div class="card">
      <div class="card-header">
        Inventories
        <button class="btn btn-primary btn-sm" data-action="create-inventory">+ Add Inventory</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Name</th><th>Project</th><th>Updated</th><th></th></tr></thead>
          <tbody>
            ${inventories.length ? inventories.map(inv => {
              const proj = projects.find(p => p.id === inv.project_id);
              return `
              <tr>
                <td>${escapeHtml(inv.name)}</td>
                <td>${proj ? escapeHtml(proj.name) : inv.project_id}</td>
                <td>${new Date(inv.updated_at).toLocaleString()}</td>
                <td>
                  <button class="btn btn-sm btn-secondary" data-action="edit-inventory" data-id="${inv.id}">Edit</button>
                  <button class="btn btn-sm btn-danger" data-action="delete-inventory" data-id="${inv.id}">Delete</button>
                </td>
              </tr>`;
            }).join('') : '<tr><td colspan="4" class="empty-state">No inventories. Add one for a project.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderCredentials() {
  return `
    <h1 class="page-title">Credentials</h1>
    <div class="card">
      <div class="card-header">
        Credentials
        <button class="btn btn-primary btn-sm" data-action="create-credential">+ Add Credential</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Name</th><th>Kind</th><th>Project</th><th></th></tr></thead>
          <tbody>
            ${credentials.length ? credentials.map(c => {
              const proj = projects.find(p => p.id === c.project_id);
              return `
              <tr>
                <td>${escapeHtml(c.name)}</td>
                <td>${escapeHtml(c.kind)}</td>
                <td>${proj ? escapeHtml(proj.name) : c.project_id}</td>
                <td>
                  <button class="btn btn-sm btn-secondary" data-action="edit-credential" data-id="${c.id}">Edit</button>
                  <button class="btn btn-sm btn-danger" data-action="delete-credential" data-id="${c.id}">Delete</button>
                </td>
              </tr>`;
            }).join('') : '<tr><td colspan="4" class="empty-state">No credentials. Add SSH or Vault credentials.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderTemplates() {
  return `
    <h1 class="page-title">Job Templates</h1>
    <div class="card">
      <div class="card-header">
        Job Templates
        <button class="btn btn-primary btn-sm" data-action="create-template">+ Add Template</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Name</th><th>Playbook</th><th>Project</th><th></th></tr></thead>
          <tbody>
            ${jobTemplates.length ? jobTemplates.map(jt => {
              const proj = projects.find(p => p.id === jt.project_id);
              const sched = jt.schedule_enabled && jt.schedule_cron ? `<span class="badge badge-running" title="${escapeHtml(jt.schedule_cron)}">Schedule</span>` : '';
              return `
              <tr>
                <td>${escapeHtml(jt.name)} ${sched}</td>
                <td>${escapeHtml(jt.playbook_path)}</td>
                <td>${proj ? escapeHtml(proj.name) : jt.project_id}</td>
                <td>
                  <button class="btn btn-sm btn-primary" data-action="launch-job" data-id="${jt.id}">Launch</button>
                  <button class="btn btn-sm btn-secondary" data-action="edit-template" data-id="${jt.id}">Edit</button>
                  <button class="btn btn-sm btn-danger" data-action="delete-template" data-id="${jt.id}">Delete</button>
                </td>
              </tr>`;
            }).join('') : '<tr><td colspan="4" class="empty-state">No job templates. Create one to run playbooks.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderJobs() {
  return `
    <h1 class="page-title">Jobs</h1>
    <div class="card">
      <div class="card-header">
        Job history
        <button class="btn btn-danger btn-sm float-right" data-action="delete-job-history">Clear all</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>ID</th><th>Playbook</th><th>Status</th><th>Started</th><th>Finished</th><th></th></tr></thead>
          <tbody>
            ${jobs.length ? jobs.map(j => `
              <tr>
                <td>${j.id}</td>
                <td>${escapeHtml(j.playbook_path)}</td>
                <td><span class="badge badge-${j.status}">${j.status}</span></td>
                <td>${j.started_at ? new Date(j.started_at).toLocaleString() : '—'}</td>
                <td>${j.finished_at ? new Date(j.finished_at).toLocaleString() : '—'}</td>
                <td>
                  <button class="btn btn-sm btn-secondary" data-action="view-job" data-id="${j.id}">View log</button>
                  <button class="btn btn-sm btn-danger" data-action="delete-job" data-id="${j.id}">Delete</button>
                </td>
              </tr>
            `).join('') : '<tr><td colspan="6" class="empty-state">No jobs yet.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function escapeHtml(s) {
  if (s == null) return '';
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

function showModal(title, body, footer = '') {
  const overlay = qs('#modal-overlay');
  const modal = qs('#modal');
  modal.innerHTML = `<div class="modal-header">${escapeHtml(title)}</div><div class="modal-body">${body}</div><div class="modal-footer">${footer}</div>`;
  overlay.classList.remove('hidden');
}

function closeModal() {
  if (jobPollIntervalId) {
    clearInterval(jobPollIntervalId);
    jobPollIntervalId = null;
  }
  qs('#modal-overlay').classList.add('hidden');
}

qs('#modal-overlay').onclick = (e) => { if (e.target === e.currentTarget) closeModal(); };

function openProjectModal(id) {
  const p = id ? projects.find(x => x.id === id) : null;
  const credOptions = credentials.filter(c => c.kind === 'ssh' || c.kind === 'git').map(c => `<option value="${c.id}" ${p && p.git_credential_id === c.id ? 'selected' : ''}>${escapeHtml(c.name)} (${c.kind})</option>`).join('');
  showModal(
    p ? 'Edit Project' : 'New Project',
    `
      <div class="form-group">
        <label>Name</label>
        <input type="text" id="modal-name" value="${p ? escapeHtml(p.name) : ''}" placeholder="Project name">
      </div>
      <div class="form-group">
        <label>Description</label>
        <textarea id="modal-desc" placeholder="Optional">${p ? escapeHtml(p.description || '') : ''}</textarea>
      </div>
      <div class="form-group">
        <label>Git / GitHub repo URL (optional)</label>
        <input type="text" id="modal-git-url" value="${p && p.git_url ? escapeHtml(p.git_url) : ''}" placeholder="https://github.com/owner/repo.git or git@github.com:owner/repo.git">
      </div>
      <div class="form-group">
        <label>Git branch</label>
        <input type="text" id="modal-git-branch" value="${p && p.git_branch ? escapeHtml(p.git_branch) : 'main'}" placeholder="main">
      </div>
      <div class="form-group">
        <label>Git credential (for private repos: SSH key or Git token)</label>
        <select id="modal-git-cred"><option value="">— None (public repo) —</option>${credOptions}</select>
      </div>
    `,
    `<button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
     <button class="btn btn-primary" id="modal-save-project" data-id="${id || ''}">Save</button>`
  );
  qs('#modal-save-project').onclick = async () => {
    const name = qs('#modal-name').value.trim();
    if (!name) return;
    const git_url = qs('#modal-git-url').value.trim() || null;
    const git_branch = qs('#modal-git-branch').value.trim() || 'main';
    const gcid = qs('#modal-git-cred').value;
    const git_credential_id = gcid ? parseInt(gcid, 10) : null;
    try {
      if (id) await fetchJSON(`${API}/projects/${id}`, { method: 'PATCH', body: JSON.stringify({ name, description: qs('#modal-desc').value, git_url, git_branch, git_credential_id }) });
      else await fetchJSON(`${API}/projects`, { method: 'POST', body: JSON.stringify({ name, description: qs('#modal-desc').value, git_url, git_branch, git_credential_id }) });
      closeModal();
      reloadAndRender();
    } catch (e) { showError(e); }
  };
}

function openInventoryModal(id) {
  const inv = id ? inventories.find(x => x.id === id) : null;
  showModal(
    inv ? 'Edit Inventory' : 'New Inventory',
    `
      <div class="form-group">
        <label>Project</label>
        <select id="modal-inv-project">${projects.map(p => `<option value="${p.id}" ${inv && inv.project_id === p.id ? 'selected' : ''}>${escapeHtml(p.name)}</option>`).join('')}</select>
      </div>
      <div class="form-group">
        <label>Name</label>
        <input type="text" id="modal-name" value="${inv ? escapeHtml(inv.name) : ''}" placeholder="Inventory name">
      </div>
      <div class="form-group">
        <label>Content (INI or YAML)</label>
        <textarea id="modal-content" placeholder="[all]\nhost1\nhost2" style="min-height:180px">${inv ? escapeHtml(inv.content) : ''}</textarea>
      </div>
    `,
    `<button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
     <button class="btn btn-primary" id="modal-save-inv" data-id="${id || ''}">Save</button>`
  );
  const sel = qs('#modal-inv-project');
  if (!inv && projects[0]) sel.value = projects[0].id;
  qs('#modal-save-inv').onclick = async () => {
    const name = qs('#modal-name').value.trim();
    const project_id = parseInt(sel.value, 10);
    if (!name || !project_id) return;
    try {
      if (id) await fetchJSON(`${API}/inventories/${id}`, { method: 'PATCH', body: JSON.stringify({ name, content: qs('#modal-content').value }) });
      else await fetchJSON(`${API}/inventories`, { method: 'POST', body: JSON.stringify({ project_id, name, content: qs('#modal-content').value }) });
      closeModal();
      reloadAndRender();
    } catch (e) { showError(e); }
  };
}

function openCredentialModal(id) {
  const c = id ? credentials.find(x => x.id === id) : null;
  showModal(
    c ? 'Edit Credential' : 'New Credential',
    `
      <div class="form-group">
        <label>Project</label>
        <select id="modal-cred-project">${projects.map(p => `<option value="${p.id}" ${c && c.project_id === p.id ? 'selected' : ''}>${escapeHtml(p.name)}</option>`).join('')}</select>
      </div>
      <div class="form-group">
        <label>Name</label>
        <input type="text" id="modal-name" value="${c ? escapeHtml(c.name) : ''}" placeholder="Credential name">
      </div>
      <div class="form-group">
        <label>Kind</label>
        <select id="modal-kind">
          <option value="ssh" ${c && c.kind === 'ssh' ? 'selected' : ''}>SSH private key (remote servers / Git SSH)</option>
          <option value="password" ${c && c.kind === 'password' ? 'selected' : ''}>SSH password</option>
          <option value="vault" ${c && c.kind === 'vault' ? 'selected' : ''}>Ansible Vault password</option>
          <option value="git" ${c && c.kind === 'git' ? 'selected' : ''}>Git HTTPS token (GitHub/GitLab)</option>
        </select>
      </div>
      <div class="form-group">
        <label>Secret</label>
        <textarea id="modal-secret" placeholder="${c ? 'Leave blank to keep existing' : 'Paste private key, password, or token'}">${c ? '' : ''}</textarea>
      </div>
    `,
    `<button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
     <button class="btn btn-primary" id="modal-save-cred" data-id="${id || ''}">Save</button>`
  );
  const sel = qs('#modal-cred-project');
  if (!c && projects[0]) sel.value = projects[0].id;
  qs('#modal-save-cred').onclick = async () => {
    const name = qs('#modal-name').value.trim();
    const project_id = parseInt(sel.value, 10);
    const kind = qs('#modal-kind').value;
    const secret = qs('#modal-secret').value;
    if (!name || !project_id) return;
    if (!id && !secret) { alert('Secret is required for new credential'); return; }
    try {
      if (id) {
        const body = { name, kind };
        if (secret) body.secret = secret;
        await fetchJSON(`${API}/credentials/${id}`, { method: 'PATCH', body: JSON.stringify(body) });
      } else await fetchJSON(`${API}/credentials`, { method: 'POST', body: JSON.stringify({ project_id, name, kind, secret: secret || 'x', extra: '' }) });
      closeModal();
      reloadAndRender();
    } catch (e) { showError(e); }
  };
}

function openTemplateModal(id) {
  const jt = id ? jobTemplates.find(x => x.id === id) : null;
  const invOptions = inventories.map(inv => `<option value="${inv.id}" ${jt && jt.inventory_id === inv.id ? 'selected' : ''}>${escapeHtml(inv.name)} (${inv.project_id})</option>`).join('');
  const credOptions = credentials.map(c => `<option value="${c.id}" ${jt && jt.credential_id === c.id ? 'selected' : ''}>${escapeHtml(c.name)}</option>`).join('');
  showModal(
    jt ? 'Edit Job Template' : 'New Job Template',
    `
      <div class="form-group">
        <label>Project</label>
        <select id="modal-tpl-project">${projects.map(p => `<option value="${p.id}" ${jt && jt.project_id === p.id ? 'selected' : ''}>${escapeHtml(p.name)}</option>`).join('')}</select>
      </div>
      <div class="form-group">
        <label>Name</label>
        <input type="text" id="modal-name" value="${jt ? escapeHtml(jt.name) : ''}" placeholder="Template name">
      </div>
      <div class="form-group">
        <label>Playbook or script path</label>
        <input type="text" id="modal-playbook" value="${jt ? escapeHtml(jt.playbook_path) : ''}" placeholder="e.g. playbook.yml (Ansible) or clamscan.sh (script)">
      </div>
      <div class="form-group">
        <label>Inventory</label>
        <select id="modal-inv"><option value="">— None —</option>${invOptions}</select>
      </div>
      <div class="form-group">
        <label>Credential (SSH key, SSH password, or Vault)</label>
        <select id="modal-cred"><option value="">— None —</option>${credOptions}</select>
      </div>
      <div class="form-group">
        <label>Extra vars (YAML/JSON)</label>
        <textarea id="modal-extra">${jt ? escapeHtml(jt.extra_vars || '') : ''}</textarea>
      </div>
      <div class="form-group">
        <label><input type="checkbox" id="modal-schedule-enabled" ${jt && jt.schedule_enabled ? 'checked' : ''}> Run on schedule (cron)</label>
      </div>
      <div class="form-group" id="modal-schedule-fields">
        <label>Cron (min hour day month dow)</label>
        <input type="text" id="modal-schedule-cron" value="${jt && jt.schedule_cron ? escapeHtml(jt.schedule_cron) : ''}" placeholder="0 2 * * *">
        <small class="text-muted">0 2 * * * = daily 2:00 · 0 */6 * * * = every 6h · 0 3 * * 1 = Mon 3:00</small>
      </div>
      <div class="form-group" id="modal-schedule-tz-wrap">
        <label>Timezone</label>
        <input type="text" id="modal-schedule-tz" value="${jt && jt.schedule_tz ? escapeHtml(jt.schedule_tz) : 'UTC'}" placeholder="UTC">
      </div>
      <div class="form-group" id="modal-next-run-wrap" style="display:none">
        <label>Next run</label>
        <p id="modal-next-run" class="text-muted">—</p>
      </div>
    `,
    `<button class="btn btn-secondary" data-action="close-modal">Cancel</button>
     <button class="btn btn-primary" id="modal-save-tpl" data-id="${id || ''}">Save</button>`
  );
  if (!jt && projects[0]) qs('#modal-tpl-project').value = projects[0].id;
  const scheduleEnabled = qs('#modal-schedule-enabled');
  const nextRunWrap = qs('#modal-next-run-wrap');
  const nextRunEl = qs('#modal-next-run');
  function toggleScheduleFields() {
    const on = scheduleEnabled.checked;
    qs('#modal-schedule-fields').style.display = on ? 'block' : 'none';
    qs('#modal-schedule-tz-wrap').style.display = on ? 'block' : 'none';
    nextRunWrap.style.display = on ? 'block' : 'none';
    if (on && id) fetchJSON(`${API}/job_templates/${id}/next_run`).then(r => { nextRunEl.textContent = r.next_run ? new Date(r.next_run).toLocaleString() : '—'; }).catch(() => {});
    else if (on) nextRunEl.textContent = 'Save to see next run';
  }
  scheduleEnabled.onchange = toggleScheduleFields;
  toggleScheduleFields();
  qs('#modal-save-tpl').onclick = async () => {
    const name = qs('#modal-name').value.trim();
    const playbook_path = qs('#modal-playbook').value.trim();
    const project_id = parseInt(qs('#modal-tpl-project').value, 10);
    const invVal = qs('#modal-inv').value;
    const credVal = qs('#modal-cred').value;
    const inventory_id = invVal ? parseInt(invVal, 10) : null;
    const credential_id = credVal ? parseInt(credVal, 10) : null;
    const extra_vars = qs('#modal-extra').value;
    const schedule_enabled = scheduleEnabled.checked;
    const schedule_cron = schedule_enabled ? qs('#modal-schedule-cron').value.trim() || null : null;
    const schedule_tz = schedule_enabled ? (qs('#modal-schedule-tz').value.trim() || 'UTC') : null;
    if (!name || !playbook_path || !project_id) return;
    try {
      const body = { name, playbook_path, inventory_id, credential_id, extra_vars, schedule_enabled, schedule_cron, schedule_tz };
      if (id) await fetchJSON(`${API}/job_templates/${id}`, { method: 'PATCH', body: JSON.stringify(body) });
      else await fetchJSON(`${API}/job_templates`, { method: 'POST', body: JSON.stringify({ project_id, ...body }) });
      closeModal();
      reloadAndRender();
    } catch (e) { showError(e); }
  };
}

async function deleteProject(id) {
  if (!confirm('Delete this project and all its inventories, credentials, and templates?')) return;
  try {
    await fetchJSON(`${API}/projects/${id}`, { method: 'DELETE' });
    reloadAndRender();
  } catch (e) { showError(e); }
}

async function deleteInventory(id) {
  if (!confirm('Delete this inventory?')) return;
  try {
    await fetchJSON(`${API}/inventories/${id}`, { method: 'DELETE' });
    reloadAndRender();
  } catch (e) { showError(e); }
}

async function deleteCredential(id) {
  if (!confirm('Delete this credential?')) return;
  try {
    await fetchJSON(`${API}/credentials/${id}`, { method: 'DELETE' });
    reloadAndRender();
  } catch (e) { showError(e); }
}

async function deleteTemplate(id) {
  if (!confirm('Delete this job template?')) return;
  try {
    await fetchJSON(`${API}/job_templates/${id}`, { method: 'DELETE' });
    reloadAndRender();
  } catch (e) { showError(e); }
}

async function pullProject(id) {
  const p = projects.find(x => x.id === id);
  if (!p || !p.git_url) return;
  try {
    const res = await fetchJSON(`${API}/projects/${id}/pull`, { method: 'POST' });
    const list = (res.playbooks || []).length
      ? '<ul class="playbook-list">' + (res.playbooks || []).map(pb => '<li><code>' + escapeHtml(pb) + '</code></li>').join('') + '</ul>'
      : '<p class="empty-state">No supported files found. We look for: .yml, .yaml, .sh, .bash, .ps1, .bat, .cmd, .tf, .hcl, .py, .rb and similar (case-insensitive).</p>';
    showModal(
      'Pull from Git',
      `<p>${escapeHtml(res.message || 'Pulled successfully.')}</p><p><strong>Files found (use in Job Templates):</strong></p><p class="text-muted" style="font-size:0.85rem;margin-top:0.25rem;">.yml/.yaml = Ansible playbooks (run with inventory). .sh, .ps1, .py, etc. = scripts (run directly).</p>${list}`,
      '<button class="btn btn-primary" onclick="closeModal(); reloadAndRender();">Close</button>'
    );
  } catch (e) {
    showError(e);
  }
}

async function launchJob(templateId) {
  try {
    const job = await fetchJSON(`${API}/jobs/launch`, { method: 'POST', body: JSON.stringify({ job_template_id: templateId, extra_vars_override: '' }) });
    viewJob(job.id);
    reloadAndRender();
  } catch (e) { showError(e); }
}

async function deleteJob(id) {
  if (!confirm('Delete this job from history?')) return;
  try {
    await fetchJSON(`${API}/jobs/${id}`, { method: 'DELETE' });
    await reloadAndRender();
  } catch (e) { showError(e); }
}

async function deleteJobHistory() {
  if (!jobs.length) return;
  if (!confirm('Delete all jobs from history?')) return;
  try {
    await Promise.all(jobs.map(j => fetchJSON(`${API}/jobs/${j.id}`, { method: 'DELETE' })).reverse());
    await reloadAndRender();
  } catch (e) { showError(e); }
}
function jobModalBody(job) {
  return `
    <p><strong>Playbook:</strong> ${escapeHtml(job.playbook_path)}</p>
    <p><strong>Status:</strong> <span class="badge badge-${job.status}">${job.status}</span></p>
    <p><strong>Started:</strong> ${job.started_at ? new Date(job.started_at).toLocaleString() : '—'}</p>
    <p><strong>Finished:</strong> ${job.finished_at ? new Date(job.finished_at).toLocaleString() : '—'}</p>
    <div class="form-group">
      <label>Output</label>
      <pre class="log-output">${escapeHtml(job.output_log || '(no output yet)')}</pre>
    </div>
  `;
}

function viewJob(id) {
  if (jobPollIntervalId) {
    clearInterval(jobPollIntervalId);
    jobPollIntervalId = null;
  }
  fetchJSON(`${API}/jobs/${id}`).then(job => {
    const modal = qs('#modal');
    modal.innerHTML = `
      <div class="modal-header">Job #${job.id} — ${job.status}</div>
      <div class="modal-body" id="job-modal-body">${jobModalBody(job)}</div>
      <div class="modal-footer"><button class="btn btn-primary" data-action="close-modal">Close</button></div>
    `;
    qs('#modal-overlay').classList.remove('hidden');

    const poll = () => {
      fetchJSON(`${API}/jobs/${id}`).then(j => {
        const header = modal.querySelector('.modal-header');
        const body = modal.querySelector('#job-modal-body');
        if (header) header.textContent = `Job #${j.id} — ${j.status}`;
        if (body) body.innerHTML = jobModalBody(j);
        if (j.status === 'success' || j.status === 'failed') {
          if (jobPollIntervalId) {
            clearInterval(jobPollIntervalId);
            jobPollIntervalId = null;
          }
          reloadAndRender();
        }
      }).catch(() => {});
    };

    if (job.status === 'pending' || job.status === 'running') {
      jobPollIntervalId = setInterval(poll, 1500);
    }
  }).catch(e => showError(e));
}

async function loadAll() {
  try {
    projects = await fetchJSON(`${API}/projects`);
    inventories = [];
    credentials = [];
    jobTemplates = [];
    for (const p of projects) {
      const [invList, credList, tplList] = await Promise.all([
        fetchJSON(`${API}/inventories?project_id=${p.id}`),
        fetchJSON(`${API}/credentials?project_id=${p.id}`),
        fetchJSON(`${API}/job_templates?project_id=${p.id}`),
      ]);
      inventories.push(...invList);
      credentials.push(...credList);
      jobTemplates.push(...tplList);
    }
    jobs = await fetchJSON(`${API}/jobs?limit=100`);
  } catch (e) {
    console.error(e);
    // Keep existing data so one failed poll doesn't wipe the UI
  }
}

async function reloadAndRender() {
  await loadAll();
  render();
}

// Init: nav + load data + render + auto-refresh
qsAll('.sidebar-nav a').forEach(a => {
  a.onclick = (e) => { e.preventDefault(); setPage(a.dataset.page); };
});
reloadAndRender().finally(() => {
  startRefresh();
});

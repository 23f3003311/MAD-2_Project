

const PPA = {
  
  getToken: () => localStorage.getItem('ppa_token'),
  getRole: () => localStorage.getItem('ppa_role'),
  getName: () => localStorage.getItem('ppa_name'),
  getEmail: () => localStorage.getItem('ppa_email'),
  getUserId: () => localStorage.getItem('ppa_user_id'),
  getProfileId: () => localStorage.getItem('ppa_profile_id'),

  logout() {
    ['ppa_token','ppa_role','ppa_name','ppa_email','ppa_user_id','ppa_profile_id']
      .forEach(k => localStorage.removeItem(k));
    window.location.href = '/login';
  },

  requireRole(expectedRole) {
    const token = this.getToken();
    const role = this.getRole();
    if (!token || !role) { window.location.href = '/login'; return false; }
    if (role !== expectedRole) { window.location.href = '/login'; return false; }
    return true;
  },

  
  async request(method, url, body = null, isFormData = false) {
    const token = this.getToken();
    const headers = { 'Authorization': `Bearer ${token}` };
    if (!isFormData) headers['Content-Type'] = 'application/json';
    const opts = { method, headers };
    if (body) opts.body = isFormData ? body : JSON.stringify(body);
    const res = await fetch(url, opts);
    if (res.status === 401) { this.logout(); return null; }
    return res.json();
  },

  get: (url) => PPA.request('GET', url),
  post: (url, body) => PPA.request('POST', url, body),
  put: (url, body) => PPA.request('PUT', url, body),
  del: (url) => PPA.request('DELETE', url),
  upload: (url, formData) => PPA.request('POST', url, formData, true),

  
  formatDate(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('en-IN', { day:'2-digit', month:'short', year:'numeric' });
  },
  formatDateTime(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('en-IN', { dateStyle:'medium', timeStyle:'short' });
  },
  daysLeft(isoDate) {
    if (!isoDate) return null;
    const diff = new Date(isoDate) - new Date();
    return Math.ceil(diff / (1000*60*60*24));
  },

  
  statusBadge(status) {
    const map = {
      pending: 'badge bg-warning text-dark',
      approved: 'badge bg-success',
      rejected: 'badge bg-danger',
      closed: 'badge bg-secondary',
      applied: 'badge bg-primary',
      shortlisted: 'badge bg-info text-dark',
      selected: 'badge bg-success',
      active: 'badge bg-success',
      blacklisted: 'badge bg-danger',
    };
    return map[status] || 'badge bg-secondary';
  },

  toast(msg, type = 'success') {
    const id = 'toast-' + Date.now();
    const colors = { success: '#3fb950', danger: '#f85149', warning: '#d29922', info: '#58a6ff' };
    const icons = { success: 'bi-check-circle-fill', danger: 'bi-exclamation-triangle-fill',
                    warning: 'bi-exclamation-circle-fill', info: 'bi-info-circle-fill' };
    const el = document.createElement('div');
    el.id = id;
    el.style.cssText = `position:fixed;top:20px;right:20px;z-index:9999;
      background:#161b22;border:1px solid #30363d;border-left:3px solid ${colors[type]};
      border-radius:8px;padding:14px 18px;color:#e6edf3;font-size:14px;
      box-shadow:0 8px 24px rgba(0,0,0,.4);display:flex;gap:10px;align-items:center;
      max-width:360px;animation:slideIn .3s ease;font-family:'Inter',sans-serif;`;
    el.innerHTML = `<i class="bi ${icons[type]}" style="color:${colors[type]};font-size:16px;"></i><span>${msg}</span>`;
    document.body.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .3s';
                       setTimeout(() => el.remove(), 300); }, 3500);
  },
};


if (!document.getElementById('ppa-toast-style')) {
  const s = document.createElement('style');
  s.id = 'ppa-toast-style';
  s.textContent = '@keyframes slideIn { from{transform:translateX(120%);opacity:0} to{transform:translateX(0);opacity:1} }';
  document.head.appendChild(s);
}

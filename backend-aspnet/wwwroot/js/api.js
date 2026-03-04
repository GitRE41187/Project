const api = {
  getToken: () => localStorage.getItem('token'),
  setToken: (token) => { if (token) localStorage.setItem('token', token); else localStorage.removeItem('token'); },
  headers: (includeAuth = true) => {
    const h = { 'Content-Type': 'application/json' };
    const t = api.getToken();
    if (includeAuth && t) h['Authorization'] = `Bearer ${t}`;
    return h;
  },
  async request(url, options = {}) {
    const res = await fetch(`${CONFIG.API_BASE}${url}`, {
      ...options,
      headers: { ...api.headers(!options.skipAuth), ...options.headers }
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw { status: res.status, ...data };
    return data;
  },
  get: (url) => api.request(url, { method: 'GET' }),
  post: (url, body) => api.request(url, { method: 'POST', body: JSON.stringify(body) }),
  put: (url, body) => api.request(url, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (url) => api.request(url, { method: 'DELETE' }),
  async postForm(url, formData) {
    const t = api.getToken();
    const h = {};
    if (t) h['Authorization'] = `Bearer ${t}`;
    const res = await fetch(`${CONFIG.API_BASE}${url}`, { method: 'POST', headers: h, body: formData });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw { status: res.status, ...data };
    return data;
  }
};

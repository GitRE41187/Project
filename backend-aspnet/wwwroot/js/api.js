const api = {
  getToken: () => localStorage.getItem('token'),
  setToken: (token) => {
    if (token) localStorage.setItem('token', token);
    else localStorage.removeItem('token');
  },
  headers: (includeAuth = true) => {
    const h = { 'Content-Type': 'application/json' };
    const t = api.getToken();
    if (includeAuth && t) h['Authorization'] = `Bearer ${t}`;
    return h;
  },
  async parseJsonBody(res) {
    const ct = (res.headers.get('content-type') || '').toLowerCase();
    if (ct.includes('application/json')) {
      try {
        const t = await res.text();
        return t ? JSON.parse(t) : {};
      } catch (_) {
        return {};
      }
    }
    const text = await res.text();
    if (!text) return {};
    try {
      return JSON.parse(text);
    } catch (_) {
      if (!res.ok) return { error: text.trim().slice(0, 500) || res.statusText || 'Request failed' };
      return {};
    }
  },
  async request(url, options = {}) {
    const method = options.method || 'GET';
    console.info('[API] request', { method, url });
    const res = await fetch(`${CONFIG.API_BASE}${url}`, {
      ...options,
      headers: { ...api.headers(!options.skipAuth), ...options.headers }
    });
    const data = await api.parseJsonBody(res);
    if (!res.ok) {
      console.error('[API] failed', { method, url, status: res.status, data });
      throw { status: res.status, ...data };
    }
    console.info('[API] success', { method, url, status: res.status });
    return data;
  },
  get: (url) => api.request(url, { method: 'GET' }),
  post: (url, body) => api.request(url, { method: 'POST', body: JSON.stringify(body) }),
  put: (url, body) => api.request(url, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (url) => api.request(url, { method: 'DELETE' }),
  async postForm(url, formData) {
    console.info('[API] request', { method: 'POST_FORM', url });
    const t = api.getToken();
    const h = {};
    if (t) h['Authorization'] = `Bearer ${t}`;
    const res = await fetch(`${CONFIG.API_BASE}${url}`, { method: 'POST', headers: h, body: formData });
    const ct = res.headers.get('content-type') || '';
    let data = {};
    if (ct.includes('application/json')) {
      try {
        data = await res.json();
      } catch (_) {
        data = {};
      }
    } else {
      const text = await res.text();
      if (res.ok) {
        try {
          data = text ? JSON.parse(text) : {};
        } catch (_) {
          data = text ? { message: text } : {};
        }
      } else {
        data = { error: text?.trim() ? text.slice(0, 500) : res.statusText || 'Request failed' };
      }
    }
    if (!res.ok) {
      console.error('[API] failed', { method: 'POST_FORM', url, status: res.status, data });
      throw { status: res.status, ...data };
    }
    console.info('[API] success', { method: 'POST_FORM', url, status: res.status });
    return data;
  }
};

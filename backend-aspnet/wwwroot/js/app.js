/** Main app - init, routing, user state */
let user = null;
let currentPage = 'dashboard';

async function fetchUser() {
  try {
    const res = await api.get('/api/auth/me');
    user = res.user;
    return true;
  } catch {
    api.setToken(null);
    user = null;
    return false;
  }
}

let pageCleanup = null;

function renderPage(page) {
  const container = document.getElementById('page-content');
  if (pageCleanup) {
    try {
      const ret = pageCleanup();
      if (ret && typeof ret.then === 'function') ret.catch(() => {});
    } catch (_) {
      /* ignore */
    }
    pageCleanup = null;
  }
  container.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>';
  const done = (p) => {
    Promise.resolve(p).then((fn) => {
      if (typeof fn === 'function') pageCleanup = fn;
    });
  };
  if (page === 'dashboard') done(renderDashboard(container));
  else if (page === 'queue') renderQueue(container);
  else if (page === 'control') done(renderControl(container));
  else if (page === 'admin') renderAdmin(container);
}

function navigate(page) {
  currentPage = page;
  renderSidebar();
  document.querySelectorAll('.nav-item[data-page]').forEach(el => el.classList.toggle('active', el.dataset.page === page));
  renderPage(page);
}

async function initApp() {
  document.getElementById('loading').classList.add('d-none');
  const token = api.getToken();
  if (!token) {
    await RobotRealtime.stop();
    renderAuthPage('login');
    return;
  }
  const ok = await fetchUser();
  if (!ok) {
    await RobotRealtime.stop();
    renderAuthPage('login');
    return;
  }
  document.getElementById('auth-pages').classList.add('d-none');
  document.getElementById('app-layout').classList.remove('d-none');
  renderSidebar();
  await RobotRealtime.start();
  renderPage(currentPage);
}

document.addEventListener('DOMContentLoaded', () => {
  const hash = window.location.hash.slice(1) || 'dashboard';
  if (['dashboard','queue','control','admin'].includes(hash)) currentPage = hash;
  initApp();
});

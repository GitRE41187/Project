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
/** ป้องกัน async page render ที่ยังค้างหลังสลับเมนูไปแล้ว (จะทับ innerHTML ของหน้าอื่น) */
let viewGeneration = 0;

/** ยกเลิก subscription/interval ของหน้าและทำให้ isCurrentView() ของรอบก่อนเป็น false (logout / สลับเมนู) */
function invalidateSpaView() {
  if (pageCleanup) {
    try {
      const ret = pageCleanup();
      if (ret && typeof ret.then === 'function') ret.catch(() => {});
    } catch (_) {
      /* ignore */
    }
    pageCleanup = null;
  }
  viewGeneration++;
}

function renderPage(page) {
  const container = document.getElementById('page-content');
  invalidateSpaView();
  const genAtStart = viewGeneration;
  const isCurrentView = () => genAtStart === viewGeneration;
  container.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>';
  const done = (p) => {
    Promise.resolve(p).then((fn) => {
      if (typeof fn !== 'function' || genAtStart !== viewGeneration) return;
      pageCleanup = fn;
    });
  };
  if (page === 'dashboard') done(renderDashboard(container, isCurrentView));
  else if (page === 'queue') renderQueue(container, isCurrentView);
  else if (page === 'control') done(renderControl(container, isCurrentView));
  else if (page === 'admin') renderAdmin(container, isCurrentView);
}

function navigate(page) {
  currentPage = page;
  if (['dashboard', 'queue', 'control', 'admin'].includes(page)) {
    window.location.hash = page;
  }
  renderSidebar();
  document.querySelectorAll('.nav-item[data-page]').forEach((el) => el.classList.toggle('active', el.dataset.page === page));
  renderPage(page);
}

async function initApp() {
  document.getElementById('loading').classList.add('d-none');
  const token = api.getToken();
  if (!token) {
    await RobotRealtime.stop();
    invalidateSpaView();
    renderAuthPage('login');
    return;
  }
  const ok = await fetchUser();
  if (!ok) {
    await RobotRealtime.stop();
    invalidateSpaView();
    renderAuthPage('login');
    return;
  }
  document.getElementById('auth-pages').classList.add('d-none');
  document.getElementById('app-layout').classList.remove('d-none');
  renderSidebar();
  await RobotRealtime.start();
  const h = window.location.hash.slice(1);
  if (!['dashboard', 'queue', 'control', 'admin'].includes(h)) {
    window.history.replaceState(null, '', `#${currentPage}`);
  }
  renderPage(currentPage);
}

document.addEventListener('DOMContentLoaded', () => {
  const hash = window.location.hash.slice(1) || 'dashboard';
  if (['dashboard', 'queue', 'control', 'admin'].includes(hash)) currentPage = hash;
  initApp();
});

window.addEventListener('hashchange', () => {
  const hash = window.location.hash.slice(1);
  if (!api.getToken() || !user) return;
  if (!['dashboard', 'queue', 'control', 'admin'].includes(hash) || hash === currentPage) return;
  currentPage = hash;
  renderSidebar();
  document.querySelectorAll('.nav-item[data-page]').forEach((el) => el.classList.toggle('active', el.dataset.page === hash));
  renderPage(hash);
  const sidebar = document.getElementById('sidebar');
  if (sidebar?.classList.contains('open')) closeSidebar();
});

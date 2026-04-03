/** Sidebar: nav, toggle, logout */
function renderSidebar() {
  document.getElementById('sidebar-username').textContent = user?.username || 'User';
  document.getElementById('sidebar-email').textContent = user?.email || '';
  const adminNav = document.getElementById('nav-admin');
  if (user?.role === 'admin') adminNav.classList.remove('d-none');
  else adminNav.classList.add('d-none');
  document.querySelectorAll('.nav-item[data-page]').forEach(el => {
    el.classList.toggle('active', el.dataset.page === currentPage);
    el.onclick = () => { navigate(el.dataset.page); closeSidebar(); };
  });
  document.getElementById('btn-logout').onclick = () => {
    api.setToken(null);
    user = null;
    invalidateSpaView();
    initApp();
  };
  initSidebarToggle();
}

function openSidebar() {
  document.getElementById('sidebar').classList.add('open');
  document.getElementById('sidebar-overlay').classList.add('show');
  document.body.style.overflow = 'hidden';
}
function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebar-overlay').classList.remove('show');
  document.body.style.overflow = '';
}
function initSidebarToggle() {
  const toggle = document.getElementById('sidebar-toggle');
  const overlay = document.getElementById('sidebar-overlay');
  if (!toggle || !overlay) return;
  toggle.onclick = () => openSidebar();
  overlay.onclick = () => closeSidebar();
}

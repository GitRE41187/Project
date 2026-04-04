/** โหมดสว่าง/มืด — เก็บใน localStorage, sync กับ data-theme / data-bs-theme */
(function () {
  const STORAGE_KEY = 'fc-theme';

  function normalize(t) {
    return t === 'light' || t === 'dark' ? t : 'dark';
  }

  function readStored() {
    return normalize(localStorage.getItem(STORAGE_KEY));
  }

  function syncToggleButtons(theme) {
    const isDark = theme === 'dark';
    document.querySelectorAll('[data-theme-toggle]').forEach((btn) => {
      btn.setAttribute('aria-label', isDark ? 'สลับเป็นโหมดสว่าง' : 'สลับเป็นโหมดมืด');
      btn.setAttribute('title', isDark ? 'โหมดสว่าง' : 'โหมดมืด');
      btn.innerHTML = isDark
        ? '<i class="bi bi-sun-fill" aria-hidden="true"></i>'
        : '<i class="bi bi-moon-stars-fill" aria-hidden="true"></i>';
    });
  }

  function apply(theme) {
    const t = normalize(theme);
    document.documentElement.setAttribute('data-theme', t);
    document.documentElement.setAttribute('data-bs-theme', t);
    localStorage.setItem(STORAGE_KEY, t);
    syncToggleButtons(t);
  }

  function getTheme() {
    return normalize(document.documentElement.getAttribute('data-theme'));
  }

  function toggle() {
    apply(getTheme() === 'dark' ? 'light' : 'dark');
  }

  document.addEventListener('click', (e) => {
    if (e.target.closest('[data-theme-toggle]')) {
      e.preventDefault();
      toggle();
    }
  });

  window.FieldControlTheme = { apply, getTheme, toggle };

  document.addEventListener('DOMContentLoaded', () => {
    syncToggleButtons(readStored());
  });
})();

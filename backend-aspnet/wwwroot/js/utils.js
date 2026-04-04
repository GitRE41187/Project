/** Toast notifications */
function showToast(message, type = 'success') {
  const c = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast show align-items-center text-bg-${type} border-0`;
  el.setAttribute('role', 'alert');
  el.innerHTML = `<div class="d-flex"><div class="toast-body">${message}</div><button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="ปิด"></button></div>`;
  c.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

/** Load HTML template from /templates/ */
async function loadTemplate(name) {
  const res = await fetch(`/templates/${name}.html`);
  if (!res.ok) throw new Error(`Template ${name} not found`);
  return res.text();
}

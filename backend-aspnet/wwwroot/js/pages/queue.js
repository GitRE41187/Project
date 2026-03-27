/** Queue page */
async function renderQueue(container) {
  const formatLocalDateTimeInput = (date) => {
    const pad = (n) => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  };

  const html = await loadTemplate('queue');
  container.innerHTML = html;

  const load = async () => {
    try {
      const res = await api.get('/api/queue/my-bookings');
      const list = document.getElementById('bookings-list');
      const bookings = res.bookings || [];
      list.innerHTML = bookings.length ? bookings.map(b => `
        <div class="card-custom">
          <div class="d-flex justify-content-between align-items-center">
            <div>
              <strong>${b.field_name || 'Main Field'}</strong><br>
              <small>${new Date(b.start_time).toLocaleString()} - ${new Date(b.end_time).toLocaleString()}</small>
            </div>
            <span class="badge bg-${b.status === 'active' ? 'success' : b.status === 'pending' ? 'warning' : 'secondary'}">${b.status === 'active' ? 'ใช้งาน' : b.status === 'pending' ? 'รอดำเนินการ' : b.status}</span>
            ${b.status === 'pending' ? `<button class="btn btn-outline-danger btn-sm" data-id="${b.id}">ยกเลิก</button>` : ''}
          </div>
        </div>
      `).join('') : '<div class="card-custom text-center py-5"><p class="text-muted">ยังไม่มีการจอง</p><button class="btn btn-primary" id="btn-book-empty"><i class="bi bi-plus-lg me-1"></i> จองคิว</button></div>';
      list.querySelectorAll('[data-id]').forEach(btn => {
        btn.onclick = async () => {
          if (!confirm('ยกเลิกการจองนี้?')) return;
          try {
            await api.delete(`/api/queue/cancel/${btn.dataset.id}`);
            showToast('ยกเลิกแล้ว');
            load();
          } catch (e) { showToast(e.error || 'Failed', 'danger'); }
        };
      });
      const e = document.getElementById('btn-book-empty');
      if (e) e.onclick = () => document.getElementById('btn-book').click();
    } catch (e) {
      document.getElementById('bookings-list').innerHTML = `<div class="card-custom"><p class="text-danger">${e.error || 'Failed to load'}</p></div>`;
    }
  };
  await load();

  document.getElementById('btn-book').onclick = async () => {
    const modalHtml = await loadTemplate('queue-book-modal');
    const modal = document.getElementById('modal-container');
    modal.innerHTML = modalHtml;
    const now = new Date();
    const min = formatLocalDateTimeInput(now);
    modal.querySelector('[name="startTime"]').min = min;
    modal.querySelector('[name="endTime"]').min = min;
    modal.querySelector('[data-dismiss]').onclick = () => modal.innerHTML = '';
    modal.querySelector('#book-form').onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const startTime = fd.get('startTime');
      const endTime = fd.get('endTime');
      try {
        await api.post('/api/queue/book', { startTime, endTime });
        showToast('จองสำเร็จ');
        modal.innerHTML = '';
        load();
      } catch (err) { showToast(err.error || 'Failed', 'danger'); }
    };
  };
}

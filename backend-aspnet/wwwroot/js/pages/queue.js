/** Queue page */
async function renderQueue(container, isCurrentView) {
  const formatLocalDateTimeInput = (date) => {
    const pad = (n) => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  };

  const html = await loadTemplate('queue');
  if (!isCurrentView()) return;
  container.innerHTML = html;

  const load = async () => {
    try {
      const res = await api.get('/api/queue/my-bookings');
      if (!isCurrentView()) return;
      const list = document.getElementById('bookings-list');
      if (!list) return;
      const bookings = res.bookings || [];
      list.innerHTML = bookings.length ? bookings.map(b => `
        <div class="card-custom">
          <div class="d-flex justify-content-between align-items-center flex-wrap gap-3">
            <div>
              <strong>${b.field_name || 'Main Field'}</strong>
              <div class="queue-card-meta">${new Date(b.start_time).toLocaleString()} — ${new Date(b.end_time).toLocaleString()}</div>
            </div>
            <div class="d-flex align-items-center gap-2 flex-wrap">
              <span class="badge bg-${b.status === 'active' ? 'success' : b.status === 'pending' ? 'warning' : 'secondary'}">${b.status === 'active' ? 'ใช้งาน' : b.status === 'pending' ? 'รอดำเนินการ' : b.status}</span>
              ${b.status === 'pending' ? `<button type="button" class="btn btn-outline-danger btn-sm" data-id="${b.id}">ยกเลิก</button>` : ''}
            </div>
          </div>
        </div>
      `).join('') : '<div class="card-custom empty-state"><p class="text-muted mb-0">ยังไม่มีการจอง</p><button type="button" class="btn btn-primary mt-3 btn-icon-pad" id="btn-book-empty"><i class="bi bi-plus-lg me-1"></i> จองคิว</button></div>';
      list.querySelectorAll('[data-id]').forEach(btn => {
        btn.onclick = async () => {
          if (!confirm('ยกเลิกการจองนี้?')) return;
          try {
            await api.delete(`/api/queue/cancel/${btn.dataset.id}`);
            if (!isCurrentView()) return;
            showToast('ยกเลิกแล้ว');
            load();
          } catch (e) {
            if (!isCurrentView()) return;
            showToast(e.error || 'Failed', 'danger');
          }
        };
      });
      const e = document.getElementById('btn-book-empty');
      if (e) e.onclick = () => document.getElementById('btn-book').click();
    } catch (e) {
      if (!isCurrentView()) return;
      const bl = document.getElementById('bookings-list');
      if (bl) bl.innerHTML = `<div class="card-custom"><p class="text-danger">${e.error || 'Failed to load'}</p></div>`;
    }
  };
  await load();
  if (!isCurrentView()) return;

  document.getElementById('btn-book').onclick = async () => {
    const modalHtml = await loadTemplate('queue-book-modal');
    if (!isCurrentView()) return;
    const modal = document.getElementById('modal-container');
    if (!modal) return;
    modal.innerHTML = modalHtml;
    const now = new Date();
    const startInput = modal.querySelector('[name="startTime"]');
    const endInput = modal.querySelector('[name="endTime"]');
    const preview = modal.querySelector('#slot-preview');
    const dismissBtn = modal.querySelector('[data-dismiss]');
    const bookForm = modal.querySelector('#book-form');
    if (!startInput || !endInput || !preview || !dismissBtn || !bookForm) {
      showToast('ไม่สามารถเปิดฟอร์มจองได้', 'danger');
      return;
    }
    const minStart = new Date(now.getTime() + 5 * 60 * 1000);
    startInput.min = formatLocalDateTimeInput(minStart);
    startInput.value = formatLocalDateTimeInput(minStart);

    const updatePreview = () => {
      if (!startInput.value || !endInput.value) {
        preview.textContent = 'เลือกระยะเวลาได้อิสระ แต่รวมกันต้องไม่เกิน 1 ชั่วโมง';
        return;
      }
      const start = new Date(startInput.value);
      const end = new Date(endInput.value);
      if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
        preview.textContent = 'รูปแบบเวลาไม่ถูกต้อง';
        return;
      }
      const diffMinutes = Math.round((end - start) / 60000);
      preview.textContent = `ช่วงที่เลือก: ${startInput.value.replace('T', ' ')} - ${endInput.value.replace('T', ' ')} (${diffMinutes} นาที)`;
    };

    const syncEndBounds = () => {
      if (!startInput.value) return;
      const start = new Date(startInput.value);
      if (Number.isNaN(start.getTime())) return;
      const maxEnd = new Date(start.getTime() + 60 * 60 * 1000);
      endInput.min = formatLocalDateTimeInput(start);
      endInput.max = formatLocalDateTimeInput(maxEnd);
      if (!endInput.value || new Date(endInput.value) < start || new Date(endInput.value) > maxEnd) {
        endInput.value = formatLocalDateTimeInput(maxEnd);
      }
      updatePreview();
    };

    startInput.onchange = syncEndBounds;
    endInput.onchange = updatePreview;
    syncEndBounds();

    dismissBtn.onclick = () => {
      if (isCurrentView()) modal.innerHTML = '';
    };
    bookForm.onsubmit = async (e) => {
      e.preventDefault();
      if (!isCurrentView()) return;
      if (!startInput.value || !endInput.value) {
        showToast('กรุณาเลือกเวลาเริ่มและเวลาสิ้นสุด', 'danger');
        return;
      }
      const startDate = new Date(startInput.value);
      const endDate = new Date(endInput.value);
      const diffMs = endDate - startDate;
      if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) {
        showToast('รูปแบบเวลาไม่ถูกต้อง', 'danger');
        return;
      }
      if (startDate <= now) {
        showToast('ไม่สามารถจองเวลาในอดีตได้', 'danger');
        return;
      }
      if (diffMs <= 0) {
        showToast('เวลาสิ้นสุดต้องมากกว่าเวลาเริ่ม', 'danger');
        return;
      }
      if (diffMs > 60 * 60 * 1000) {
        showToast('จองได้ไม่เกิน 1 ชั่วโมง', 'danger');
        return;
      }
      const startTime = formatLocalDateTimeInput(startDate);
      const endTime = formatLocalDateTimeInput(endDate);
      try {
        await api.post('/api/queue/book', { startTime, endTime });
        if (!isCurrentView()) return;
        showToast('จองสำเร็จ');
        modal.innerHTML = '';
        load();
      } catch (err) {
        if (!isCurrentView()) return;
        showToast(err.error || 'Failed', 'danger');
      }
    };
  };
}

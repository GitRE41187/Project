/** Queue page */
async function renderQueue(container, isCurrentView) {
  const formatLocalDateTimeInput = (date) => {
    const pad = (n) => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  };

  const fmtDate = (str) => {
    const d = new Date(str);
    return d.toLocaleString('th-TH', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };
  const fmtDuration = (start, end) => {
    const m = Math.round((new Date(end) - new Date(start)) / 60000);
    if (m < 60) return `${m} นาที`;
    const h = Math.floor(m / 60);
    return m % 60 ? `${h} ชม. ${m % 60} นาที` : `${h} ชม.`;
  };

  const html = await loadTemplate('queue');
  if (!isCurrentView()) return;
  container.innerHTML = html;

  let queueCountdownInterval = null;

  const startCountdowns = (list) => {
    clearInterval(queueCountdownInterval);
    const updateAll = () => {
      if (!isCurrentView()) { clearInterval(queueCountdownInterval); return; }
      list.querySelectorAll('.booking-countdown[data-end]').forEach(el => {
        const ms = new Date(el.dataset.end) - new Date();
        if (ms <= 0) { el.textContent = 'หมดเวลา'; return; }
        const m = Math.floor(ms / 60000);
        const s = Math.floor((ms % 60000) / 1000);
        el.textContent = `${m}:${String(s).padStart(2, '0')} นาที`;
      });
      list.querySelectorAll('.booking-start-in[data-start]').forEach(el => {
        const ms = new Date(el.dataset.start) - new Date();
        if (ms <= 0) { el.textContent = 'กำลังเริ่ม...'; return; }
        const m = Math.floor(ms / 60000);
        if (m >= 60) {
          const h = Math.floor(m / 60);
          el.textContent = `ประมาณ ${h} ชม. ${m % 60 ? `${m % 60} นาที` : ''}`;
        } else {
          el.textContent = `${m} นาที`;
        }
      });
    };
    updateAll();
    queueCountdownInterval = setInterval(updateAll, 1000);
  };

  const load = async () => {
    try {
      const res = await api.get('/api/queue/my-bookings');
      if (!isCurrentView()) return;
      const list = document.getElementById('bookings-list');
      if (!list) return;
      const bookings = res.bookings || [];
      list.innerHTML = bookings.length ? bookings.map(b => {
        const statusMap = { active: ['success', 'play-fill', 'ใช้งาน'], pending: ['warning', 'clock', 'รอดำเนินการ'] };
        const [sc, ic, sl] = statusMap[b.status] || ['secondary', 'x-circle', b.status];
        return `
        <div class="card-custom booking-card-${b.status}">
          <div class="d-flex justify-content-between align-items-start flex-wrap gap-3">
            <div class="flex-grow-1">
              <div class="d-flex align-items-center gap-2 mb-2 flex-wrap">
                <span class="badge bg-${sc}"><i class="bi bi-${ic} me-1"></i>${sl}</span>
                <strong>${b.field_name || 'Main Field'}</strong>
              </div>
              <div class="queue-card-meta">
                <i class="bi bi-clock me-1"></i>${fmtDate(b.start_time)} &mdash; ${fmtDate(b.end_time)}
                <span class="ms-2 badge bg-secondary bg-opacity-50 fw-normal">${fmtDuration(b.start_time, b.end_time)}</span>
              </div>
              ${b.status === 'active' ? `
              <div class="mt-2 d-flex align-items-center gap-1 text-success small fw-semibold">
                <i class="bi bi-hourglass-split"></i>
                เหลือเวลา: <span class="booking-countdown ms-1" data-end="${b.end_time}">—</span>
              </div>` : ''}
              ${b.status === 'pending' ? `
              <div class="mt-2 booking-start-in-wrap d-flex align-items-center gap-1 small">
                <i class="bi bi-calendar-event text-muted"></i>
                <span class="text-muted">เริ่มใน </span><span class="booking-start-in fw-semibold" data-start="${b.start_time}">—</span>
              </div>` : ''}
            </div>
            <div class="d-flex align-items-center gap-2 flex-wrap flex-shrink-0">
              ${b.status === 'pending' ? `<button type="button" class="btn btn-outline-danger btn-sm" data-id="${b.id}"><i class="bi bi-x-circle me-1"></i>ยกเลิก</button>` : ''}
            </div>
          </div>
        </div>`;
      }).join('') : `<div class="card-custom empty-state">
        <i class="bi bi-calendar-x d-block mb-3" style="font-size:2.5rem;opacity:0.35"></i>
        <p class="text-muted mb-0">ยังไม่มีการจอง</p>
        <button type="button" class="btn btn-primary mt-3 btn-icon-pad" id="btn-book-empty">
          <i class="bi bi-plus-lg me-1"></i> จองคิวเลย
        </button>
      </div>`;

      startCountdowns(list);

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

    // Quick-duration chips
    modal.querySelectorAll('.duration-chip[data-mins]').forEach(chip => {
      chip.onclick = () => {
        if (!startInput.value) return;
        const start = new Date(startInput.value);
        if (Number.isNaN(start.getTime())) return;
        const mins = parseInt(chip.dataset.mins, 10);
        endInput.value = formatLocalDateTimeInput(new Date(start.getTime() + mins * 60000));
        syncEndBounds();
        modal.querySelectorAll('.duration-chip').forEach(c => {
          c.className = 'btn btn-sm btn-outline-secondary duration-chip';
        });
        chip.className = 'btn btn-sm btn-primary duration-chip';
      };
    });

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

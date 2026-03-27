/** Queue page */
async function renderQueue(container) {
  const formatLocalDateTimeInput = (date) => {
    const pad = (n) => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  };
  const formatDateInput = (date) => formatLocalDateTimeInput(date).slice(0, 10);
  const formatHour = (hour) => `${String(hour).padStart(2, '0')}:00`;

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
    const dateInput = modal.querySelector('[name="bookingDate"]');
    const slotInput = modal.querySelector('[name="hourSlot"]');
    const slotGrid = modal.querySelector('#hour-slot-grid');
    const preview = modal.querySelector('#slot-preview');
    const todayDateStr = formatDateInput(now);
    dateInput.min = todayDateStr;
    dateInput.value = todayDateStr;

    const populateSlots = () => {
      const selectedDate = dateInput.value;
      if (!selectedDate) return;
      const isToday = selectedDate === formatDateInput(new Date());
      const currentHour = new Date().getHours();
      const startHour = isToday ? currentHour + 1 : 0;
      const buttons = [];
      slotInput.value = '';
      for (let h = startHour; h <= 23; h += 1) {
        buttons.push(`<button type="button" class="btn btn-outline-light btn-sm slot-btn" data-hour="${h}">${formatHour(h)} - ${formatHour((h + 1) % 24)}</button>`);
      }
      slotGrid.innerHTML = buttons.join('');
      slotGrid.querySelectorAll('.slot-btn').forEach((btn) => {
        btn.onclick = () => {
          slotGrid.querySelectorAll('.slot-btn').forEach((x) => x.classList.replace('btn-primary', 'btn-outline-light'));
          btn.classList.replace('btn-outline-light', 'btn-primary');
          slotInput.value = btn.dataset.hour;
          const startHourValue = Number(btn.dataset.hour);
          const startText = `${dateInput.value} ${formatHour(startHourValue)}`;
          const endDate = new Date(`${dateInput.value}T00:00`);
          endDate.setHours(startHourValue + 1, 0, 0, 0);
          preview.textContent = `ช่วงที่เลือก: ${startText} - ${formatLocalDateTimeInput(endDate).replace('T', ' ')}`;
        };
      });
      if (!buttons.length)
        preview.textContent = 'วันนี้ไม่มีช่วงเวลาว่างแล้ว โปรดเลือกวันถัดไป';
      else
        preview.textContent = 'ระยะเวลาใช้งาน: 1 ชั่วโมงต่อการจอง';
    };

    dateInput.onchange = () => populateSlots();
    populateSlots();

    modal.querySelector('[data-dismiss]').onclick = () => modal.innerHTML = '';
    modal.querySelector('#book-form').onsubmit = async (e) => {
      e.preventDefault();
      if (!dateInput.value || !slotInput.value) {
        showToast('กรุณาเลือกวันและช่วงเวลา', 'danger');
        return;
      }
      const startHour = Number(slotInput.value);
      const startDate = new Date(`${dateInput.value}T00:00`);
      startDate.setHours(startHour, 0, 0, 0);
      const endDate = new Date(startDate);
      endDate.setHours(endDate.getHours() + 1);
      const startTime = formatLocalDateTimeInput(startDate);
      const endTime = formatLocalDateTimeInput(endDate);
      try {
        await api.post('/api/queue/book', { startTime, endTime });
        showToast('จองสำเร็จ');
        modal.innerHTML = '';
        load();
      } catch (err) { showToast(err.error || 'Failed', 'danger'); }
    };
  };
}

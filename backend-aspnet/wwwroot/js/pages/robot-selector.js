/** Thai labels for robot status from backend */
function robotStatusLabelTh(status) {
  if (status == null || status === '') return '—';
  const m = { available: 'พร้อมใช้', idle: 'รอคำสั่ง', in_use: 'กำลังใช้งาน', offline: 'ออฟไลน์' };
  return m[status] || status;
}

function formatRobotBattery(b) {
  if (b == null || b === '') return '';
  if (typeof b === 'object') {
    if (typeof b.percent === 'number') return `${b.percent}%`;
    if (typeof b.level === 'number') return `${b.level}%`;
    try {
      const s = JSON.stringify(b);
      return s.length > 80 ? s.slice(0, 77) + '…' : s;
    } catch (_) {
      return String(b);
    }
  }
  return String(b);
}

/** Robot selector component - shared by dashboard and control */
async function renderRobotSelector(container, onSelect, onRelease, isActive = () => true) {
  container.innerHTML = '<div class="card-custom"><div class="text-center py-4"><div class="spinner-border text-primary"></div><p class="mt-2">กำลังโหลดหุ่นยนต์...</p></div></div>';
  try {
    const [availRes, myRes] = await Promise.allSettled([
      api.get('/api/robots/available'),
      api.get('/api/robots/my-car')
    ]);
    if (!isActive()) return;

    const cars = availRes.status === 'fulfilled' ? availRes.value.availableCars || [] : [];
    const availError = availRes.status === 'rejected';
    const myCarRes = myRes.status === 'fulfilled' ? myRes.value : null;
    const myError = myRes.status === 'rejected';

    if (myError) {
      const msg = myRes.reason?.error || myRes.reason?.message || 'โหลดสถานะรถของคุณไม่สำเร็จ';
      container.innerHTML = `<div class="card-custom"><p class="text-danger">${msg}</p></div>`;
      return;
    }

    const sel = myCarRes?.hasSelectedCar ? myCarRes.selectedCar : null;
    const availWarn = availError
      ? '<p class="text-warning small mb-2"><i class="bi bi-exclamation-triangle"></i> โหลดรายการรถว่างไม่สำเร็จ — แสดงเฉพาะรถที่คุณเลือกไว้</p>'
      : '';

    let html = `
      <div class="card-custom">
        <div class="card-section-title mb-4"><i class="bi bi-robot" aria-hidden="true"></i><span>เลือกหุ่นยนต์</span></div>
        ${availWarn}
        ${sel ? `
        <div class="robot-card mb-4">
          <div class="d-flex justify-content-between align-items-center">
            <div>
              <span class="status-in-use me-2"></span><strong>${sel.name}</strong>
              <br><small class="text-muted">${sel.ip != null ? `${sel.ip}:${sel.port}` : ''}</small>
              <br><small class="text-muted">สถานะ: ${robotStatusLabelTh(sel.status)} · ${sel.isConnected ? 'เชื่อมต่อ' : 'ไม่เชื่อมต่อ'}</small>
              ${formatRobotBattery(sel.battery) ? `<br><small class="text-muted">แบตเตอรี่: ${formatRobotBattery(sel.battery)}</small>` : ''}
            </div>
            <button class="btn btn-danger btn-sm" id="btn-release">ยกเลิก</button>
          </div>
        </div>` : '<p class="text-warning mb-3"><i class="bi bi-exclamation-circle"></i> กรุณาเลือกหุ่นยนต์</p>'}
        <h6 class="text-muted mb-3">ใช้ได้ (${cars.length})</h6>
        ${cars.length ? cars.map(c => `
          <div class="robot-card d-flex justify-content-between align-items-center">
            <div><span class="status-available me-2"></span><strong>${c.name}</strong><br><small class="text-muted">${c.ip}:${c.port}</small></div>
            <button class="btn btn-primary btn-sm" ${sel ? 'disabled' : ''} data-car-id="${c.id}">เลือก</button>
          </div>
        `).join('') : `<p class="text-muted">${availError ? '—' : 'ไม่มีหุ่นยนต์พร้อมใช้งาน ตรวจสอบการเชื่อมต่อ'}</p>`}
      </div>
    `;
    container.innerHTML = html;
    if (!isActive()) return;

    container.querySelectorAll('[data-car-id]').forEach(btn => {
      const carId = btn.dataset.carId;
      const carName = btn.closest('.robot-card').querySelector('strong').textContent;
      btn.onclick = async () => {
        try {
          const res = await api.post('/api/robots/select', { carId });
          showToast(res.message || 'เลือกหุ่นยนต์แล้ว');
          onSelect(res.selectedCar || { id: carId, name: carName });
          renderRobotSelector(container, onSelect, onRelease, isActive);
        } catch (e) {
          const msg = e?.error || (e?.status === 409 ? 'รถถูกใช้งานไปแล้ว กรุณาเลือกคันอื่น' : 'เลือกหุ่นยนต์ไม่สำเร็จ');
          showToast(msg, 'danger');
          renderRobotSelector(container, onSelect, onRelease, isActive);
        }
      };
    });
    const releaseBtn = document.getElementById('btn-release');
    if (releaseBtn) releaseBtn.onclick = async () => {
      try {
        await api.post('/api/robots/release', { carId: sel.id });
        showToast('ยกเลิกการเลือกแล้ว');
        onRelease();
        renderRobotSelector(container, onSelect, onRelease, isActive);
      } catch (e) { showToast(e.error || 'Failed', 'danger'); }
    };
  } catch (e) {
    if (!isActive()) return;
    container.innerHTML = `<div class="card-custom"><p class="text-danger">โหลดไม่สำเร็จ: ${e.error || e.message}</p></div>`;
  }
}

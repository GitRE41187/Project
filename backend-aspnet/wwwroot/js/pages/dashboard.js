/** Dashboard page */
async function renderDashboard(container, isCurrentView) {
  const html = await loadTemplate('dashboard');
  if (!isCurrentView()) return () => {};
  container.innerHTML = html;

  const summaryEl = document.getElementById('dashboard-summary');
  const sel = document.getElementById('robot-selector');
  if (!sel) return () => {};

  let countdownInterval = null;

  async function renderSummary() {
    if (!isCurrentView() || !summaryEl) return;
    clearInterval(countdownInterval);
    try {
      const [qRes, sRes] = await Promise.allSettled([
        api.get('/api/queue/my-bookings'),
        api.get('/api/control/status')
      ]);
      if (!isCurrentView()) return;

      const bookings = qRes.status === 'fulfilled' ? (qRes.value.bookings || []) : [];
      const status   = sRes.status === 'fulfilled' ? sRes.value : null;
      const active   = bookings.find(b => b.status === 'active');
      const pending  = bookings.filter(b => b.status === 'pending').length;
      const hasActive = status?.hasActiveBooking || !!active;
      const car       = status?.selectedCar;
      const endTime   = active?.end_time || null;

      const fmtRemaining = () => {
        if (!endTime) return '';
        const ms = new Date(endTime) - new Date();
        if (ms <= 0) return 'หมดเวลา';
        const m = Math.floor(ms / 60000);
        const s = Math.floor((ms % 60000) / 1000);
        return `${m}:${String(s).padStart(2, '0')} นาที`;
      };

      summaryEl.innerHTML = `
        <div class="col-sm-6 col-lg-4">
          <div class="card-custom stat-tile py-3 dash-stat-card">
            <div class="stat-tile-label"><i class="bi bi-calendar-check me-1"></i>การจอง</div>
            <div class="stat-tile-value ${hasActive ? 'text-success' : ''}">
              ${hasActive ? 'ใช้งานอยู่' : pending > 0 ? `${pending} รอดำเนินการ` : 'ไม่มี'}
            </div>
            ${endTime ? `<div class="dash-stat-countdown" id="dash-countdown"><i class="bi bi-hourglass-split me-1"></i>${fmtRemaining()}</div>` : ''}
          </div>
        </div>
        <div class="col-sm-6 col-lg-4">
          <div class="card-custom stat-tile py-3 dash-stat-card">
            <div class="stat-tile-label"><i class="bi bi-robot me-1"></i>หุ่นยนต์ที่เลือก</div>
            <div class="stat-tile-value">
              ${car ? `<span class="text-success">${car.name}</span>` : '<span style="font-size:1rem;color:var(--text-muted)">ยังไม่ได้เลือก</span>'}
            </div>
            ${car ? `<div class="small mt-1 ${car.isConnected ? 'text-success' : 'text-danger'}">${car.isConnected ? '● เชื่อมต่อแล้ว' : '● ไม่ได้เชื่อมต่อ'}</div>` : ''}
          </div>
        </div>
        <div class="col-12 col-lg-4 d-flex align-items-center gap-2">
          <button class="btn btn-primary flex-fill" onclick="navigate('control')">
            <i class="bi bi-joystick me-1"></i> ควบคุมสนาม
          </button>
          <button class="btn btn-outline-secondary flex-fill" onclick="navigate('queue')">
            <i class="bi bi-calendar-plus me-1"></i> จองคิว
          </button>
        </div>
      `;

      if (endTime) {
        countdownInterval = setInterval(() => {
          if (!isCurrentView()) { clearInterval(countdownInterval); return; }
          const el = document.getElementById('dash-countdown');
          if (!el) { clearInterval(countdownInterval); return; }
          const ms = new Date(endTime) - new Date();
          if (ms <= 0) {
            el.innerHTML = '<i class="bi bi-hourglass-bottom me-1"></i>หมดเวลา';
            clearInterval(countdownInterval);
          } else {
            const m = Math.floor(ms / 60000);
            const s = Math.floor((ms % 60000) / 1000);
            el.innerHTML = `<i class="bi bi-hourglass-split me-1"></i>${m}:${String(s).padStart(2, '0')} นาที`;
          }
        }, 1000);
      }
    } catch (_) {
      if (summaryEl && isCurrentView()) summaryEl.innerHTML = '';
    }
  }

  let debounce;
  const onSelect = () => { renderSummary(); };
  const onRelease = () => { renderSummary(); };

  const refreshList = () => {
    if (!isCurrentView() || !sel) return;
    clearTimeout(debounce);
    debounce = setTimeout(() => renderRobotSelector(sel, onSelect, onRelease, isCurrentView), 400);
  };
  const unsubs = [
    RobotRealtime.on('RobotStatusUpdate', refreshList),
    RobotRealtime.on('RobotHeartbeat', refreshList)
  ];

  await renderSummary();
  renderRobotSelector(sel, onSelect, onRelease, isCurrentView);

  return () => {
    clearTimeout(debounce);
    clearInterval(countdownInterval);
    unsubs.forEach((u) => u());
  };
}

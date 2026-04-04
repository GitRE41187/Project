/** Admin page */
async function renderAdmin(container, isCurrentView) {
  try {
    const html = await loadTemplate('admin');
    if (!isCurrentView()) return;
    container.innerHTML = html;

    const [statsResult, bookingsResult, logsResult] = await Promise.allSettled([
      api.get('/api/logs/admin/stats'),
      api.get('/api/queue/admin/all'),
      api.get('/api/logs/admin/all?limit=50')
    ]);

    if (!isCurrentView()) return;

    const stats = statsResult.status === 'fulfilled' ? (statsResult.value.stats || {}) : {};
    const bookings = bookingsResult.status === 'fulfilled' ? (bookingsResult.value.bookings || []) : [];
    const logs = logsResult.status === 'fulfilled' ? (logsResult.value.logs || []) : [];
    const failedParts = [];
    if (statsResult.status !== 'fulfilled') failedParts.push('สถิติ');
    if (bookingsResult.status !== 'fulfilled') failedParts.push('ข้อมูลการจอง');
    if (logsResult.status !== 'fulfilled') failedParts.push('บันทึกกิจกรรม');

    const statsEl = document.getElementById('admin-stats');
    const bookBody = document.getElementById('admin-bookings-tbody');
    const logsBody = document.getElementById('admin-logs-tbody');
    if (!statsEl || !bookBody || !logsBody) return;

    statsEl.innerHTML = `
      <div class="col-sm-6 col-xl-3"><div class="card-custom stat-tile"><div class="stat-tile-label">ผู้ใช้ทั้งหมด</div><div class="stat-tile-value">${stats.totalUsers ?? 0}</div></div></div>
      <div class="col-sm-6 col-xl-3"><div class="card-custom stat-tile"><div class="stat-tile-label">การจองที่ใช้งาน</div><div class="stat-tile-value">${stats.activeBookings ?? 0}</div></div></div>
      <div class="col-sm-6 col-xl-3"><div class="card-custom stat-tile"><div class="stat-tile-label">อัปโหลดทั้งหมด</div><div class="stat-tile-value">${stats.totalUploads ?? 0}</div></div></div>
      <div class="col-sm-6 col-xl-3"><div class="card-custom stat-tile"><div class="stat-tile-label">กิจกรรมล่าสุด</div><div class="stat-tile-value">${stats.recentActivity ?? 0}</div></div></div>
    `;

    bookBody.innerHTML = bookings.length
      ? bookings.map(b => `<tr><td>${b.username}</td><td>${b.field_name || 'Main'}</td><td>${new Date(b.start_time).toLocaleString()}</td><td>${new Date(b.end_time).toLocaleString()}</td><td>${b.status}</td></tr>`).join('')
      : '<tr><td colspan="5" class="text-center text-muted">ไม่มีข้อมูล</td></tr>';
    logsBody.innerHTML = logs.length
      ? logs.map(l => `<tr><td>${l.username}</td><td>${l.action}</td><td>${l.details || '-'}</td><td>${new Date(l.executed_at).toLocaleString()}</td></tr>`).join('')
      : '<tr><td colspan="4" class="text-center text-muted">ไม่มีข้อมูล</td></tr>';

    if (failedParts.length) {
      const warn = document.createElement('div');
      warn.className = 'card-custom border border-warning mb-3';
      warn.innerHTML = `<p class="text-warning mb-0">โหลดข้อมูลไม่ครบ: ${failedParts.join(', ')}</p>`;
      container.prepend(warn);
    }
  } catch (e) {
    if (!isCurrentView()) return;
    container.innerHTML = `<div class="card-custom"><p class="text-danger">${e.error || 'Failed to load admin data'}</p></div>`;
  }
}

/** Admin page */
async function renderAdmin(container) {
  try {
    const html = await loadTemplate('admin');
    container.innerHTML = html;

    const [statsResult, bookingsResult, logsResult] = await Promise.allSettled([
      api.get('/api/logs/admin/stats'),
      api.get('/api/queue/admin/all'),
      api.get('/api/logs/admin/all?limit=50')
    ]);

    const stats = statsResult.status === 'fulfilled' ? (statsResult.value.stats || {}) : {};
    const bookings = bookingsResult.status === 'fulfilled' ? (bookingsResult.value.bookings || []) : [];
    const logs = logsResult.status === 'fulfilled' ? (logsResult.value.logs || []) : [];
    const failedParts = [];
    if (statsResult.status !== 'fulfilled') failedParts.push('สถิติ');
    if (bookingsResult.status !== 'fulfilled') failedParts.push('ข้อมูลการจอง');
    if (logsResult.status !== 'fulfilled') failedParts.push('บันทึกกิจกรรม');

    document.getElementById('admin-stats').innerHTML = `
      <div class="col-md-3"><div class="card-custom"><h6 class="text-muted">ผู้ใช้ทั้งหมด</h6><h3>${stats.totalUsers ?? 0}</h3></div></div>
      <div class="col-md-3"><div class="card-custom"><h6 class="text-muted">การจองที่ใช้งาน</h6><h3>${stats.activeBookings ?? 0}</h3></div></div>
      <div class="col-md-3"><div class="card-custom"><h6 class="text-muted">อัปโหลดทั้งหมด</h6><h3>${stats.totalUploads ?? 0}</h3></div></div>
      <div class="col-md-3"><div class="card-custom"><h6 class="text-muted">กิจกรรมล่าสุด</h6><h3>${stats.recentActivity ?? 0}</h3></div></div>
    `;

    document.getElementById('admin-bookings-tbody').innerHTML = bookings.length
      ? bookings.map(b => `<tr><td>${b.username}</td><td>${b.field_name || 'Main'}</td><td>${new Date(b.start_time).toLocaleString()}</td><td>${new Date(b.end_time).toLocaleString()}</td><td>${b.status}</td></tr>`).join('')
      : '<tr><td colspan="5" class="text-center text-muted">ไม่มีข้อมูล</td></tr>';
    document.getElementById('admin-logs-tbody').innerHTML = logs.length
      ? logs.map(l => `<tr><td>${l.username}</td><td>${l.action}</td><td>${l.details || '-'}</td><td>${new Date(l.executed_at).toLocaleString()}</td></tr>`).join('')
      : '<tr><td colspan="4" class="text-center text-muted">ไม่มีข้อมูล</td></tr>';

    if (failedParts.length) {
      const warn = document.createElement('div');
      warn.className = 'card-custom border border-warning mb-3';
      warn.innerHTML = `<p class="text-warning mb-0">โหลดข้อมูลไม่ครบ: ${failedParts.join(', ')}</p>`;
      container.prepend(warn);
    }
  } catch (e) {
    container.innerHTML = `<div class="card-custom"><p class="text-danger">${e.error || 'Failed to load admin data'}</p></div>`;
  }
}

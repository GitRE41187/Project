/** Control page */
async function renderControl(container) {
  let selectedCar = null;
  let executionStatus = null;
  let cameraStatus = null;
  let hasActiveBooking = false;

  const statusEl = () => {
    const robotDetail = selectedCar
      ? `<div class="mt-2 small text-muted">สถานะหุ่นยนต์: ${robotStatusLabelTh(selectedCar.status)} · ${selectedCar.isConnected ? 'เชื่อมต่อ' : 'ไม่เชื่อมต่อ'}${formatRobotBattery(selectedCar.battery) ? ` · แบตเตอรี่: ${formatRobotBattery(selectedCar.battery)}` : ''}</div>`
      : '';
    return `
    <div class="card-custom mb-4">
      <h5 class="mb-3">สถานะระบบ</h5>
      <div class="row g-3">
        <div class="col-md-6"><span class="badge ${hasActiveBooking ? 'bg-success' : 'bg-warning'}">จอง: ${hasActiveBooking ? 'ใช้งาน' : 'ไม่มี'}</span></div>
        <div class="col-md-6">
          <span class="badge ${selectedCar ? 'bg-success' : 'bg-danger'}">หุ่นยนต์: ${selectedCar ? selectedCar.name : 'ยังไม่เลือก'}</span>
          ${robotDetail}
        </div>
        <div class="col-md-6"><span class="badge ${executionStatus?.executionStatus?.is_running ? 'bg-success' : 'bg-secondary'}">การรัน: ${executionStatus?.executionStatus?.is_running ? 'ทำงาน' : 'หยุด'}</span></div>
        <div class="col-md-6"><span class="badge ${cameraStatus?.cameraStatus?.camera_active ? 'bg-success' : 'bg-secondary'}">กล้อง: ${cameraStatus?.cameraStatus?.camera_active ? 'เปิด' : 'ปิด'}</span></div>
      </div>
    </div>
  `;
  };

  const refresh = async () => {
    try {
      const [s, c, myCar] = await Promise.all([
        api.get('/api/control/status'),
        api.get('/api/control/camera/status'),
        api.get('/api/robots/my-car')
      ]);
      executionStatus = s;
      cameraStatus = c;
      hasActiveBooking = s.hasActiveBooking;
      selectedCar = s.selectedCar || (myCar.hasSelectedCar ? myCar.selectedCar : null);
    } catch (_) {}
  };

  const html = await loadTemplate('control');
  container.innerHTML = html;

  const updateUI = () => {
    document.getElementById('status-area').innerHTML = statusEl();
    const checkinWrap = document.getElementById('checkin-wrap');
    if (!hasActiveBooking) {
      checkinWrap.innerHTML = '<button class="btn btn-primary w-100 mt-2" id="btn-checkin">ลงทะเบียนเข้าใช้งาน</button>';
      const checkin = document.getElementById('btn-checkin');
      if (checkin) checkin.onclick = async () => {
        try { await api.post('/api/control/checkin'); showToast('ลงทะเบียนแล้ว'); await refresh(); updateUI(); } catch (e) { showToast(e.error || 'Failed', 'danger'); }
      };
    } else checkinWrap.innerHTML = '';
    ['btn-run','btn-stop','btn-reset','btn-cam-start','btn-cam-stop'].forEach(id => {
      const btn = document.getElementById(id);
      if (btn) btn.disabled = (id === 'btn-run' || id === 'btn-reset') && (!hasActiveBooking || !selectedCar) || (id === 'btn-stop' && !executionStatus?.executionStatus?.is_running);
    });
  };

  await refresh();
  updateUI();

  renderRobotSelector(document.getElementById('robot-selector-control'), (car) => { selectedCar = car; refresh().then(updateUI); }, () => { selectedCar = null; refresh().then(updateUI); }, selectedCar);

  document.getElementById('drop-zone').onclick = () => document.getElementById('file-input').click();
  document.getElementById('drop-zone').ondragover = (e) => { e.preventDefault(); e.currentTarget.classList.add('drag-over'); };
  document.getElementById('drop-zone').ondragleave = (e) => { e.currentTarget.classList.remove('drag-over'); };
  document.getElementById('drop-zone').ondrop = (e) => {
    e.preventDefault();
    e.currentTarget.classList.remove('drag-over');
    const f = e.dataTransfer?.files?.[0];
    if (f && f.name.endsWith('.py')) uploadFile(f);
  };
  document.getElementById('file-input').onchange = (e) => { const f = e.target.files?.[0]; if (f) uploadFile(f); e.target.value = ''; };

  async function uploadFile(file) {
    try {
      const fd = new FormData();
      fd.append('codeFile', file);
      const res = await api.postForm('/api/uploads/upload', fd);
      showToast(res.message);
      loadUploads();
      await refresh();
      updateUI();
    } catch (e) { showToast(e.error || 'Upload failed', 'danger'); }
  }

  async function loadUploads() {
    try {
      const res = await api.get('/api/uploads/my-uploads');
      const list = document.getElementById('uploads-list');
      const uploads = res.uploads || [];
      list.innerHTML = uploads.length ? uploads.map(u => `
        <div class="d-flex justify-content-between align-items-center py-2 border-bottom">
          <span>${u.original_filename}</span>
          <button class="btn btn-outline-danger btn-sm" data-id="${u.id}">ลบ</button>
        </div>
      `).join('') : '<p class="text-muted">ยังไม่มีไฟล์อัปโหลด</p>';
      list.querySelectorAll('[data-id]').forEach(btn => {
        const uid = btn.dataset.id;
        btn.onclick = async () => {
          if (!confirm('ลบ?')) return;
          try { await api.delete(`/api/uploads/${uid}`); showToast('ลบแล้ว'); loadUploads(); } catch (e) { showToast(e.error || 'Failed', 'danger'); }
        };
      });
    } catch (_) {}
  }
  loadUploads();

  document.getElementById('btn-run').onclick = async () => { try { await api.post('/api/control/run'); showToast('กำลังรัน'); await refresh(); updateUI(); } catch (e) { showToast(e.error, 'danger'); } };
  document.getElementById('btn-stop').onclick = async () => { try { await api.post('/api/control/stop'); showToast('หยุดแล้ว'); await refresh(); updateUI(); } catch (e) { showToast(e.error, 'danger'); } };
  document.getElementById('btn-reset').onclick = async () => { try { await api.post('/api/control/reset'); showToast('รีเซ็ตแล้ว'); await refresh(); updateUI(); } catch (e) { showToast(e.error, 'danger'); } };
  document.getElementById('btn-cam-start').onclick = async () => {
    try {
      const res = await api.post('/api/control/camera/start');
      showToast('เปิดกล้องแล้ว');
      const feed = document.getElementById('camera-feed');
      const streamUrl = res.cameraStreamUrl || (cameraStatus?.cameraStreamUrl);
      feed.innerHTML = streamUrl ? `<img src="${streamUrl}" class="img-fluid rounded" style="max-height:300px" onerror="this.style.display='none'">` : '<p class="text-muted">No stream URL</p>';
      await refresh();
      updateUI();
    } catch (e) { showToast(e.error || 'Failed', 'danger'); }
  };
  document.getElementById('btn-cam-stop').onclick = async () => { try { await api.post('/api/control/camera/stop'); showToast('ปิดกล้องแล้ว'); document.getElementById('camera-feed').innerHTML = ''; await refresh(); updateUI(); } catch (e) { showToast(e.error, 'danger'); } };
}

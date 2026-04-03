/** Control page */
async function renderControl(container) {
  let selectedCar = null;
  let executionStatus = null;
  let cameraStatus = null;
  let hasActiveBooking = false;
  let selectedScriptFilename = null;
  let robotFilesCount = 0;

  const fmtSize = (n) => {
    if (n == null || Number.isNaN(n)) return '';
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  };

  const canUseRobotFiles = () => hasActiveBooking && selectedCar;

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
    } catch (_) {
      /* keep last known state; realtime + next poll will recover */
    }
  };

  const html = await loadTemplate('control');
  container.innerHTML = html;

  const selEl = document.getElementById('robot-selector-control');
  const onSel = (car) => {
    selectedCar = car;
    refresh().then(() => {
      loadUploads();
      updateUI();
    });
  };
  const onRel = () => {
    selectedCar = null;
    refresh().then(() => {
      loadUploads();
      updateUI();
    });
  };

  let selectorRefreshTimer = null;
  function scheduleSelectorRefresh() {
    if (currentPage !== 'control' || !selEl) return;
    clearTimeout(selectorRefreshTimer);
    selectorRefreshTimer = setTimeout(() => {
      renderRobotSelector(selEl, onSel, onRel, selectedCar);
    }, 350);
  }

  const setDropZoneEnabled = (on) => {
    const z = document.getElementById('drop-zone');
    if (!z) return;
    z.style.opacity = on ? '' : '0.5';
    z.style.pointerEvents = on ? '' : 'none';
  };

  const updateUI = () => {
    document.getElementById('status-area').innerHTML = statusEl();
    const checkinWrap = document.getElementById('checkin-wrap');
    if (!hasActiveBooking) {
      checkinWrap.innerHTML = '<button class="btn btn-primary w-100 mt-2" id="btn-checkin">ลงทะเบียนเข้าใช้งาน</button>';
      const checkin = document.getElementById('btn-checkin');
      if (checkin) {
        checkin.onclick = async () => {
          try {
            await api.post('/api/control/checkin');
            showToast('ลงทะเบียนแล้ว');
            await refresh();
            updateUI();
          } catch (e) {
            showToast(e.error || 'Failed', 'danger');
          }
        };
      }
    } else checkinWrap.innerHTML = '';

    const canRunLoose = hasActiveBooking && selectedCar && robotFilesCount > 0 && (robotFilesCount === 1 || selectedScriptFilename);

    setDropZoneEnabled(canUseRobotFiles());

    ['btn-run', 'btn-stop', 'btn-reset', 'btn-cam-start', 'btn-cam-stop'].forEach((id) => {
      const btn = document.getElementById(id);
      if (!btn) return;
      if (id === 'btn-run') btn.disabled = !canRunLoose;
      else if (id === 'btn-stop') btn.disabled = !executionStatus?.executionStatus?.is_running;
      else btn.disabled = !hasActiveBooking || !selectedCar;
    });
  };

  const onHeartbeat = (p) => {
    if (!p?.carId || !selectedCar || p.carId !== selectedCar.id) return;
    const next = { ...selectedCar };
    if (p.status) next.status = p.status;
    if (p.battery !== undefined) next.battery = p.battery;
    next.isConnected = true;
    selectedCar = next;
    updateUI();
  };

  const onRobotStatus = (p) => {
    if (!p?.carId) return;
    if (selectedCar && p.carId === selectedCar.id) {
      const next = { ...selectedCar };
      if (p.status === 'disconnected') {
        next.isConnected = false;
        next.status = 'offline';
      } else if (p.status) {
        next.status = p.status;
        next.isConnected = true;
      }
      selectedCar = next;
      updateUI();
    }
    scheduleSelectorRefresh();
  };

  const onCodeUploaded = (payload) => {
    const uid = user?.id;
    const batch = Array.isArray(payload) ? payload : [payload];
    for (const item of batch) {
      if (item == null) continue;
      if (item.userId != null && uid != null && Number(item.userId) !== Number(uid)) continue;
      if (selectedCar && item.carId && item.carId !== selectedCar.id) continue;
      loadUploads();
      break;
    }
  };

  const unsubs = [
    RobotRealtime.on('RobotHeartbeat', onHeartbeat),
    RobotRealtime.on('RobotStatusUpdate', onRobotStatus),
    RobotRealtime.on('RobotCodeUploaded', onCodeUploaded)
  ];

  const pollMs = 8000;
  const pollTimer = setInterval(() => {
    if (currentPage !== 'control') return;
    refresh().then(() => updateUI());
  }, pollMs);

  await refresh();
  updateUI();

  renderRobotSelector(selEl, onSel, onRel, selectedCar);

  document.getElementById('drop-zone').onclick = () => {
    if (!canUseRobotFiles()) {
      showToast('กรุณาให้มีช่วงจองที่ใช้งานและเลือกรถก่อน', 'warning');
      return;
    }
    document.getElementById('file-input').click();
  };
  document.getElementById('drop-zone').ondragover = (e) => {
    e.preventDefault();
    if (canUseRobotFiles()) e.currentTarget.classList.add('drag-over');
  };
  document.getElementById('drop-zone').ondragleave = (e) => {
    e.preventDefault();
    e.currentTarget.classList.remove('drag-over');
  };
  document.getElementById('drop-zone').ondrop = (e) => {
    e.preventDefault();
    e.currentTarget.classList.remove('drag-over');
    if (!canUseRobotFiles()) {
      showToast('กรุณาให้มีช่วงจองที่ใช้งานและเลือกรถก่อน', 'warning');
      return;
    }
    const f = e.dataTransfer?.files?.[0];
    if (f && f.name.endsWith('.py')) uploadFile(f);
  };
  document.getElementById('file-input').onchange = (e) => {
    const f = e.target.files?.[0];
    if (f) uploadFile(f);
    e.target.value = '';
  };

  async function uploadFile(file) {
    if (!canUseRobotFiles()) {
      showToast('กรุณาให้มีช่วงจองที่ใช้งานและเลือกรถก่อน', 'warning');
      return;
    }
    if (!file.name.toLowerCase().endsWith('.py')) {
      showToast('อนุญาตเฉพาะไฟล์ .py', 'warning');
      return;
    }
    try {
      const fd = new FormData();
      fd.append('codeFile', file, file.name);
      const res = await api.postForm('/api/uploads/upload', fd);
      showToast(res.message || 'อัปโหลดแล้ว');
      await loadUploads();
      await refresh();
      updateUI();
    } catch (e) {
      const msg = e.error || e.detail || (e.status === 403 ? 'ไม่มีสิทธิ์อัปโหลด (จอง/เลือกรถ)' : 'อัปโหลดไม่สำเร็จ');
      showToast(typeof msg === 'string' ? msg : 'อัปโหลดไม่สำเร็จ', 'danger');
    }
  }

  async function loadUploads() {
    const list = document.getElementById('uploads-list');
    if (!canUseRobotFiles()) {
      robotFilesCount = 0;
      selectedScriptFilename = null;
      list.innerHTML = '<p class="text-muted">เลือกรถและให้จองอยู่ในช่วงใช้งานเพื่อดูรายการไฟล์บนรถ</p>';
      updateUI();
      return;
    }
    try {
      const res = await api.get('/api/uploads/my-uploads');
      const files = res.files || [];
      robotFilesCount = files.length;
      if (files.length === 1) selectedScriptFilename = files[0].filename;
      else if (files.length > 1 && selectedScriptFilename && !files.some((x) => x.filename === selectedScriptFilename))
        selectedScriptFilename = null;

      list.innerHTML = files.length
        ? files
            .map(
              (u, i) => `
        <div class="d-flex flex-wrap justify-content-between align-items-center py-2 border-bottom gap-2">
          <div class="form-check">
            <input class="form-check-input" type="radio" name="robot-script" id="rs-${i}" value="${encodeURIComponent(u.filename)}" ${selectedScriptFilename === u.filename ? 'checked' : ''}>
            <label class="form-check-label" for="rs-${i}">${u.filename} <span class="text-muted small">${fmtSize(u.size)}</span></label>
          </div>
          <button type="button" class="btn btn-outline-danger btn-sm" data-filename="${encodeURIComponent(u.filename)}">ลบบนรถ</button>
        </div>
      `
            )
            .join('')
        : '<p class="text-muted">ยังไม่มีไฟล์ .py บนรถ</p>';

      list.querySelectorAll('input[name="robot-script"]').forEach((radio) => {
        radio.onchange = () => {
          selectedScriptFilename = decodeURIComponent(radio.value);
          updateUI();
        };
      });
      list.querySelectorAll('[data-filename]').forEach((btn) => {
        btn.onclick = async () => {
          const name = decodeURIComponent(btn.dataset.filename);
          if (!confirm(`ลบ ${name} บนรถ?`)) return;
          try {
            await api.delete(`/api/uploads/file?filename=${encodeURIComponent(name)}`);
            showToast('ลบบนรถแล้ว');
            if (selectedScriptFilename === name) selectedScriptFilename = null;
            await loadUploads();
            updateUI();
          } catch (e) {
            showToast(e.error || 'Failed', 'danger');
          }
        };
      });
    } catch (e) {
      list.innerHTML = `<p class="text-danger">${e.error || 'โหลดรายการไฟล์ไม่สำเร็จ'}</p>`;
      robotFilesCount = 0;
    }
    updateUI();
  }

  document.getElementById('btn-refresh-files').onclick = () => loadUploads();

  document.getElementById('btn-run').onclick = async () => {
    if (!canUseRobotFiles()) {
      showToast('จองและเลือกรถก่อน', 'warning');
      return;
    }
    if (robotFilesCount > 1 && !selectedScriptFilename) {
      showToast('เลือกไฟล์ที่จะรัน', 'warning');
      return;
    }
    const body = {};
    if (selectedScriptFilename) body.filename = selectedScriptFilename;
    try {
      await api.post('/api/control/run', body);
      showToast('กำลังรัน');
      await refresh();
      updateUI();
    } catch (e) {
      showToast(e.error, 'danger');
    }
  };
  document.getElementById('btn-stop').onclick = async () => {
    try {
      await api.post('/api/control/stop');
      showToast('หยุดแล้ว');
      await refresh();
      updateUI();
    } catch (e) {
      showToast(e.error, 'danger');
    }
  };
  document.getElementById('btn-reset').onclick = async () => {
    try {
      await api.post('/api/control/reset');
      showToast('รีเซ็ตแล้ว');
      await refresh();
      updateUI();
    } catch (e) {
      showToast(e.error, 'danger');
    }
  };
  document.getElementById('btn-cam-start').onclick = async () => {
    try {
      const res = await api.post('/api/control/camera/start');
      showToast('เปิดกล้องแล้ว');
      const feed = document.getElementById('camera-feed');
      const streamUrl = res.cameraStreamUrl || cameraStatus?.cameraStreamUrl;
      feed.innerHTML = streamUrl
        ? `<img src="${streamUrl}" class="img-fluid rounded" style="max-height:300px" onerror="this.style.display='none'">`
        : '<p class="text-muted">No stream URL</p>';
      await refresh();
      updateUI();
    } catch (e) {
      showToast(e.error || 'Failed', 'danger');
    }
  };
  document.getElementById('btn-cam-stop').onclick = async () => {
    try {
      await api.post('/api/control/camera/stop');
      showToast('ปิดกล้องแล้ว');
      document.getElementById('camera-feed').innerHTML = '';
      await refresh();
      updateUI();
    } catch (e) {
      showToast(e.error, 'danger');
    }
  };

  loadUploads();

  return () => {
    clearInterval(pollTimer);
    clearTimeout(selectorRefreshTimer);
    unsubs.forEach((u) => u());
  };
}

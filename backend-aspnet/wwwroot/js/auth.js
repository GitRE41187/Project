/** Auth page: login / register */
let authRenderGeneration = 0;

async function renderAuthPage(type) {
  const myGen = ++authRenderGeneration;
  const isCurrentAuth = () => myGen === authRenderGeneration;

  const isLogin = type === 'login';
  const container = document.getElementById('auth-pages');
  container.className = 'auth-container';

  const html = await loadTemplate('auth');
  if (!isCurrentAuth()) return;
  container.innerHTML = html;
  if (window.FieldControlTheme) {
    window.FieldControlTheme.apply(window.FieldControlTheme.getTheme());
  }
  container.classList.remove('d-none');
  document.getElementById('app-layout').classList.add('d-none');

  const title = document.getElementById('auth-title');
  const subtitle = document.getElementById('auth-subtitle');
  const submitBtn = document.getElementById('auth-submit');
  const switchText = document.getElementById('auth-switch-text');
  const switchLink = document.getElementById('switch-auth');
  const fieldEmail = document.getElementById('field-email');
  const fieldConfirm = document.getElementById('field-confirm');

  if (isLogin) {
    title.textContent = 'ยินดีต้อนรับกลับ!';
    subtitle.textContent = 'เข้าสู่ระบบด้วยบัญชีของคุณ';
    submitBtn.textContent = 'เข้าสู่ระบบ';
    switchText.textContent = 'ยังไม่มีบัญชี? ';
    switchLink.textContent = 'สมัครฟรี';
    fieldEmail.classList.add('d-none');
    fieldConfirm.classList.add('d-none');
  } else {
    title.textContent = 'สมัครสมาชิก';
    subtitle.textContent = 'กรอกข้อมูลเพื่อเริ่มต้นใช้งาน';
    submitBtn.textContent = 'สมัครสมาชิก';
    switchText.textContent = 'มีบัญชีอยู่แล้ว? ';
    switchLink.textContent = 'เข้าสู่ระบบ';
    fieldEmail.classList.remove('d-none');
    fieldConfirm.classList.remove('d-none');
    fieldEmail.querySelector('input').required = true;
    fieldConfirm.querySelector('input').required = true;
  }

  function clearFieldErrors() {
    ['username', 'email', 'password', 'confirm'].forEach(f => {
      const input = document.getElementById(`input-${f}`);
      const err = document.getElementById(`err-${f}`);
      if (input) input.classList.remove('is-invalid');
      if (err) err.textContent = '';
    });
  }

  function setFieldError(inputId, errId, message) {
    const input = document.getElementById(inputId);
    const err = document.getElementById(errId);
    if (input) input.classList.add('is-invalid');
    if (err) err.textContent = message;
  }

  function handleServerError(errorMsg) {
    const msg = (errorMsg || '').toLowerCase();
    if (msg.includes('username or email')) {
      setFieldError('input-username', 'err-username', 'ชื่อผู้ใช้นี้ถูกใช้ไปแล้ว');
      setFieldError('input-email', 'err-email', 'อีเมลนี้ถูกใช้ไปแล้ว');
    } else if (msg.includes('username')) {
      setFieldError('input-username', 'err-username', errorMsg);
    } else if (msg.includes('email')) {
      setFieldError('input-email', 'err-email', errorMsg);
    } else if (msg.includes('password')) {
      setFieldError('input-password', 'err-password', errorMsg);
    } else if (msg.includes('credentials') || msg.includes('invalid')) {
      setFieldError('input-username', 'err-username', 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง');
      setFieldError('input-password', 'err-password', 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง');
    } else {
      showToast(errorMsg || 'เกิดข้อผิดพลาด', 'danger');
    }
  }

  document.getElementById('auth-form').onsubmit = async (e) => {
    e.preventDefault();
    if (!isCurrentAuth()) return;
    clearFieldErrors();
    const fd = new FormData(e.target);
    const data = Object.fromEntries(fd);
    if (!isLogin) {
      if (data.password !== data.confirmPassword) {
        setFieldError('input-confirm', 'err-confirm', 'รหัสผ่านไม่ตรงกัน');
        return;
      }
    }
    if (data.password.length < 6) {
      setFieldError('input-password', 'err-password', 'รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร');
      return;
    }
    try {
      const url = isLogin ? '/api/auth/login' : '/api/auth/register';
      const body = isLogin
        ? { username: data.username, password: data.password }
        : { username: data.username, email: data.email, password: data.password };
      const res = await api.post(url, body);
      if (!isCurrentAuth()) return;
      api.setToken(res.token);
      user = res.user;
      showToast(res.message);
      initApp();
    } catch (err) {
      if (!isCurrentAuth()) return;
      handleServerError(err.error);
    }
  };
  switchLink.onclick = (e) => {
    e.preventDefault();
    renderAuthPage(isLogin ? 'register' : 'login');
  };
}

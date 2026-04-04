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

  document.getElementById('auth-form').onsubmit = async (e) => {
    e.preventDefault();
    if (!isCurrentAuth()) return;
    const fd = new FormData(e.target);
    const data = Object.fromEntries(fd);
    if (!isLogin) {
      if (data.password !== data.confirmPassword) {
        showToast('รหัสผ่านไม่ตรงกัน', 'danger');
        return;
      }
    }
    if (data.password.length < 6) {
      showToast('รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร', 'danger');
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
      showToast(err.error || 'Failed', 'danger');
    }
  };
  switchLink.onclick = (e) => {
    e.preventDefault();
    renderAuthPage(isLogin ? 'register' : 'login');
  };
}

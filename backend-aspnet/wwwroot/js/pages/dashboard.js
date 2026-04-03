/** Dashboard page */
async function renderDashboard(container) {
  const html = await loadTemplate('dashboard');
  container.innerHTML = html;
  const sel = document.getElementById('robot-selector');
  let debounce;
  const refreshList = () => {
    if (currentPage !== 'dashboard' || !sel) return;
    clearTimeout(debounce);
    debounce = setTimeout(() => renderRobotSelector(sel, () => {}, () => {}), 400);
  };
  const unsubs = [RobotRealtime.on('RobotStatusUpdate', refreshList), RobotRealtime.on('RobotHeartbeat', refreshList)];
  renderRobotSelector(sel, () => {}, () => {});
  return () => {
    clearTimeout(debounce);
    unsubs.forEach((u) => u());
  };
}

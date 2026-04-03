/** Dashboard page */
async function renderDashboard(container, isCurrentView) {
  const html = await loadTemplate('dashboard');
  if (!isCurrentView()) return () => {};
  container.innerHTML = html;
  const sel = document.getElementById('robot-selector');
  if (!sel) return () => {};
  let debounce;
  const refreshList = () => {
    if (!isCurrentView() || !sel) return;
    clearTimeout(debounce);
    debounce = setTimeout(() => renderRobotSelector(sel, () => {}, () => {}, isCurrentView), 400);
  };
  const unsubs = [RobotRealtime.on('RobotStatusUpdate', refreshList), RobotRealtime.on('RobotHeartbeat', refreshList)];
  renderRobotSelector(sel, () => {}, () => {}, isCurrentView);
  return () => {
    clearTimeout(debounce);
    unsubs.forEach((u) => u());
  };
}

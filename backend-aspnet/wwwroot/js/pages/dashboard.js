/** Dashboard page */
async function renderDashboard(container) {
  const html = await loadTemplate('dashboard');
  container.innerHTML = html;
  renderRobotSelector(document.getElementById('robot-selector'), () => {}, () => {});
}

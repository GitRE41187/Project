/** Browser SignalR client for /hubs/robot — robot status, heartbeat, uploads */
const RobotRealtime = (function () {
  let connection = null;
  let startPromise = null;
  const handlers = {
    RobotStatusUpdate: new Set(),
    RobotHeartbeat: new Set(),
    RobotCodeUploaded: new Set(),
    DeployResult: new Set(),
    RobotCameraFrame: new Set(),
    connection: new Set()
  };

  function emit(ev, payload) {
    handlers[ev]?.forEach((fn) => {
      try {
        fn(payload);
      } catch (err) {
        console.warn('RobotRealtime handler', ev, err);
      }
    });
  }

  async function start() {
    if (typeof signalR === 'undefined') return;
    if (connection?.state === signalR.HubConnectionState.Connected) return;
    if (startPromise) return startPromise;

    startPromise = (async () => {
      connection = new signalR.HubConnectionBuilder()
        .withUrl(`${CONFIG.API_BASE}/hubs/robot`)
        .withAutomaticReconnect([0, 2000, 5000, 10000, 30000])
        .build();

      connection.on('RobotStatusUpdate', (p) => emit('RobotStatusUpdate', p));
      connection.on('RobotHeartbeat', (p) => emit('RobotHeartbeat', p));
      connection.on('RobotCodeUploaded', (p) => emit('RobotCodeUploaded', p));
      connection.on('DeployResult', (p) => emit('DeployResult', p));
      connection.on('RobotCameraFrame', (p) => emit('RobotCameraFrame', p));

      connection.onreconnected(() => emit('connection', { state: 'reconnected' }));
      connection.onclose(() => emit('connection', { state: 'closed' }));

      try {
        await connection.start();
        emit('connection', { state: 'connected' });
      } catch (e) {
        console.warn('SignalR start failed', e);
        emit('connection', { state: 'error', error: e });
        connection = null;
      }
    })();

    try {
      await startPromise;
    } finally {
      startPromise = null;
    }
  }

  async function stop() {
    if (!connection) return;
    try {
      await connection.stop();
    } catch (_) {
      /* ignore */
    }
    connection = null;
    emit('connection', { state: 'stopped' });
  }

  function on(event, fn) {
    if (!handlers[event]) handlers[event] = new Set();
    handlers[event].add(fn);
    return () => handlers[event].delete(fn);
  }

  function isConnected() {
    return typeof signalR !== 'undefined' && connection?.state === signalR.HubConnectionState.Connected;
  }

  return { start, stop, on, isConnected };
})();

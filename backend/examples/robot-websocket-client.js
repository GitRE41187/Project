const socketIo = require('socket.io-client');

// Robot car WebSocket client example
const createRobotClient = (carId, name, ip, port, serverUrl = 'http://localhost:5000') => {
  console.log(`🤖 Creating robot client: ${name} (${carId})`);
  
  const socket = socketIo(serverUrl, {
    transports: ['websocket'],
    timeout: 5000
  });

  let heartbeatInterval;
  let reconnectAttempts = 0;
  const MAX_RECONNECT_ATTEMPTS = 5;

  // Connection event handlers
  socket.on('connect', () => {
    console.log(`✅ Robot ${carId} connected to server`);
    reconnectAttempts = 0;
    
    // Register robot with server
    socket.emit('robot-connect', {
      carId,
      name,
      ip,
      port
    });
    
    // Start heartbeat
    startHeartbeat();
  });

  socket.on('disconnect', () => {
    console.log(`❌ Robot ${carId} disconnected from server`);
    stopHeartbeat();
  });

  socket.on('connect_error', (error) => {
    console.error(`❌ Robot ${carId} connection error:`, error.message);
    reconnectAttempts++;
    
    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      console.error(`❌ Max reconnection attempts reached for robot ${carId}`);
      process.exit(1);
    }
  });

  // Robot-specific event handlers
  socket.on('robot-command', (data) => {
    console.log(`📨 Robot ${carId} received command:`, data);
    // Handle robot commands here
  });

  socket.on('robot-status-update', (data) => {
    console.log(`📊 Robot ${carId} status update:`, data);
  });

  // Heartbeat functions
  const startHeartbeat = () => {
    heartbeatInterval = setInterval(() => {
      const heartbeatData = {
        carId,
        status: 'idle', // idle, in_use, error
        battery: Math.floor(Math.random() * 100), // Simulate battery level
        position: { x: 0, y: 0 }, // Simulate position
        timestamp: new Date().toISOString()
      };
      
      socket.emit('robot-heartbeat', heartbeatData);
      console.log(`💓 Robot ${carId} heartbeat sent`);
    }, 30000); // Send heartbeat every 30 seconds
  };

  const stopHeartbeat = () => {
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval);
      heartbeatInterval = null;
    }
  };

  // Robot control functions
  const sendStatus = (status, battery, position) => {
    socket.emit('robot-heartbeat', {
      carId,
      status,
      battery,
      position,
      timestamp: new Date().toISOString()
    });
  };

  const disconnect = () => {
    console.log(`🔌 Robot ${carId} disconnecting...`);
    socket.emit('robot-disconnect', { carId });
    stopHeartbeat();
    socket.disconnect();
  };

  // Graceful shutdown
  process.on('SIGINT', () => {
    console.log(`\n🛑 Shutting down robot ${carId}...`);
    disconnect();
    process.exit(0);
  });

  return {
    socket,
    sendStatus,
    disconnect,
    isConnected: () => socket.connected
  };
};

// Example usage
const main = () => {
  console.log('🚀 Starting Robot Car WebSocket Clients\n');
  
  // Create multiple robot car clients
  const robots = [
    { carId: 'robot-001', name: 'Alpha Bot', ip: '192.168.1.100', port: 5001 },
    { carId: 'robot-002', name: 'Beta Bot', ip: '192.168.1.101', port: 5001 },
    { carId: 'robot-003', name: 'Gamma Bot', ip: '192.168.1.102', port: 5001 },
    { carId: 'robot-004', name: 'Delta Bot', ip: '192.168.1.103', port: 5001 }
  ];

  const robotClients = robots.map(robot => 
    createRobotClient(robot.carId, robot.name, robot.ip, robot.port)
  );

  // Monitor connections
  setInterval(() => {
    console.log('\n📊 Robot Status:');
    robotClients.forEach((client, index) => {
      const robot = robots[index];
      console.log(`  ${robot.name} (${robot.carId}): ${client.isConnected() ? '🟢 Connected' : '🔴 Disconnected'}`);
    });
  }, 60000); // Check every minute

  console.log('🤖 All robot clients started. Press Ctrl+C to stop.');
};

// Run the example
if (require.main === module) {
  main();
}

module.exports = { createRobotClient };

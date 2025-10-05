const axios = require('axios');

// Example script to register robot cars with the backend
const registerRobotCar = async (carId, name, ip, port) => {
  try {
    const response = await axios.post('http://localhost:5000/api/robots/register', {
      carId,
      name,
      ip,
      port
    });
    
    console.log(`✅ Robot car "${name}" registered successfully:`, response.data);
    return response.data;
  } catch (error) {
    console.error(`❌ Failed to register robot car "${name}":`, error.response?.data || error.message);
    return null;
  }
};

// Send heartbeat to keep robot car online
const sendHeartbeat = async (carId) => {
  try {
    await axios.post('http://localhost:5000/api/robots/heartbeat', {
      carId
    });
    console.log(`💓 Heartbeat sent for robot car: ${carId}`);
  } catch (error) {
    console.error(`❌ Failed to send heartbeat for ${carId}:`, error.message);
  }
};

// Example usage
const main = async () => {
  console.log('🤖 Robot Car Registration Example\n');
  
  // Register multiple robot cars
  const robotCars = [
    { carId: 'robot-001', name: 'Alpha Bot', ip: '192.168.1.100', port: 5001 },
    { carId: 'robot-002', name: 'Beta Bot', ip: '192.168.1.101', port: 5001 },
    { carId: 'robot-003', name: 'Gamma Bot', ip: '192.168.1.102', port: 5001 },
    { carId: 'robot-004', name: 'Delta Bot', ip: '192.168.1.103', port: 5001 }
  ];

  // Register all robot cars
  for (const car of robotCars) {
    await registerRobotCar(car.carId, car.name, car.ip, car.port);
    await new Promise(resolve => setTimeout(resolve, 1000)); // Wait 1 second between registrations
  }

  console.log('\n📡 Setting up heartbeat for all robot cars...');
  
  // Send heartbeats every 30 seconds
  const heartbeatInterval = setInterval(async () => {
    for (const car of robotCars) {
      await sendHeartbeat(car.carId);
    }
    console.log('--- Heartbeat cycle completed ---\n');
  }, 30000);

  // Keep the script running
  console.log('🔄 Heartbeat service started. Press Ctrl+C to stop.');
  
  process.on('SIGINT', () => {
    console.log('\n🛑 Stopping heartbeat service...');
    clearInterval(heartbeatInterval);
    process.exit(0);
  });
};

// Run the example
main().catch(console.error);


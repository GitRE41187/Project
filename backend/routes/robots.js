const express = require('express');
const pool = require('../config/database');
const { authenticateToken } = require('../middleware/auth');
const axios = require('axios');

const router = express.Router();

// In-memory storage for robot cars (in production, use Redis or database)
const robotCars = new Map(); // carId -> { id, name, ip, port, status, lastSeen, user, socketId }
const robotConnections = new Map(); // socketId -> { carId, robotInfo }

// Register a new robot car (now handled by WebSocket connection)
router.post('/register', async (req, res) => {
  try {
    const { carId, name, ip, port } = req.body;

    if (!carId || !name || !ip || !port) {
      return res.status(400).json({ error: 'carId, name, ip, and port are required' });
    }

    // Check if robot is already connected via WebSocket
    const existingRobot = robotCars.get(carId);
    if (existingRobot && existingRobot.socketId) {
      return res.status(409).json({ 
        error: 'Robot car is already connected via WebSocket',
        message: 'Use WebSocket connection instead of HTTP registration'
      });
    }

    const robotCar = {
      id: carId,
      name: name,
      ip: ip,
      port: port,
      status: 'available', // available, in_use, offline
      lastSeen: new Date(),
      user: null,
      socketId: null
    };

    robotCars.set(carId, robotCar);

    // Log robot registration
    await pool.execute(
      'INSERT INTO ROBOT_CARS (car_id, name, ip, port, status, last_seen) VALUES (?, ?, ?, ?, ?, ?) ON DUPLICATE KEY UPDATE name=VALUES(name), ip=VALUES(ip), port=VALUES(port), status=VALUES(status), last_seen=VALUES(last_seen)',
      [carId, name, ip, port, 'available', new Date()]
    );

    res.json({
      message: 'Robot car registered successfully (HTTP fallback)',
      car: robotCar,
      note: 'For real-time connection, use WebSocket connection to /socket.io/'
    });
  } catch (error) {
    console.error('Register robot error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Get all available robot cars
router.get('/available', authenticateToken, async (req, res) => {
  try {
    const availableStatuses = new Set(['available', 'idle']); // treat 'idle' as selectable/available
    const availableCars = Array.from(robotCars.values())
      .filter(car => availableStatuses.has(car.status) && car.socketId) // Only show connected robots
      .map(car => ({
        id: car.id,
        name: car.name,
        ip: car.ip,
        port: car.port,
        lastSeen: car.lastSeen,
        status: car.status, // expose current live status (available/idle/in_use/offline)
        isConnected: !!car.socketId,
        connectionType: car.socketId ? 'websocket' : 'http'
      }));

    res.json({
      availableCars,
      total: availableCars.length,
      connectedRobots: Array.from(robotCars.values()).filter(car => car.socketId).length
    });
  } catch (error) {
    console.error('Get available robots error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Get all robot cars (for admin)
router.get('/all', authenticateToken, async (req, res) => {
  try {
    // Check if user is admin (you might want to add admin middleware)
    const userId = req.user.id;
    
    const allCars = Array.from(robotCars.values()).map(car => ({
      id: car.id,
      name: car.name,
      ip: car.ip,
      port: car.port,
      status: car.status,
      lastSeen: car.lastSeen,
      currentUser: car.user,
      isConnected: !!car.socketId,
      connectionType: car.socketId ? 'websocket' : 'http'
    }));

    res.json({
      robotCars: allCars,
      total: allCars.length,
      connectedCount: allCars.filter(car => car.isConnected).length,
      disconnectedCount: allCars.filter(car => !car.isConnected).length
    });
  } catch (error) {
    console.error('Get all robots error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Select a robot car
router.post('/select', authenticateToken, async (req, res) => {
  try {
    const userId = req.user.id;
    const { carId } = req.body;

    if (!carId) {
      return res.status(400).json({ error: 'carId is required' });
    }

    const robotCar = robotCars.get(carId);
    if (!robotCar) {
      return res.status(404).json({ error: 'Robot car not found' });
    }

    if (robotCar.status !== 'available') {
      return res.status(409).json({ error: 'Robot car is not available' });
    }

    // Check if user has active booking
    const [bookings] = await pool.execute(`
      SELECT id, start_time, end_time, status 
      FROM BOOKINGS 
      WHERE user_id = ? AND status = 'active' AND start_time <= NOW() AND end_time > NOW()
    `, [userId]);

    if (bookings.length === 0) {
      return res.status(403).json({ error: 'No active booking found' });
    }

    // Reserve the robot car
    robotCar.status = 'in_use';
    robotCar.user = userId;
    robotCars.set(carId, robotCar);

    // Update database
    await pool.execute(
      'UPDATE ROBOT_CARS SET status = ?, current_user = ? WHERE car_id = ?',
      ['in_use', userId, carId]
    );

    res.json({
      message: 'Robot car selected successfully',
      selectedCar: {
        id: robotCar.id,
        name: robotCar.name,
        ip: robotCar.ip,
        port: robotCar.port
      }
    });
  } catch (error) {
    console.error('Select robot error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Release a robot car
router.post('/release', authenticateToken, async (req, res) => {
  try {
    const userId = req.user.id;
    const { carId } = req.body;

    if (!carId) {
      return res.status(400).json({ error: 'carId is required' });
    }

    const robotCar = robotCars.get(carId);
    if (!robotCar) {
      return res.status(404).json({ error: 'Robot car not found' });
    }

    if (robotCar.user !== userId) {
      return res.status(403).json({ error: 'You can only release your own robot car' });
    }

    // Release the robot car
    robotCar.status = 'available';
    robotCar.user = null;
    robotCars.set(carId, robotCar);

    // Update database
    await pool.execute(
      'UPDATE ROBOT_CARS SET status = ?, current_user = NULL WHERE car_id = ?',
      ['available', carId]
    );

    res.json({
      message: 'Robot car released successfully'
    });
  } catch (error) {
    console.error('Release robot error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Get user's selected robot car
router.get('/my-car', authenticateToken, async (req, res) => {
  try {
    const userId = req.user.id;

    const userCar = Array.from(robotCars.values())
      .find(car => car.user === userId && car.status === 'in_use');

    if (!userCar) {
      return res.json({ hasSelectedCar: false });
    }

    res.json({
      hasSelectedCar: true,
      selectedCar: {
        id: userCar.id,
        name: userCar.name,
        ip: userCar.ip,
        port: userCar.port
      }
    });
  } catch (error) {
    console.error('Get my car error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Heartbeat from robot car
router.post('/heartbeat', async (req, res) => {
  try {
    const { carId } = req.body;

    if (!carId) {
      return res.status(400).json({ error: 'carId is required' });
    }

    const robotCar = robotCars.get(carId);
    if (robotCar) {
      robotCar.lastSeen = new Date();
      
      // Update last seen in database
      await pool.execute(
        'UPDATE ROBOT_CARS SET last_seen = ? WHERE car_id = ?',
        [new Date(), carId]
      );
    }

    res.json({ message: 'Heartbeat received' });
  } catch (error) {
    console.error('Heartbeat error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Clean up offline robots (should be called periodically)
router.post('/cleanup', async (req, res) => {
  try {
    const now = new Date();
    const OFFLINE_TIMEOUT = 5 * 60 * 1000; // 5 minutes

    let cleanedCount = 0;
    for (const [carId, car] of robotCars.entries()) {
      if (now - car.lastSeen > OFFLINE_TIMEOUT && car.status !== 'in_use') {
        car.status = 'offline';
        robotCars.set(carId, car);
        cleanedCount++;
      }
    }

    // Update database
    await pool.execute(
      'UPDATE ROBOT_CARS SET status = ? WHERE last_seen < ? AND status != "in_use"',
      ['offline', new Date(Date.now() - OFFLINE_TIMEOUT)]
    );

    res.json({
      message: 'Cleanup completed',
      cleanedCount
    });
  } catch (error) {
    console.error('Cleanup error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// WebSocket connection management functions
const registerRobotConnection = (socketId, carId, robotInfo) => {
  const robotCar = robotCars.get(carId) || {
    id: carId,
    name: robotInfo.name,
    ip: robotInfo.ip,
    port: robotInfo.port,
    status: 'available',
    lastSeen: new Date(),
    user: null,
    socketId: null
  };

  robotCar.socketId = socketId;
  robotCar.lastSeen = new Date();
  robotCar.status = 'available';
  
  robotCars.set(carId, robotCar);
  robotConnections.set(socketId, { carId, robotInfo });
  
  return robotCar;
};

const unregisterRobotConnection = (socketId) => {
  const connection = robotConnections.get(socketId);
  if (connection) {
    const { carId } = connection;
    const robotCar = robotCars.get(carId);
    if (robotCar) {
      robotCar.socketId = null;
      robotCar.status = 'offline';
      robotCar.lastSeen = new Date();
      robotCars.set(carId, robotCar);
    }
    robotConnections.delete(socketId);
    return carId;
  }
  return null;
};

const updateRobotHeartbeat = (carId, status, battery, position) => {
  const robotCar = robotCars.get(carId);
  if (robotCar) {
    robotCar.lastSeen = new Date();
    robotCar.status = status || robotCar.status;
    robotCar.battery = battery;
    robotCar.position = position;
    robotCars.set(carId, robotCar);
    return robotCar;
  }
  return null;
};

const getRobotBySocketId = (socketId) => {
  const connection = robotConnections.get(socketId);
  return connection ? robotCars.get(connection.carId) : null;
};

// Export robotCars and connection management functions for use in other modules
module.exports = { 
  router, 
  robotCars, 
  robotConnections,
  registerRobotConnection,
  unregisterRobotConnection,
  updateRobotHeartbeat,
  getRobotBySocketId
};

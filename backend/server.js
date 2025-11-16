const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const http = require('http');
const socketIo = require('socket.io');
require('dotenv').config();

const authRoutes = require('./routes/auth');
const queueRoutes = require('./routes/queue');
const controlRoutes = require('./routes/control');
const uploadRoutes = require('./routes/uploads');
const logRoutes = require('./routes/logs');
const { 
  router: robotRoutes, 
  registerRobotConnection, 
  unregisterRobotConnection, 
  updateRobotHeartbeat 
} = require('./routes/robots');

const app = express();
const server = http.createServer(app);
const io = socketIo(server, {
  cors: {
    origin: process.env.CLIENT_URL || "http://localhost:3000",
    methods: ["GET", "POST"]
  }
});

// Middleware
app.use(helmet());
app.use(cors({
  origin: process.env.CLIENT_URL || "http://localhost:3000",
  credentials: true
}));
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// Trust proxy for rate limiting
app.set('trust proxy', 1);

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each IP to 100 requests per windowMs
  message: 'Too many requests from this IP, please try again later.',
  standardHeaders: true,
  legacyHeaders: false
});
app.use('/api/', limiter);

// Routes
app.use('/api/auth', authRoutes);
app.use('/api/queue', queueRoutes);
app.use('/api/control', controlRoutes);
app.use('/api/uploads', uploadRoutes);
app.use('/api/logs', logRoutes);
app.use('/api/robots', robotRoutes);

// Health check
app.get('/api/health', (req, res) => {
  res.json({ 
    status: 'OK', 
    timestamp: new Date().toISOString(),
    uptime: process.uptime()
  });
});

// Socket.IO for real-time updates
io.on('connection', (socket) => {
  console.log('Client connected:', socket.id);


  // Robot car connection handling
  socket.on('robot-connect', (data) => {
    const { carId, name, ip, port } = data;
    console.log(`🤖 Robot car connected: ${name} (${carId}) from ${ip}:${port}`);

    // If this carId already has an active socket, disconnect the old one to avoid duplicates
    try {
      const { robotCars } = require('./routes/robots');
      const existing = robotCars.get(carId);
      if (existing && existing.socketId && existing.socketId !== socket.id) {
        const oldSocket = io.sockets.sockets.get(existing.socketId);
        if (oldSocket) {
          console.log(`🔁 Replacing existing connection for ${carId}. Disconnecting old socket ${existing.socketId}`);
          oldSocket.disconnect(true);
        }
      }
    } catch (e) {
      console.error('Error checking existing robot socket:', e);
    }

    // Register robot connection
    const robotInfo = { carId, name, ip, port };
    const robotCar = registerRobotConnection(socket.id, carId, robotInfo);
    
    // Store robot connection info in socket
    socket.carId = carId;
    socket.robotInfo = robotInfo;
    socket.join(`robot-${carId}`);
    
    // Notify all clients about robot connection
    io.emit('robot-status-update', {
      carId,
      name,
      ip,
      port,
      status: 'connected',
      timestamp: new Date().toISOString()
    });
    
    console.log(`✅ Robot ${carId} registered with socket ${socket.id}`);
  });

  socket.on('robot-heartbeat', (data) => {
    const { carId, status, battery, position } = data;
    console.log(`💓 Robot heartbeat: ${carId} - Status: ${status}`);
    
    // Update robot heartbeat in memory
    updateRobotHeartbeat(carId, status, battery, position);
    
    // Update robot status and notify clients
    io.emit('robot-heartbeat', {
      carId,
      status,
      battery,
      position,
      timestamp: new Date().toISOString()
    });
  });

  // Debug logs from robot
  socket.on('robot-debug', (payload) => {
    try {
      const { carId, event, data, timestamp } = payload || {};
      console.log(`🐞 [${timestamp || new Date().toISOString()}] ${carId} ${event}`, data || {});
      io.emit('robot-debug', payload);
    } catch (e) {
      console.error('robot-debug handling error:', e);
    }
  });

  // Status updates from robot (run/idle/etc.)
  socket.on('robot-status', (payload) => {
    try {
      const { carId, status, userId } = payload || {};
      console.log(`⚙️ Robot status: ${carId} -> ${status} (user: ${userId || '-'})`);
      io.emit('robot-status-update', {
        carId,
        status,
        userId: userId || null,
        timestamp: new Date().toISOString()
      });
    } catch (e) {
      console.error('robot-status handling error:', e);
    }
  });

  // Code uploaded to car via HTTP on the Pi
  socket.on('robot-code-uploaded', (payload) => {
    try {
      const { carId, userId, filename, original, size, timestamp } = payload || {};
      console.log(`📦 Code uploaded on car ${carId}: ${filename} (${original || '-'}; ${size || 0}B)`);
      io.emit('robot-code-uploaded', payload);
    } catch (e) {
      console.error('robot-code-uploaded handling error:', e);
    }
  });

  // Result after server-initiated deploy-code
  socket.on('deploy-result', (payload) => {
    try {
      const { carId, userId, success, message, filename } = payload || {};
      console.log(`🚚 Deploy result from ${carId}: ${success ? 'OK' : 'FAIL'} ${message || ''} (${filename || ''})`);
      io.emit('deploy-result', payload);
    } catch (e) {
      console.error('deploy-result handling error:', e);
    }
  });

  socket.on('robot-disconnect', (data) => {
    const { carId } = data;
    console.log(`🤖 Robot car disconnected: ${carId}`);
    
    // Unregister robot connection
    unregisterRobotConnection(socket.id);
    
    // Notify all clients about robot disconnection
    io.emit('robot-status-update', {
      carId,
      status: 'disconnected',
      timestamp: new Date().toISOString()
    });
  });

  socket.on('disconnect', () => {
    console.log('Client disconnected:', socket.id);
    
    // If this was a robot connection, handle disconnection
    if (socket.carId) {
      console.log(`🤖 Robot car disconnected: ${socket.carId}`);
      
      // Unregister robot connection
      const disconnectedCarId = unregisterRobotConnection(socket.id);
      
      // Notify all clients about robot disconnection
      io.emit('robot-status-update', {
        carId: disconnectedCarId || socket.carId,
        status: 'disconnected',
        timestamp: new Date().toISOString()
      });
    }
  });
});

// Make io available to routes
app.set('io', io);

// Error handling middleware
app.use((err, req, res, next) => {
  console.error('Error:', err);
  
  if (err.code === 'LIMIT_FILE_SIZE') {
    return res.status(400).json({ error: 'File too large' });
  }
  
  if (err.message === 'Only Python files (.py) are allowed') {
    return res.status(400).json({ error: err.message });
  }
  
  res.status(500).json({ 
    error: 'Internal server error',
    message: process.env.NODE_ENV === 'development' ? err.message : 'Something went wrong'
  });
});

// 404 handler
app.use('*', (req, res) => {
  res.status(404).json({ error: 'Route not found' });
});

const PORT = process.env.PORT || 5000;

server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
  console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM received, shutting down gracefully');
  server.close(() => {
    console.log('Process terminated');
  });
});

module.exports = { app, io };

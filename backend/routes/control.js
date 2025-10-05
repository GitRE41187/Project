const express = require('express');
const pool = require('../config/database');
const { authenticateToken } = require('../middleware/auth');
const axios = require('axios');

const router = express.Router();

// Check if user has active booking
const checkActiveBooking = async (userId) => {
  // First, auto-activate bookings that have started
  await pool.execute(`
    UPDATE BOOKINGS 
    SET status = 'active' 
    WHERE user_id = ? AND status = 'pending' AND start_time <= NOW() AND end_time > NOW()
  `, [userId]);

  // Then check for active booking
  const [bookings] = await pool.execute(`
    SELECT id, start_time, end_time, status 
    FROM BOOKINGS 
    WHERE user_id = ? AND status = 'active' AND start_time <= NOW() AND end_time > NOW()
  `, [userId]);

  return bookings.length > 0 ? bookings[0] : null;
};

// Get user's selected robot car
const getUserSelectedCar = async (userId) => {
  const { robotCars } = require('./robots');
  return Array.from(robotCars.values())
    .find(car => car.user === userId && car.status === 'in_use');
};

// Upload code to selected robot car
router.post('/upload', authenticateToken, async (req, res) => {
  try {
    const userId = req.user.id;
    const { filePath, originalFilename } = req.body;

    if (!filePath) {
      return res.status(400).json({ error: 'File path is required' });
    }

    // Check if user has active booking
    const activeBooking = await checkActiveBooking(userId);
    if (!activeBooking) {
      return res.status(403).json({ error: 'No active booking found' });
    }

    // Check if user has selected a robot car
    const selectedCar = await getUserSelectedCar(userId);
    if (!selectedCar) {
      return res.status(403).json({ error: 'No robot car selected. Please select a robot car first.' });
    }

    // Send file to selected robot car via server
    try {
      const robotUrl = `http://${selectedCar.ip}:${selectedCar.port}`;
      const response = await axios.post(`${robotUrl}/upload_code`, {
        user_id: userId,
        file_path: filePath,
        original_filename: originalFilename
      });

      // Log the upload
      await pool.execute(
        'INSERT INTO EXECUTION_LOGS (user_id, booking_id, action, details) VALUES (?, ?, ?, ?)',
        [userId, activeBooking.id, 'upload', `Code uploaded to ${selectedCar.name}: ${originalFilename}`]
      );

      res.json({
        message: 'Code uploaded successfully',
        robotCar: selectedCar.name,
        piResponse: response.data
      });
    } catch (piError) {
      console.error('Robot upload error:', piError.message);
      res.status(500).json({ error: `Failed to upload code to robot car ${selectedCar.name}` });
    }
  } catch (error) {
    console.error('Upload code error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Run code
router.post('/run', authenticateToken, async (req, res) => {
  try {
    const userId = req.user.id;

    // Check if user has active booking
    const activeBooking = await checkActiveBooking(userId);
    if (!activeBooking) {
      return res.status(403).json({ error: 'No active booking found' });
    }

    // Check if user has selected a robot car
    const selectedCar = await getUserSelectedCar(userId);
    if (!selectedCar) {
      return res.status(403).json({ error: 'No robot car selected. Please select a robot car first.' });
    }

    // Send run command to selected robot car
    try {
      const robotUrl = `http://${selectedCar.ip}:${selectedCar.port}`;
      const response = await axios.post(`${robotUrl}/run`, {
        user_id: userId
      });

      // Log the run command
      await pool.execute(
        'INSERT INTO EXECUTION_LOGS (user_id, booking_id, action, details) VALUES (?, ?, ?, ?)',
        [userId, activeBooking.id, 'run', `Code execution started on ${selectedCar.name}`]
      );

      res.json({
        message: 'Code execution started',
        robotCar: selectedCar.name,
        piResponse: response.data
      });
    } catch (piError) {
      console.error('Robot run error:', piError.message);
      res.status(500).json({ error: `Failed to run code on robot car ${selectedCar.name}` });
    }
  } catch (error) {
    console.error('Run code error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Stop code
router.post('/stop', authenticateToken, async (req, res) => {
  try {
    const userId = req.user.id;

    // Check if user has active booking
    const activeBooking = await checkActiveBooking(userId);
    if (!activeBooking) {
      return res.status(403).json({ error: 'No active booking found' });
    }

    // Check if user has selected a robot car
    const selectedCar = await getUserSelectedCar(userId);
    if (!selectedCar) {
      return res.status(403).json({ error: 'No robot car selected. Please select a robot car first.' });
    }

    // Send stop command to selected robot car
    try {
      const robotUrl = `http://${selectedCar.ip}:${selectedCar.port}`;
      const response = await axios.post(`${robotUrl}/stop`, {
        user_id: userId
      });

      // Log the stop command
      await pool.execute(
        'INSERT INTO EXECUTION_LOGS (user_id, booking_id, action, details) VALUES (?, ?, ?, ?)',
        [userId, activeBooking.id, 'stop', `Code execution stopped on ${selectedCar.name}`]
      );

      res.json({
        message: 'Code execution stopped',
        robotCar: selectedCar.name,
        piResponse: response.data
      });
    } catch (piError) {
      console.error('Robot stop error:', piError.message);
      res.status(500).json({ error: `Failed to stop code on robot car ${selectedCar.name}` });
    }
  } catch (error) {
    console.error('Stop code error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Reset field
router.post('/reset', authenticateToken, async (req, res) => {
  try {
    const userId = req.user.id;

    // Check if user has active booking
    const activeBooking = await checkActiveBooking(userId);
    if (!activeBooking) {
      return res.status(403).json({ error: 'No active booking found' });
    }

    // Check if user has selected a robot car
    const selectedCar = await getUserSelectedCar(userId);
    if (!selectedCar) {
      return res.status(403).json({ error: 'No robot car selected. Please select a robot car first.' });
    }

    // Send reset command to selected robot car
    try {
      const robotUrl = `http://${selectedCar.ip}:${selectedCar.port}`;
      const response = await axios.post(`${robotUrl}/reset`, {
        user_id: userId
      });

      // Log the reset command
      await pool.execute(
        'INSERT INTO EXECUTION_LOGS (user_id, booking_id, action, details) VALUES (?, ?, ?, ?)',
        [userId, activeBooking.id, 'reset', `Field reset to start position on ${selectedCar.name}`]
      );

      res.json({
        message: 'Field reset successfully',
        robotCar: selectedCar.name,
        piResponse: response.data
      });
    } catch (piError) {
      console.error('Robot reset error:', piError.message);
      res.status(500).json({ error: `Failed to reset field on robot car ${selectedCar.name}` });
    }
  } catch (error) {
    console.error('Reset field error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Get execution status
router.get('/status', authenticateToken, async (req, res) => {
  try {
    const userId = req.user.id;

    // Check if user has active booking
    const activeBooking = await checkActiveBooking(userId);
    if (!activeBooking) {
      return res.json({ hasActiveBooking: false });
    }

    // Check if user has selected a robot car
    const selectedCar = await getUserSelectedCar(userId);
    if (!selectedCar) {
      return res.json({
        hasActiveBooking: true,
        booking: activeBooking,
        hasSelectedCar: false,
        executionStatus: { error: 'No robot car selected' }
      });
    }

    // Get status from selected robot car
    try {
      const robotUrl = `http://${selectedCar.ip}:${selectedCar.port}`;
      const response = await axios.get(`${robotUrl}/status/${userId}`);
      
      res.json({
        hasActiveBooking: true,
        booking: activeBooking,
        hasSelectedCar: true,
        selectedCar: {
          id: selectedCar.id,
          name: selectedCar.name
        },
        executionStatus: response.data
      });
    } catch (piError) {
      console.error('Robot status error:', piError.message);
      res.json({
        hasActiveBooking: true,
        booking: activeBooking,
        hasSelectedCar: true,
        selectedCar: {
          id: selectedCar.id,
          name: selectedCar.name
        },
        executionStatus: { error: `Unable to get execution status from ${selectedCar.name}` }
      });
    }
  } catch (error) {
    console.error('Get status error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Camera endpoints
// Start camera
router.post('/camera/start', authenticateToken, async (req, res) => {
  try {
    const userId = req.user.id;

    // Check if user has active booking
    const activeBooking = await checkActiveBooking(userId);
    if (!activeBooking) {
      return res.status(403).json({ error: 'No active booking found' });
    }

    // Check if user has selected a robot car
    const selectedCar = await getUserSelectedCar(userId);
    if (!selectedCar) {
      return res.status(403).json({ error: 'No robot car selected. Please select a robot car first.' });
    }

    // Send start camera command to selected robot car
    try {
      const robotUrl = `http://${selectedCar.ip}:${selectedCar.port}`;
      const response = await axios.post(`${robotUrl}/camera/start`, {
        user_id: userId
      });

      // Log the camera start
      await pool.execute(
        'INSERT INTO EXECUTION_LOGS (user_id, booking_id, action, details) VALUES (?, ?, ?, ?)',
        [userId, activeBooking.id, 'camera_start', `Camera streaming started on ${selectedCar.name}`]
      );

      res.json({
        message: 'Camera started successfully',
        robotCar: selectedCar.name,
        cameraStreamUrl: `${robotUrl}/camera/stream`,
        piResponse: response.data
      });
    } catch (piError) {
      console.error('Robot camera start error:', piError.message);
      res.status(500).json({ error: `Failed to start camera on robot car ${selectedCar.name}` });
    }
  } catch (error) {
    console.error('Start camera error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Stop camera
router.post('/camera/stop', authenticateToken, async (req, res) => {
  try {
    const userId = req.user.id;

    // Check if user has active booking
    const activeBooking = await checkActiveBooking(userId);
    if (!activeBooking) {
      return res.status(403).json({ error: 'No active booking found' });
    }

    // Check if user has selected a robot car
    const selectedCar = await getUserSelectedCar(userId);
    if (!selectedCar) {
      return res.status(403).json({ error: 'No robot car selected. Please select a robot car first.' });
    }

    // Send stop camera command to selected robot car
    try {
      const robotUrl = `http://${selectedCar.ip}:${selectedCar.port}`;
      const response = await axios.post(`${robotUrl}/camera/stop`, {
        user_id: userId
      });

      // Log the camera stop
      await pool.execute(
        'INSERT INTO EXECUTION_LOGS (user_id, booking_id, action, details) VALUES (?, ?, ?, ?)',
        [userId, activeBooking.id, 'camera_stop', `Camera streaming stopped on ${selectedCar.name}`]
      );

      res.json({
        message: 'Camera stopped successfully',
        robotCar: selectedCar.name,
        piResponse: response.data
      });
    } catch (piError) {
      console.error('Robot camera stop error:', piError.message);
      res.status(500).json({ error: `Failed to stop camera on robot car ${selectedCar.name}` });
    }
  } catch (error) {
    console.error('Stop camera error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Get camera status
router.get('/camera/status', authenticateToken, async (req, res) => {
  try {
    const userId = req.user.id;

    // Check if user has active booking
    const activeBooking = await checkActiveBooking(userId);
    if (!activeBooking) {
      return res.json({ hasActiveBooking: false });
    }

    // Check if user has selected a robot car
    const selectedCar = await getUserSelectedCar(userId);
    if (!selectedCar) {
      return res.json({
        hasActiveBooking: true,
        booking: activeBooking,
        hasSelectedCar: false,
        cameraStatus: { error: 'No robot car selected' }
      });
    }

    // Get camera status from selected robot car
    try {
      const robotUrl = `http://${selectedCar.ip}:${selectedCar.port}`;
      const response = await axios.get(`${robotUrl}/camera/status`);
      
      res.json({
        hasActiveBooking: true,
        booking: activeBooking,
        hasSelectedCar: true,
        selectedCar: {
          id: selectedCar.id,
          name: selectedCar.name
        },
        cameraStatus: response.data,
        cameraStreamUrl: response.data.camera_active ? `${robotUrl}/camera/stream` : null
      });
    } catch (piError) {
      console.error('Robot camera status error:', piError.message);
      res.json({
        hasActiveBooking: true,
        booking: activeBooking,
        hasSelectedCar: true,
        selectedCar: {
          id: selectedCar.id,
          name: selectedCar.name
        },
        cameraStatus: { error: `Unable to get camera status from ${selectedCar.name}` }
      });
    }
  } catch (error) {
    console.error('Get camera status error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Manual check-in for booking
router.post('/checkin', authenticateToken, async (req, res) => {
  try {
    const userId = req.user.id;

    // Find pending booking that should be active
    const [bookings] = await pool.execute(`
      SELECT id, start_time, end_time, status 
      FROM BOOKINGS 
      WHERE user_id = ? AND status = 'pending' AND start_time <= NOW() AND end_time > NOW()
      ORDER BY start_time DESC
      LIMIT 1
    `, [userId]);

    if (bookings.length === 0) {
      return res.status(404).json({ 
        error: 'No pending booking found for current time slot' 
      });
    }

    const booking = bookings[0];

    // Activate the booking
    await pool.execute(`
      UPDATE BOOKINGS 
      SET status = 'active' 
      WHERE id = ?
    `, [booking.id]);

    // Log the check-in
    await pool.execute(
      'INSERT INTO EXECUTION_LOGS (user_id, booking_id, action, details) VALUES (?, ?, ?, ?)',
      [userId, booking.id, 'upload', `Manual check-in at ${new Date().toISOString()}`]
    );

    res.json({
      message: 'Successfully checked in',
      booking: {
        id: booking.id,
        start_time: booking.start_time,
        end_time: booking.end_time,
        status: 'active'
      }
    });
  } catch (error) {
    console.error('Check-in error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

module.exports = router;

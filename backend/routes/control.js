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

// Upload code to Raspberry Pi
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

    // Send file to Raspberry Pi
    try {
      const response = await axios.post(`${process.env.PI_BASE_URL}/upload_code`, {
        user_id: userId,
        file_path: filePath,
        original_filename: originalFilename
      });

      // Log the upload
      await pool.execute(
        'INSERT INTO EXECUTION_LOGS (user_id, booking_id, action, details) VALUES (?, ?, ?, ?)',
        [userId, activeBooking.id, 'upload', `Code uploaded: ${originalFilename}`]
      );

      res.json({
        message: 'Code uploaded successfully',
        piResponse: response.data
      });
    } catch (piError) {
      console.error('Pi upload error:', piError.message);
      res.status(500).json({ error: 'Failed to upload code to Raspberry Pi' });
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

    // Send run command to Raspberry Pi
    try {
      const response = await axios.post(`${process.env.PI_BASE_URL}/run`, {
        user_id: userId
      });

      // Log the run command
      await pool.execute(
        'INSERT INTO EXECUTION_LOGS (user_id, booking_id, action, details) VALUES (?, ?, ?, ?)',
        [userId, activeBooking.id, 'run', 'Code execution started']
      );

      res.json({
        message: 'Code execution started',
        piResponse: response.data
      });
    } catch (piError) {
      console.error('Pi run error:', piError.message);
      res.status(500).json({ error: 'Failed to run code on Raspberry Pi' });
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

    // Send stop command to Raspberry Pi
    try {
      const response = await axios.post(`${process.env.PI_BASE_URL}/stop`, {
        user_id: userId
      });

      // Log the stop command
      await pool.execute(
        'INSERT INTO EXECUTION_LOGS (user_id, booking_id, action, details) VALUES (?, ?, ?, ?)',
        [userId, activeBooking.id, 'stop', 'Code execution stopped']
      );

      res.json({
        message: 'Code execution stopped',
        piResponse: response.data
      });
    } catch (piError) {
      console.error('Pi stop error:', piError.message);
      res.status(500).json({ error: 'Failed to stop code on Raspberry Pi' });
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

    // Send reset command to Raspberry Pi
    try {
      const response = await axios.post(`${process.env.PI_BASE_URL}/reset`, {
        user_id: userId
      });

      // Log the reset command
      await pool.execute(
        'INSERT INTO EXECUTION_LOGS (user_id, booking_id, action, details) VALUES (?, ?, ?, ?)',
        [userId, activeBooking.id, 'reset', 'Field reset to start position']
      );

      res.json({
        message: 'Field reset successfully',
        piResponse: response.data
      });
    } catch (piError) {
      console.error('Pi reset error:', piError.message);
      res.status(500).json({ error: 'Failed to reset field on Raspberry Pi' });
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

    // Get status from Raspberry Pi
    try {
      const response = await axios.get(`${process.env.PI_BASE_URL}/status/${userId}`);
      
      res.json({
        hasActiveBooking: true,
        booking: activeBooking,
        executionStatus: response.data
      });
    } catch (piError) {
      console.error('Pi status error:', piError.message);
      res.json({
        hasActiveBooking: true,
        booking: activeBooking,
        executionStatus: { error: 'Unable to get execution status' }
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

    // Send start camera command to Raspberry Pi
    try {
      const response = await axios.post(`${process.env.PI_BASE_URL}/camera/start`, {
        user_id: userId
      });

      // Log the camera start
      await pool.execute(
        'INSERT INTO EXECUTION_LOGS (user_id, booking_id, action, details) VALUES (?, ?, ?, ?)',
        [userId, activeBooking.id, 'camera_start', 'Camera streaming started']
      );

      res.json({
        message: 'Camera started successfully',
        piResponse: response.data
      });
    } catch (piError) {
      console.error('Pi camera start error:', piError.message);
      res.status(500).json({ error: 'Failed to start camera on Raspberry Pi' });
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

    // Send stop camera command to Raspberry Pi
    try {
      const response = await axios.post(`${process.env.PI_BASE_URL}/camera/stop`, {
        user_id: userId
      });

      // Log the camera stop
      await pool.execute(
        'INSERT INTO EXECUTION_LOGS (user_id, booking_id, action, details) VALUES (?, ?, ?, ?)',
        [userId, activeBooking.id, 'camera_stop', 'Camera streaming stopped']
      );

      res.json({
        message: 'Camera stopped successfully',
        piResponse: response.data
      });
    } catch (piError) {
      console.error('Pi camera stop error:', piError.message);
      res.status(500).json({ error: 'Failed to stop camera on Raspberry Pi' });
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

    // Get camera status from Raspberry Pi
    try {
      const response = await axios.get(`${process.env.PI_BASE_URL}/camera/status`);
      
      res.json({
        hasActiveBooking: true,
        booking: activeBooking,
        cameraStatus: response.data
      });
    } catch (piError) {
      console.error('Pi camera status error:', piError.message);
      res.json({
        hasActiveBooking: true,
        booking: activeBooking,
        cameraStatus: { error: 'Unable to get camera status' }
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

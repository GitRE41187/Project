const express = require('express');
const pool = require('../config/database');
const { authenticateToken, requireAdmin } = require('../middleware/auth');
const axios = require('axios');

const router = express.Router();

// Get current queue
router.get('/', async (req, res) => {
  try {
    const [bookings] = await pool.execute(`
      SELECT 
        b.id,
        b.user_id,
        b.field_id,
        b.start_time,
        b.end_time,
        b.status,
        b.created_at,
        u.username
      FROM BOOKINGS b
      JOIN USERS u ON b.user_id = u.id
      WHERE b.status IN ('pending', 'active')
      ORDER BY b.start_time ASC
    `);

    res.json({ queue: bookings });
  } catch (error) {
    console.error('Get queue error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Book a slot
router.post('/book', authenticateToken, async (req, res) => {
  try {
    const { startTime, endTime, fieldId = 1 } = req.body;
    const userId = req.user.id;

    if (!startTime || !endTime) {
      return res.status(400).json({ error: 'Start time and end time are required' });
    }

    const start = new Date(startTime);
    const end = new Date(endTime);

    if (start >= end) {
      return res.status(400).json({ error: 'End time must be after start time' });
    }

    if (start < new Date()) {
      return res.status(400).json({ error: 'Cannot book in the past' });
    }

    // Check for conflicts
    const [conflicts] = await pool.execute(`
      SELECT id FROM BOOKINGS 
      WHERE field_id = ? 
      AND status IN ('pending', 'active')
      AND (
        (start_time <= ? AND end_time > ?) OR
        (start_time < ? AND end_time >= ?) OR
        (start_time >= ? AND end_time <= ?)
      )
    `, [fieldId, start, start, end, end, start, end]);

    if (conflicts.length > 0) {
      return res.status(400).json({ error: 'Time slot conflicts with existing booking' });
    }

    // Create booking
    const [result] = await pool.execute(
      'INSERT INTO BOOKINGS (user_id, field_id, start_time, end_time) VALUES (?, ?, ?, ?)',
      [userId, fieldId, start, end]
    );

    // Log the booking
    await pool.execute(
      'INSERT INTO EXECUTION_LOGS (user_id, booking_id, action, details) VALUES (?, ?, ?, ?)',
      [userId, result.insertId, 'upload', `Booked slot from ${start} to ${end}`]
    );

    res.status(201).json({
      message: 'Slot booked successfully',
      bookingId: result.insertId
    });
  } catch (error) {
    console.error('Book slot error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Cancel booking
router.delete('/cancel/:bookingId', authenticateToken, async (req, res) => {
  try {
    const { bookingId } = req.params;
    const userId = req.user.id;

    // Check if booking exists and belongs to user
    const [bookings] = await pool.execute(
      'SELECT id, status FROM BOOKINGS WHERE id = ? AND user_id = ?',
      [bookingId, userId]
    );

    if (bookings.length === 0) {
      return res.status(404).json({ error: 'Booking not found' });
    }

    const booking = bookings[0];

    if (booking.status === 'done') {
      return res.status(400).json({ error: 'Cannot cancel completed booking' });
    }

    if (booking.status === 'active') {
      // If currently active, stop any running code
      try {
        await axios.post(`${process.env.PI_BASE_URL}/stop`, {
          user_id: userId
        });
      } catch (piError) {
        console.error('Error stopping code on Pi:', piError.message);
      }
    }

    // Update booking status
    await pool.execute(
      'UPDATE BOOKINGS SET status = ? WHERE id = ?',
      ['cancelled', bookingId]
    );

    // Log the cancellation
    await pool.execute(
      'INSERT INTO EXECUTION_LOGS (user_id, booking_id, action, details) VALUES (?, ?, ?, ?)',
      [userId, bookingId, 'stop', 'Booking cancelled by user']
    );

    res.json({ message: 'Booking cancelled successfully' });
  } catch (error) {
    console.error('Cancel booking error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Get user's bookings
router.get('/my-bookings', authenticateToken, async (req, res) => {
  try {
    const userId = req.user.id;

    const [bookings] = await pool.execute(`
      SELECT 
        b.id,
        b.field_id,
        b.start_time,
        b.end_time,
        b.status,
        b.created_at,
        f.name as field_name
      FROM BOOKINGS b
      LEFT JOIN FIELDS f ON b.field_id = f.id
      WHERE b.user_id = ?
      ORDER BY b.created_at DESC
    `, [userId]);

    res.json({ bookings });
  } catch (error) {
    console.error('Get user bookings error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Admin: Get all bookings
router.get('/admin/all', authenticateToken, requireAdmin, async (req, res) => {
  try {
    const [bookings] = await pool.execute(`
      SELECT 
        b.id,
        b.user_id,
        b.field_id,
        b.start_time,
        b.end_time,
        b.status,
        b.created_at,
        u.username,
        f.name as field_name
      FROM BOOKINGS b
      JOIN USERS u ON b.user_id = u.id
      LEFT JOIN FIELDS f ON b.field_id = f.id
      ORDER BY b.created_at DESC
    `);

    res.json({ bookings });
  } catch (error) {
    console.error('Get all bookings error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

module.exports = router;

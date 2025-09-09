const express = require('express');
const pool = require('../config/database');
const { authenticateToken, requireAdmin } = require('../middleware/auth');

const router = express.Router();

// Get user's execution logs
router.get('/my-logs', authenticateToken, async (req, res) => {
  try {
    const userId = req.user.id;
    const { limit = 50, offset = 0 } = req.query;

    const [logs] = await pool.execute(`
      SELECT 
        el.id,
        el.action,
        el.details,
        el.executed_at,
        b.start_time,
        b.end_time
      FROM EXECUTION_LOGS el
      LEFT JOIN BOOKINGS b ON el.booking_id = b.id
      WHERE el.user_id = ?
      ORDER BY el.executed_at DESC
      LIMIT ? OFFSET ?
    `, [userId, parseInt(limit), parseInt(offset)]);

    res.json({ logs });
  } catch (error) {
    console.error('Get user logs error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Admin: Get all execution logs
router.get('/admin/all', authenticateToken, requireAdmin, async (req, res) => {
  try {
    const { limit = 100, offset = 0, userId, action } = req.query;

    let query = `
      SELECT 
        el.id,
        el.user_id,
        el.action,
        el.details,
        el.executed_at,
        u.username,
        b.start_time,
        b.end_time
      FROM EXECUTION_LOGS el
      JOIN USERS u ON el.user_id = u.id
      LEFT JOIN BOOKINGS b ON el.booking_id = b.id
      WHERE 1=1
    `;
    
    const params = [];

    if (userId) {
      query += ' AND el.user_id = ?';
      params.push(userId);
    }

    if (action) {
      query += ' AND el.action = ?';
      params.push(action);
    }

    query += ' ORDER BY el.executed_at DESC LIMIT ? OFFSET ?';
    params.push(parseInt(limit), parseInt(offset));

    const [logs] = await pool.execute(query, params);

    res.json({ logs });
  } catch (error) {
    console.error('Get all logs error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Admin: Get system statistics
router.get('/admin/stats', authenticateToken, requireAdmin, async (req, res) => {
  try {
    // Get total users
    const [userCount] = await pool.execute('SELECT COUNT(*) as count FROM USERS');
    
    // Get total bookings
    const [bookingCount] = await pool.execute('SELECT COUNT(*) as count FROM BOOKINGS');
    
    // Get active bookings
    const [activeBookingCount] = await pool.execute(`
      SELECT COUNT(*) as count FROM BOOKINGS 
      WHERE status = 'active' AND start_time <= NOW() AND end_time > NOW()
    `);
    
    // Get total uploads
    const [uploadCount] = await pool.execute('SELECT COUNT(*) as count FROM UPLOADS');
    
    // Get recent activity (last 24 hours)
    const [recentActivity] = await pool.execute(`
      SELECT COUNT(*) as count FROM EXECUTION_LOGS 
      WHERE executed_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
    `);

    // Get action breakdown
    const [actionBreakdown] = await pool.execute(`
      SELECT action, COUNT(*) as count 
      FROM EXECUTION_LOGS 
      WHERE executed_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
      GROUP BY action
    `);

    res.json({
      stats: {
        totalUsers: userCount[0].count,
        totalBookings: bookingCount[0].count,
        activeBookings: activeBookingCount[0].count,
        totalUploads: uploadCount[0].count,
        recentActivity: recentActivity[0].count
      },
      actionBreakdown
    });
  } catch (error) {
    console.error('Get stats error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

module.exports = router;

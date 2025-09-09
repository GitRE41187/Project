const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const pool = require('../config/database');
const { authenticateToken } = require('../middleware/auth');
const axios = require('axios');

const router = express.Router();

// Configure multer for file uploads
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    const uploadDir = process.env.UPLOAD_DIR || 'uploads';
    if (!fs.existsSync(uploadDir)) {
      fs.mkdirSync(uploadDir, { recursive: true });
    }
    cb(null, uploadDir);
  },
  filename: (req, file, cb) => {
    const userId = req.user.id;
    const timestamp = Date.now();
    const extension = path.extname(file.originalname);
    cb(null, `user_${userId}_${timestamp}${extension}`);
  }
});

const fileFilter = (req, file, cb) => {
  // Only allow Python files
  if (file.mimetype === 'text/x-python' || 
      file.mimetype === 'application/x-python-code' ||
      path.extname(file.originalname).toLowerCase() === '.py') {
    cb(null, true);
  } else {
    cb(new Error('Only Python files (.py) are allowed'), false);
  }
};

const upload = multer({
  storage: storage,
  fileFilter: fileFilter,
  limits: {
    fileSize: parseInt(process.env.MAX_FILE_SIZE) || 10 * 1024 * 1024, // 10MB default
    files: 1
  }
});

// Upload file
router.post('/upload', authenticateToken, upload.single('codeFile'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded' });
    }

    const userId = req.user.id;
    const { originalname, filename, path: filePath, size } = req.file;

    // Save upload record to database
    const [result] = await pool.execute(
      'INSERT INTO UPLOADS (user_id, original_filename, file_path, file_size) VALUES (?, ?, ?, ?)',
      [userId, originalname, filePath, size]
    );

    const uploadId = result.insertId;

    // Check if user has active booking
    const [bookings] = await pool.execute(`
      SELECT id, start_time, end_time, status 
      FROM BOOKINGS 
      WHERE user_id = ? AND status = 'active' AND start_time <= NOW() AND end_time > NOW()
    `, [userId]);

    const hasActiveBooking = bookings.length > 0;

    // If user has active booking, send file to Raspberry Pi
    if (hasActiveBooking) {
      try {
        const piResponse = await axios.post(`${process.env.PI_BASE_URL}/upload_code`, {
          user_id: userId,
          file_path: filePath,
          original_filename: originalname
        });

        // Log the upload
        await pool.execute(
          'INSERT INTO EXECUTION_LOGS (user_id, action, details) VALUES (?, ?, ?)',
          [userId, 'upload', `Code uploaded and sent to Pi: ${originalname}`]
        );

        res.json({
          message: 'File uploaded and sent to Raspberry Pi successfully',
          uploadId,
          hasActiveBooking: true,
          piResponse: piResponse.data
        });
      } catch (piError) {
        console.error('Pi upload error:', piError.message);
        res.status(500).json({ 
          error: 'File uploaded but failed to send to Raspberry Pi',
          uploadId,
          hasActiveBooking: true
        });
      }
    } else {
      res.json({
        message: 'File uploaded successfully. Upload to Raspberry Pi when you have an active booking.',
        uploadId,
        hasActiveBooking: false
      });
    }
  } catch (error) {
    console.error('Upload error:', error);
    
    // Clean up uploaded file if database save failed
    if (req.file && req.file.path) {
      try {
        fs.unlinkSync(req.file.path);
      } catch (unlinkError) {
        console.error('Error cleaning up file:', unlinkError);
      }
    }
    
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Get user's uploads
router.get('/my-uploads', authenticateToken, async (req, res) => {
  try {
    const userId = req.user.id;

    const [uploads] = await pool.execute(`
      SELECT id, original_filename, file_path, file_size, uploaded_at
      FROM UPLOADS
      WHERE user_id = ?
      ORDER BY uploaded_at DESC
    `, [userId]);

    res.json({ uploads });
  } catch (error) {
    console.error('Get uploads error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Delete upload
router.delete('/:uploadId', authenticateToken, async (req, res) => {
  try {
    const { uploadId } = req.params;
    const userId = req.user.id;

    // Get upload details
    const [uploads] = await pool.execute(
      'SELECT file_path FROM UPLOADS WHERE id = ? AND user_id = ?',
      [uploadId, userId]
    );

    if (uploads.length === 0) {
      return res.status(404).json({ error: 'Upload not found' });
    }

    const filePath = uploads[0].file_path;

    // Delete from database
    await pool.execute('DELETE FROM UPLOADS WHERE id = ?', [uploadId]);

    // Delete file from filesystem
    try {
      if (fs.existsSync(filePath)) {
        fs.unlinkSync(filePath);
      }
    } catch (unlinkError) {
      console.error('Error deleting file:', unlinkError);
    }

    res.json({ message: 'Upload deleted successfully' });
  } catch (error) {
    console.error('Delete upload error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Download file
router.get('/download/:uploadId', authenticateToken, async (req, res) => {
  try {
    const { uploadId } = req.params;
    const userId = req.user.id;

    // Get upload details
    const [uploads] = await pool.execute(
      'SELECT original_filename, file_path FROM UPLOADS WHERE id = ? AND user_id = ?',
      [uploadId, userId]
    );

    if (uploads.length === 0) {
      return res.status(404).json({ error: 'Upload not found' });
    }

    const { original_filename, file_path } = uploads[0];

    if (!fs.existsSync(file_path)) {
      return res.status(404).json({ error: 'File not found on server' });
    }

    res.download(file_path, original_filename);
  } catch (error) {
    console.error('Download error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

module.exports = router;

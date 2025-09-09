const multer = require('multer');
const path = require('path');
const fs = require('fs');

// Ensure upload directory exists
const uploadDir = process.env.UPLOAD_DIR || 'uploads';
if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir, { recursive: true });
}

const storage = multer.diskStorage({
  destination: (req, file, cb) => {
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

module.exports = upload;

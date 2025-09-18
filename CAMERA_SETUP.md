# Camera Setup Guide

## Overview
This guide explains how to set up and use the camera streaming feature that allows users to connect to the Raspberry Pi camera.

## Features
- Real-time camera streaming from Raspberry Pi
- Camera start/stop controls
- Live video feed in web browser
- User authentication and booking validation
- Camera status monitoring

## Setup Instructions

### 1. Raspberry Pi Setup

#### Install Dependencies
```bash
cd raspberry-pi
pip install -r requirements.txt
```

#### Required Hardware
- USB Camera or Raspberry Pi Camera Module
- Ensure camera is connected and working

#### Test Camera
```bash
# Test if camera is detected
python -c "import cv2; cap = cv2.VideoCapture(0); print('Camera available:', cap.isOpened()); cap.release()"
```

### 2. Backend Setup

#### Environment Variables
Add to your backend `.env` file:
```
PI_BASE_URL=http://localhost:5001
```

#### API Endpoints
The backend now includes these camera endpoints:
- `POST /api/control/camera/start` - Start camera streaming
- `POST /api/control/camera/stop` - Stop camera streaming  
- `GET /api/control/camera/status` - Get camera status

### 3. Frontend Setup

#### Environment Variables
Create `frontend/.env` file:
```
REACT_APP_API_URL=http://localhost:3001/api
REACT_APP_PI_BASE_URL=http://localhost:5001
```

#### New Components
- `Camera.js` - Main camera page component
- Added camera route in `App.js`
- Added camera navigation link in `Navbar.js`

## Usage

### 1. Start the Services

#### Raspberry Pi
```bash
cd raspberry-pi
python app.py
```

#### Backend
```bash
cd backend
npm start
```

#### Frontend
```bash
cd frontend
npm start
```

### 2. Access Camera

1. Login to the system
2. Make sure you have an active booking
3. Navigate to "Camera" in the navigation menu
4. Click "Start Camera" to begin streaming
5. View live feed from Raspberry Pi camera
6. Click "Stop Camera" when done

## Camera API Endpoints (Raspberry Pi)

### Start Camera
```http
POST http://localhost:5001/camera/start
Content-Type: application/json

{
  "user_id": 123
}
```

### Stop Camera
```http
POST http://localhost:5001/camera/stop
Content-Type: application/json

{
  "user_id": 123
}
```

### Camera Status
```http
GET http://localhost:5001/camera/status
```

### Camera Stream
```http
GET http://localhost:5001/camera/stream
```

## Troubleshooting

### Camera Not Working
1. Check if camera is connected: `ls /dev/video*`
2. Test camera with: `python -c "import cv2; cap = cv2.VideoCapture(0); print(cap.isOpened())"`
3. Check camera permissions
4. Verify OpenCV installation

### Stream Not Loading
1. Check Raspberry Pi server is running on port 5001
2. Verify camera is started before accessing stream
3. Check browser console for errors
4. Ensure CORS is properly configured

### Permission Errors
1. Make sure user has active booking
2. Check authentication token is valid
3. Verify user is the current camera user

## Security Features

- User authentication required
- Active booking validation
- Only one user can control camera at a time
- Camera automatically stops when user logs out
- All camera actions are logged in the database

## Performance Notes

- Camera resolution: 640x480
- Frame rate: 30 FPS
- JPEG quality: 80%
- Stream uses MJPEG format for browser compatibility
- Automatic cleanup when camera stops

## Network Configuration

For production deployment, update the URLs:
- Change `localhost` to your Raspberry Pi's IP address
- Update CORS settings for cross-origin requests
- Consider using HTTPS for secure streaming

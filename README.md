# Python Field Control System

A comprehensive system for managing Python code execution on a Raspberry Pi-controlled field. Users can upload Python code, book time slots, and control field operations through a web interface.

## System Architecture

### Components

1. **Frontend (React)** - User interface for code upload, queue management, and field control
2. **Backend (Node.js + Express)** - API server with authentication, queue management, and file handling
3. **Database (MySQL)** - Stores user data, bookings, uploads, and execution logs
4. **Raspberry Pi (Python Flask)** - Handles code execution and field control

### Features

- **User Authentication** - JWT-based login/registration system
- **Code Upload** - Secure Python file upload with validation
- **Queue Management** - Time slot booking and management system
- **Field Control** - Run, stop, and reset field operations
- **Admin Dashboard** - System monitoring and user management
- **Real-time Updates** - Socket.io for live status updates
- **Safety Features** - Code validation and restricted imports

## Quick Start

### Prerequisites

- Node.js (v16 or higher)
- MySQL (v8.0 or higher)
- Python (v3.8 or higher)
- Raspberry Pi (optional, for field control)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd python-field-control-system
   ```

2. **Install dependencies**
   ```bash
   npm run install-all
   ```

3. **Database Setup**
   ```bash
   # Create MySQL database
   mysql -u root -p < database/schema.sql
   ```

4. **Environment Configuration**
   ```bash
   # Backend
   cd backend
   cp env.example .env
   # Edit .env with your database credentials
   
   # Raspberry Pi
   cd raspberry-pi
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Start the system**
   ```bash
   # Start all services
   npm run dev
   
   # Or start individually
   npm run server    # Backend API
   npm run client    # React frontend
   npm run pi        # Raspberry Pi API
   ```

### Default Credentials

- **Admin User**: `admin` / `admin123`
- **API Endpoints**: 
  - Backend: `http://localhost:5000`
  - Frontend: `http://localhost:3000`
  - Raspberry Pi: `http://localhost:5001`

## API Documentation

### Authentication Endpoints

- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login
- `GET /api/auth/me` - Get current user

### Queue Management

- `GET /api/queue` - Get current queue
- `POST /api/queue/book` - Book a time slot
- `DELETE /api/queue/cancel/:id` - Cancel booking
- `GET /api/queue/my-bookings` - Get user's bookings

### File Upload

- `POST /api/uploads/upload` - Upload Python file
- `GET /api/uploads/my-uploads` - Get user's uploads
- `DELETE /api/uploads/:id` - Delete upload

### Field Control

- `POST /api/control/run` - Run user code
- `POST /api/control/stop` - Stop code execution
- `POST /api/control/reset` - Reset field
- `GET /api/control/status` - Get execution status

### Admin Endpoints

- `GET /api/logs/admin/stats` - System statistics
- `GET /api/logs/admin/all` - All activity logs
- `GET /api/queue/admin/all` - All bookings

## Raspberry Pi Setup

### Hardware Requirements

- Raspberry Pi 4 (recommended)
- MicroSD card (32GB+)
- Power supply
- Field control hardware (motors, sensors, etc.)

### Software Installation

1. **Install Python dependencies**
   ```bash
   cd raspberry-pi
   pip install -r requirements.txt
   ```

2. **Configure field control**
   - Update `field_reset_position` in `app.py`
   - Add your field control logic
   - Configure safety limits

3. **Start the service**
   ```bash
   python app.py
   ```

### Safety Features

- **Code Validation** - Only allows safe Python imports
- **Process Isolation** - Each user's code runs in separate process
- **Time Limits** - Automatic cleanup of old files and processes
- **Resource Limits** - Memory and CPU usage restrictions

## Database Schema

### Tables

- **USERS** - User accounts and authentication
- **BOOKINGS** - Time slot reservations
- **UPLOADS** - File upload records
- **EXECUTION_LOGS** - System activity logs
- **FIELDS** - Field configuration

## Development

### Project Structure

```
├── backend/           # Node.js API server
│   ├── config/        # Database configuration
│   ├── middleware/    # Auth and upload middleware
│   ├── routes/        # API routes
│   └── server.js      # Main server file
├── frontend/          # React application
│   ├── src/
│   │   ├── components/    # Reusable components
│   │   ├── contexts/      # React contexts
│   │   ├── pages/         # Page components
│   │   └── App.js         # Main app component
├── raspberry-pi/      # Python Flask API
│   ├── app.py         # Main Flask application
│   └── requirements.txt
├── database/          # Database schema
└── README.md
```

### Adding New Features

1. **Backend**: Add new routes in `backend/routes/`
2. **Frontend**: Create components in `frontend/src/components/`
3. **Database**: Update schema in `database/schema.sql`
4. **Raspberry Pi**: Add endpoints in `raspberry-pi/app.py`

## Deployment

### Production Setup

1. **Environment Variables**
   - Set `NODE_ENV=production`
   - Configure secure JWT secrets
   - Set up production database

2. **Security**
   - Use HTTPS in production
   - Configure CORS properly
   - Set up rate limiting
   - Enable helmet security headers

3. **Monitoring**
   - Set up logging
   - Monitor system resources
   - Track user activity

### Docker Deployment

```dockerfile
# Example Dockerfile for backend
FROM node:16-alpine
WORKDIR /app
COPY backend/package*.json ./
RUN npm ci --only=production
COPY backend/ .
EXPOSE 5000
CMD ["npm", "start"]
```

## Troubleshooting

### Common Issues

1. **Database Connection**
   - Check MySQL service is running
   - Verify credentials in `.env`
   - Ensure database exists

2. **File Upload Issues**
   - Check file size limits
   - Verify upload directory permissions
   - Ensure only `.py` files are uploaded

3. **Raspberry Pi Connection**
   - Check network connectivity
   - Verify API endpoints
   - Check Python dependencies

### Logs

- **Backend**: Check console output and error logs
- **Frontend**: Check browser console for errors
- **Raspberry Pi**: Check console output and execution logs

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Review the API documentation

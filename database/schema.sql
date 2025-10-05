-- Field Control System Database Schema
CREATE DATABASE IF NOT EXISTS field_control;
USE field_control;

-- Users table
CREATE TABLE USERS (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('user', 'admin') DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Fields table (for future expansion)
CREATE TABLE FIELDS (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bookings/Queue table
CREATE TABLE BOOKINGS (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    field_id INT DEFAULT 1,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    status ENUM('pending', 'active', 'done', 'cancelled') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES USERS(id) ON DELETE CASCADE,
    FOREIGN KEY (field_id) REFERENCES FIELDS(id) ON DELETE CASCADE
);

-- Code uploads table
CREATE TABLE UPLOADS (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size INT NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES USERS(id) ON DELETE CASCADE
);

-- Robot cars table
CREATE TABLE ROBOT_CARS (
    id INT PRIMARY KEY AUTO_INCREMENT,
    car_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    ip VARCHAR(45) NOT NULL,
    port INT NOT NULL,
    status ENUM('available', 'in_use', 'offline') DEFAULT 'available',
    `current_user` INT,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`current_user`) REFERENCES USERS(id) ON DELETE SET NULL
);

-- Execution logs table
CREATE TABLE EXECUTION_LOGS (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    booking_id INT,
    robot_car_id INT,
    action ENUM('upload', 'run', 'stop', 'reset', 'camera_start', 'camera_stop', 'error') NOT NULL,
    details TEXT,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES USERS(id) ON DELETE CASCADE,
    FOREIGN KEY (booking_id) REFERENCES BOOKINGS(id) ON DELETE SET NULL,
    FOREIGN KEY (robot_car_id) REFERENCES ROBOT_CARS(id) ON DELETE SET NULL
);

-- Insert default field
INSERT INTO FIELDS (name, description) VALUES ('Main Field', 'Primary field for Python code execution');

-- Insert default admin user (password: admin123)
INSERT INTO USERS (username, email, password_hash, role) VALUES 
('admin', 'admin@fieldcontrol.com', '$2a$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'admin');

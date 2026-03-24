-- Field Control System Database Schema (PostgreSQL)
-- สร้าง database:  psql -U postgres -c "CREATE DATABASE field_control"
-- รัน schema:      psql -U postgres -d field_control -f backend-aspnet/database/schema.sql

CREATE TABLE USERS (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user' NOT NULL CHECK (role IN ('user', 'admin')),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE FIELDS (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE BOOKINGS (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES USERS(id) ON DELETE CASCADE,
    field_id INT DEFAULT 1 REFERENCES FIELDS(id) ON DELETE CASCADE,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' NOT NULL CHECK (status IN ('pending', 'active', 'done', 'cancelled')),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE UPLOADS (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES USERS(id) ON DELETE CASCADE,
    original_filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size BIGINT NOT NULL,
    uploaded_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ROBOT_CARS (
    id SERIAL PRIMARY KEY,
    car_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    ip VARCHAR(45) NOT NULL,
    port INT NOT NULL,
    status VARCHAR(20) DEFAULT 'available' NOT NULL CHECK (status IN ('available', 'in_use', 'offline')),
    current_user_id INT REFERENCES USERS(id) ON DELETE SET NULL,
    last_seen TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE EXECUTION_LOGS (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES USERS(id) ON DELETE CASCADE,
    booking_id INT REFERENCES BOOKINGS(id) ON DELETE SET NULL,
    robot_car_id INT REFERENCES ROBOT_CARS(id) ON DELETE SET NULL,
    action VARCHAR(30) NOT NULL CHECK (action IN ('upload', 'run', 'stop', 'reset', 'camera_start', 'camera_stop', 'error')),
    details TEXT,
    executed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
   NEW.updated_at = CURRENT_TIMESTAMP;
   RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_users_updated_at BEFORE UPDATE ON USERS
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

CREATE TRIGGER tr_bookings_updated_at BEFORE UPDATE ON BOOKINGS
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

CREATE TRIGGER tr_robot_cars_updated_at BEFORE UPDATE ON ROBOT_CARS
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

INSERT INTO FIELDS (name, description) VALUES ('Main Field', 'Primary field for Python code execution');

INSERT INTO USERS (username, email, password_hash, role) VALUES
('admin', 'admin@fieldcontrol.com', '$2a$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'admin');

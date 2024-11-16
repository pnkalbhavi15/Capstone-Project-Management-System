drop database capstone_management;
CREATE DATABASE IF NOT EXISTS capstone_management;
USE capstone_management;

DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS teams;
DROP TABLE IF EXISTS team_members;
DROP TABLE IF EXISTS faculty_slots;
DROP TABLE IF EXISTS mentoring_requests;
DROP TABLE IF EXISTS notifications;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('student', 'faculty', 'admin') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS teams ( 
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE
);
ALTER TABLE teams ADD COLUMN member_count INT DEFAULT 0;

CREATE TABLE IF NOT EXISTS team_members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    team_id INT NOT NULL,
    user_id INT NOT NULL,
    UNIQUE (user_id),
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS mentoring_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    team_id INT NOT NULL,
    faculty_id INT NOT NULL,
    user_id INT NOT NULL,
    details TEXT,
    resume_file LONGBLOB,
    request_status ENUM('pending', 'accepted', 'rejected') DEFAULT 'pending',
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (faculty_id) REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS faculty_slots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    faculty_id INT NOT NULL,
    time_slot VARCHAR(255) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (faculty_id) REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    message VARCHAR(255),
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS user_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    action VARCHAR(255),
    action_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    username VARCHAR(255),
    role ENUM('student', 'faculty', 'admin')
);

CREATE INDEX idx_team_id ON team_members (team_id);
CREATE INDEX idx_user_id_team_members ON team_members (user_id);
CREATE INDEX idx_user_id_mentoring_requests ON mentoring_requests (user_id);
CREATE INDEX idx_faculty_id ON faculty_slots (faculty_id);
CREATE INDEX idx_user_id_notifications ON notifications (user_id);

DELIMITER //
CREATE PROCEDURE add_user(
    IN username VARCHAR(255),
    IN password_hash VARCHAR(255),
    IN role ENUM('student', 'faculty', 'admin')
)
BEGIN
    INSERT INTO users (username, password_hash, role) VALUES (username, password_hash, role);
END //
DELIMITER ;

DELIMITER //
CREATE TRIGGER after_user_insert
AFTER INSERT ON users
FOR EACH ROW
BEGIN
    INSERT INTO user_log (action, username, role)
    VALUES ('User  Registered', NEW.username, NEW.role);
END //
DELIMITER ;

CALL add_user('testuser', 'hashed_password', 'student'); 
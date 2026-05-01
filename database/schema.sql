-- InterviewAI Database Schema
-- Run once to set up a fresh database

CREATE DATABASE IF NOT EXISTS InterviewAI CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE InterviewAI;

-- ── Users ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    full_name       VARCHAR(255) NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    password        VARCHAR(255) NOT NULL,
    -- Profile fields
    phone           VARCHAR(50)  DEFAULT NULL,
    bio             TEXT         DEFAULT NULL,
    linkedin        VARCHAR(255) DEFAULT NULL,
    github          VARCHAR(255) DEFAULT NULL,
    profile_picture VARCHAR(255) DEFAULT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- ── Password Resets ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS password_resets (
    email      VARCHAR(255) PRIMARY KEY,
    code       VARCHAR(10),
    token      VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- ── Interviews ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS interviews (
    interview_id VARCHAR(100) PRIMARY KEY,
    user_id      INT NOT NULL,
    field        VARCHAR(255),
    cv_filename  VARCHAR(255) DEFAULT NULL,   -- original CV file name
    cv_analysis  JSON,
    answers      JSON,
    feedback     JSON,
    courses      JSON,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
select * from users;
select * from password_resets;
select * from interviews;
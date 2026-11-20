-- ==============================================================================
-- Database Schema: Automated Image Preprocessing System Using AWS
-- Module 5: AWS RDS MySQL Database Integration
-- Target Database: Amazon RDS MySQL 8.x
-- ==============================================================================

-- Create database if not exists
CREATE DATABASE IF NOT EXISTS `image_preprocessing`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE `image_preprocessing`;

-- ------------------------------------------------------------------------------
-- Table: image_records
-- Stores comprehensive metadata of raw uploaded images and their processed counterparts.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `image_records` (
    `image_id` VARCHAR(36) PRIMARY KEY,

    `original_filename` VARCHAR(255) NOT NULL,

    `bucket_name` VARCHAR(255) NOT NULL,

    `original_s3_key` VARCHAR(512) NOT NULL,

    `processed_s3_key` VARCHAR(512) DEFAULT NULL,

    `original_format` VARCHAR(20) DEFAULT NULL,

    `processed_format` VARCHAR(20) DEFAULT NULL,

    `original_width` INT DEFAULT NULL,

    `original_height` INT DEFAULT NULL,

    `processed_width` INT DEFAULT NULL,

    `processed_height` INT DEFAULT NULL,

    `original_size_bytes` BIGINT DEFAULT NULL,

    `processed_size_bytes` BIGINT DEFAULT NULL,

    `content_type` VARCHAR(100) DEFAULT NULL,

    `processing_status` VARCHAR(20) NOT NULL DEFAULT 'PENDING',

    `error_message` TEXT DEFAULT NULL,

    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    `processed_at` TIMESTAMP NULL DEFAULT NULL,

    INDEX `idx_processing_status` (`processing_status`),

    INDEX `idx_created_at` (`created_at`),

    UNIQUE KEY `uk_original_s3_key` (`original_s3_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- Useful Verification & Diagnostic Queries
-- ------------------------------------------------------------------------------
-- View all recorded images:
-- SELECT * FROM image_records ORDER BY created_at DESC;

-- Check processing status breakdown:
-- SELECT processing_status, COUNT(*) AS count FROM image_records GROUP BY processing_status;

-- Inspect pending or failed items:
-- SELECT image_id, original_filename, processing_status, error_message FROM image_records WHERE processing_status IN ('PENDING', 'FAILED');

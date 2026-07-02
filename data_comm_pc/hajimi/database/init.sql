-- Hajimi ground-station login database initialization.
-- Default MySQL connection used by the app:
--   host: 127.0.0.1
--   port: 3306
--   user: root
--   password: 123456
--
-- Default app login:
--   username: admin
--   password: 123456

CREATE DATABASE IF NOT EXISTS `edge_agent_platform`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `edge_agent_platform`;

CREATE TABLE IF NOT EXISTS `users` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(64) NOT NULL,
  `display_name` VARCHAR(64) NOT NULL,
  `password_hash` CHAR(64) NOT NULL,
  `salt` CHAR(32) NOT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `last_login_at` TIMESTAMP NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_users_username` (`username`)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

INSERT INTO `users` (`username`, `display_name`, `password_hash`, `salt`)
VALUES (
  'admin',
  'Administrator',
  '53020ce8a0d34eed28d31be2db374e21c0358a02e99c7318a675656fc8f6bc9a',
  '0123456789abcdeffedcba9876543210'
)
ON DUPLICATE KEY UPDATE
  `display_name` = VALUES(`display_name`);

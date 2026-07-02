# -*- coding: utf-8 -*-
"""MySQL-backed user repository for application login."""

import hashlib
import hmac
import os
import re
from dataclasses import dataclass
from typing import Optional

import pymysql
from pymysql.cursors import DictCursor

from config.auth_config import AuthConfig


@dataclass(frozen=True)
class AuthUser:
    user_id: int
    username: str
    display_name: str


class MySQLUserRepository:
    def __init__(self, config: AuthConfig):
        self.config = config
        self._database = self._quote_identifier(config.mysql_database)
        self._table = self._quote_identifier(config.users_table)

    def initialize(self) -> None:
        """Create the database, user table, and first admin account if needed."""
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS {self._database} "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )

        with self._connect(database=self.config.mysql_database) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._table} (
                        id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                        username VARCHAR(64) NOT NULL,
                        display_name VARCHAR(64) NOT NULL,
                        password_hash CHAR(64) NOT NULL,
                        salt CHAR(32) NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        last_login_at TIMESTAMP NULL DEFAULT NULL,
                        PRIMARY KEY (id),
                        UNIQUE KEY uq_users_username (username)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )

        self._ensure_default_user()

    def authenticate(self, username: str, password: str) -> Optional[AuthUser]:
        username = username.strip()
        if not username or not password:
            return None

        with self._connect(database=self.config.mysql_database) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT id, username, display_name, password_hash, salt "
                    f"FROM {self._table} WHERE username = %s LIMIT 1",
                    (username,),
                )
                row = cursor.fetchone()
                if not row:
                    return None

                password_hash = self._hash_password(password, row["salt"])
                if not hmac.compare_digest(password_hash, row["password_hash"]):
                    return None

                cursor.execute(
                    f"UPDATE {self._table} SET last_login_at = NOW() WHERE id = %s",
                    (row["id"],),
                )
                return AuthUser(
                    user_id=int(row["id"]),
                    username=row["username"],
                    display_name=row["display_name"],
                )

    def create_user(self, username: str, password: str, display_name: str = "") -> AuthUser:
        username = username.strip()
        display_name = display_name.strip() or username
        self._validate_new_user(username, password, display_name)

        salt = os.urandom(16).hex()
        password_hash = self._hash_password(password, salt)

        try:
            with self._connect(database=self.config.mysql_database) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"INSERT INTO {self._table} "
                        "(username, display_name, password_hash, salt) "
                        "VALUES (%s, %s, %s, %s)",
                        (username, display_name, password_hash, salt),
                    )
                    return AuthUser(
                        user_id=int(cursor.lastrowid),
                        username=username,
                        display_name=display_name,
                    )
        except pymysql.err.IntegrityError as exc:
            raise ValueError("用户名已存在") from exc

    def _ensure_default_user(self) -> None:
        with self._connect(database=self.config.mysql_database) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) AS total FROM {self._table}")
                row = cursor.fetchone()
                if row and int(row["total"]) > 0:
                    return

        self.create_user(
            self.config.default_username,
            self.config.default_password,
            self.config.default_display_name,
        )

    def _connect(self, database: Optional[str] = None):
        return pymysql.connect(
            host=self.config.mysql_host,
            port=self.config.mysql_port,
            user=self.config.mysql_user,
            password=self.config.mysql_password,
            database=database,
            autocommit=True,
            charset="utf8mb4",
            cursorclass=DictCursor,
            connect_timeout=self.config.connect_timeout,
        )

    @staticmethod
    def _hash_password(password: str, salt_hex: str) -> str:
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            120000,
        )
        return digest.hex()

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_]+", identifier):
            raise ValueError(f"Unsafe MySQL identifier: {identifier}")
        return f"`{identifier}`"

    @staticmethod
    def _validate_new_user(username: str, password: str, display_name: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.@-]{3,64}", username):
            raise ValueError("用户名需为 3-64 位，可包含字母、数字、下划线、点、@ 或 -")
        if len(password) < 6:
            raise ValueError("密码至少 6 位")
        if len(display_name) > 64:
            raise ValueError("显示名称不能超过 64 位")

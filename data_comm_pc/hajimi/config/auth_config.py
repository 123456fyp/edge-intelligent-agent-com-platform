# -*- coding: utf-8 -*-
"""Authentication and MySQL configuration for the ground station."""

import os
from dataclasses import dataclass


@dataclass
class AuthConfig:
    mysql_host: str = os.getenv("EDGE_AGENT_MYSQL_HOST", "127.0.0.1")
    mysql_port: int = int(os.getenv("EDGE_AGENT_MYSQL_PORT", "3306"))
    mysql_user: str = os.getenv("EDGE_AGENT_MYSQL_USER", "root")
    mysql_password: str = os.getenv("EDGE_AGENT_MYSQL_PASSWORD", "123456")
    mysql_database: str = os.getenv("EDGE_AGENT_MYSQL_DATABASE", "edge_agent_platform")
    users_table: str = os.getenv("EDGE_AGENT_USERS_TABLE", "users")
    connect_timeout: int = int(os.getenv("EDGE_AGENT_MYSQL_TIMEOUT", "5"))

    default_username: str = os.getenv("EDGE_AGENT_DEFAULT_USERNAME", "admin")
    default_password: str = os.getenv("EDGE_AGENT_DEFAULT_PASSWORD", "123456")
    default_display_name: str = os.getenv("EDGE_AGENT_DEFAULT_DISPLAY_NAME", "Administrator")

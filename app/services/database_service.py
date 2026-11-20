"""
Amazon RDS MySQL Database Service
Automated Image Preprocessing System Using AWS

Manages database connections, parameterized queries, transactional execution,
and metadata persistence for raw and processed image records using PyMySQL.
"""

import os
import uuid
import logging
from typing import Optional, Dict, Any, List
import pymysql
from pymysql.cursors import DictCursor

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Base exception for database operations."""
    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.original_exception = original_exception


class DatabaseConnectionError(DatabaseError):
    """Exception raised when connection to MySQL cannot be established."""
    pass


class DatabaseService:
    """
    Database Service implementing connection management and operations for image_records.
    Uses parameterized SQL queries, explicit transaction control, and guaranteed connection cleanup.
    """

    ALLOWED_UPDATE_FIELDS = {
        'processing_status',
        'processed_s3_key',
        'processed_format',
        'processed_width',
        'processed_height',
        'processed_size_bytes',
        'error_message',
        'processed_at'
    }

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        db_name: Optional[str] = None,
        connect_timeout: Optional[int] = None
    ):
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._db_name = db_name
        self._connect_timeout = connect_timeout
        self._mock_connection = None

    @property
    def host(self) -> str:
        if self._host is not None:
            return self._host
        try:
            from flask import current_app, has_app_context
            if has_app_context():
                if current_app.config.get('TESTING'):
                    return ''
                app_host = current_app.config.get('DB_HOST')
                if app_host is not None:
                    return app_host
        except (ImportError, RuntimeError):
            pass
        return os.getenv('DB_HOST', '')

    @property
    def port(self) -> int:
        if self._port is not None:
            return self._port
        try:
            return int(os.getenv('DB_PORT', 3306))
        except (ValueError, TypeError):
            return 3306

    @property
    def user(self) -> str:
        if self._user is not None:
            return self._user
        return os.getenv('DB_USER', 'admin')

    @property
    def password(self) -> str:
        if self._password is not None:
            return self._password
        return os.getenv('DB_PASSWORD', '')

    @property
    def db_name(self) -> str:
        if self._db_name is not None:
            return self._db_name
        return os.getenv('DB_NAME', 'image_preprocessing')

    @property
    def connect_timeout(self) -> int:
        if self._connect_timeout is not None:
            return self._connect_timeout
        try:
            return int(os.getenv('DB_CONNECT_TIMEOUT', 10))
        except (ValueError, TypeError):
            return 10

    def set_mock_connection(self, connection):
        """Allows injecting a mock connection object for testing."""
        self._mock_connection = connection

    def is_configured(self) -> bool:
        """
        Validates whether database connection configuration is provided
        and does not contain placeholder tokens.
        """
        host = self.host.strip() if self.host else ''
        if not host:
            return False
        # Guard against placeholder endpoint strings in .env.example
        placeholders = ('your-rds-endpoint', 'localhost-placeholder', 'your_rds_endpoint')
        if any(token in host.lower() for token in placeholders):
            return False
        return True

    def get_connection(self):
        """
        Establishes a new PyMySQL connection.
        Enforces connection timeout, utf8mb4 encoding, and DictCursor.
        Never logs passwords.
        """
        if self._mock_connection is not None:
            return self._mock_connection

        if not self.is_configured():
            logger.warning("Database connection requested but database is not configured.")
            raise DatabaseConnectionError("Database configuration is missing or incomplete.")

        try:
            logger.info("Connecting to MySQL host: %s:%d, DB: %s, User: %s",
                        self.host, self.port, self.db_name, self.user)
            connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.db_name,
                connect_timeout=self.connect_timeout,
                charset='utf8mb4',
                cursorclass=DictCursor,
                autocommit=False
            )
            return connection
        except pymysql.MySQLError as err:
            logger.error("Failed to connect to MySQL database at %s:%d: %s",
                         self.host, self.port, str(err))
            raise DatabaseConnectionError(f"Database connection failed: {str(err)}", original_exception=err)
        except Exception as err:
            logger.error("Unexpected error connecting to MySQL database: %s", str(err))
            raise DatabaseConnectionError(f"Unexpected database connection error: {str(err)}", original_exception=err)

    def test_connection(self) -> bool:
        """
        Tests database connectivity by executing a lightweight query.
        Safely closes the connection upon completion.
        """
        if not self.is_configured():
            return False

        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            result = cursor.fetchone()
            return result is not None
        except Exception as err:
            logger.warning("Database connectivity test failed: %s", str(err))
            return False
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def check_health(self) -> str:
        """
        Returns status string for health check endpoint:
        'connected', 'not_configured', or 'disconnected'.
        """
        if not self.is_configured():
            return "not_configured"
        if self.test_connection():
            return "connected"
        return "disconnected"

    def create_image_record(self, record_data: Dict[str, Any]) -> str:
        """
        Inserts a new image record into 'image_records' table with status PENDING.
        Uses parameterized SQL query and commits transaction.
        Returns the unique image_id.
        """
        image_id = record_data.get('image_id') or str(uuid.uuid4())
        processing_status = record_data.get('processing_status', 'PENDING')
        original_filename = record_data.get('original_filename', '')
        bucket_name = record_data.get('bucket_name', '')
        original_s3_key = record_data.get('original_s3_key', '')
        original_format = record_data.get('original_format')
        original_width = record_data.get('original_width')
        original_height = record_data.get('original_height')
        original_size_bytes = record_data.get('original_size_bytes')
        content_type = record_data.get('content_type')
        error_message = record_data.get('error_message')

        sql = """
            INSERT INTO image_records (
                image_id, original_filename, bucket_name, original_s3_key,
                original_format, original_width, original_height,
                original_size_bytes, content_type, processing_status, error_message
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s
            );
        """
        params = (
            image_id, original_filename, bucket_name, original_s3_key,
            original_format, original_width, original_height,
            original_size_bytes, content_type, processing_status, error_message
        )

        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            logger.info("Successfully created image record: image_id=%s, key=%s",
                        image_id, original_s3_key)
            return image_id
        except Exception as err:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            logger.error("Failed to create image record (id=%s): %s", image_id, str(err))
            raise DatabaseError(f"Failed to create image record: {str(err)}", original_exception=err)
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def update_image_record(self, image_id: str, updates: Dict[str, Any]) -> bool:
        """
        Updates fields of an existing image record.
        Enforces:
        - Only permitted update fields are processed.
        - Status 'COMPLETED' is never overwritten by a subsequent 'PENDING' or 'PROCESSING'.
        Uses parameterized SQL query, commits transaction, and cleans up connection.
        Returns True if a matching record was updated, False otherwise.
        """
        if not updates:
            return False

        # Filter only allowed fields
        valid_updates = {k: v for k, v in updates.items() if k in self.ALLOWED_UPDATE_FIELDS}
        if not valid_updates:
            logger.warning("No valid fields provided for update on image_id=%s", image_id)
            return False

        set_clauses = []
        params = []
        for field, val in valid_updates.items():
            set_clauses.append(f"`{field}` = %s")
            params.append(val)

        # Protection: do not overwrite a COMPLETED status with PENDING or PROCESSING
        new_status = valid_updates.get('processing_status')
        if new_status in ('PENDING', 'PROCESSING'):
            where_condition = "WHERE `image_id` = %s AND `processing_status` != 'COMPLETED'"
        else:
            where_condition = "WHERE `image_id` = %s"

        params.append(image_id)

        sql = f"UPDATE `image_records` SET {', '.join(set_clauses)} {where_condition};"

        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(sql, tuple(params))
            conn.commit()
            rc = getattr(cursor, 'rowcount', 1)
            updated = (rc > 0) if isinstance(rc, int) else True
            logger.info("Updated image record %s (rows affected=%s)", image_id, str(rc))
            return updated
        except Exception as err:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            logger.error("Failed to update image record %s: %s", image_id, str(err))
            raise DatabaseError(f"Failed to update image record: {str(err)}", original_exception=err)
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_image_by_id(self, image_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a single image record by image_id.
        Returns dictionary or None if not found.
        """
        sql = "SELECT * FROM `image_records` WHERE `image_id` = %s LIMIT 1;"
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(sql, (image_id,))
            record = cursor.fetchone()
            return record
        except Exception as err:
            logger.error("Failed to retrieve image by id (%s): %s", image_id, str(err))
            raise DatabaseError(f"Failed to retrieve image: {str(err)}", original_exception=err)
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_image_by_s3_key(self, original_s3_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a single image record by original_s3_key.
        Returns dictionary or None if not found.
        """
        sql = "SELECT * FROM `image_records` WHERE `original_s3_key` = %s LIMIT 1;"
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(sql, (original_s3_key,))
            record = cursor.fetchone()
            return record
        except Exception as err:
            logger.error("Failed to retrieve image by s3 key (%s): %s", original_s3_key, str(err))
            raise DatabaseError(f"Failed to retrieve image by s3 key: {str(err)}", original_exception=err)
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_all_images(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Retrieves a paginated list of image records ordered by created_at DESC.
        """
        sql = "SELECT * FROM `image_records` ORDER BY `created_at` DESC LIMIT %s OFFSET %s;"
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(sql, (limit, offset))
            records = cursor.fetchall()
            return list(records) if records else []
        except Exception as err:
            logger.error("Failed to retrieve images list: %s", str(err))
            raise DatabaseError(f"Failed to list images: {str(err)}", original_exception=err)
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_processing_statistics(self) -> Dict[str, Any]:
        """
        Computes aggregate metrics by processing_status.
        Returns dict with total and individual counts.
        """
        sql = "SELECT `processing_status`, COUNT(*) AS count FROM `image_records` GROUP BY `processing_status`;"
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall() or []
            counts: Dict[str, int] = {}
            total = 0
            for r in rows:
                status = r.get('processing_status', 'UNKNOWN')
                c = int(r.get('count', 0))
                counts[status] = c
                total += c

            return {
                "total": total,
                "pending": counts.get("PENDING", 0),
                "processing": counts.get("PROCESSING", 0),
                "completed": counts.get("COMPLETED", 0),
                "failed": counts.get("FAILED", 0),
                "by_status": counts
            }
        except Exception as err:
            logger.error("Failed to compute processing statistics: %s", str(err))
            raise DatabaseError(f"Failed to compute statistics: {str(err)}", original_exception=err)
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass


    def get_dashboard_statistics(self) -> Dict[str, Any]:
        """
        Calculates aggregate statistics for the dashboard cards:
        - total_images: Total number of records
        - completed: Successfully processed records
        - pending: Pending processing records
        - processing: Actively processing records
        - failed: Failed records
        Uses an efficient GROUP BY query without loading full records.
        """
        stats = self.get_processing_statistics()
        return {
            "total_images": stats.get("total", 0),
            "completed": stats.get("completed", 0),
            "pending": stats.get("pending", 0),
            "processing": stats.get("processing", 0),
            "failed": stats.get("failed", 0)
        }

    def get_images_paginated(self, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
        """
        Fetches paginated image records sorted newest first with metadata.
        Returns:
            {
                "records": list of dicts,
                "pagination": {
                    "page": int,
                    "per_page": int,
                    "total_records": int,
                    "total_pages": int,
                    "has_next": bool,
                    "has_prev": bool
                }
            }
        """
        page = max(1, int(page))
        per_page = max(1, min(100, int(per_page)))
        offset = (page - 1) * per_page

        count_sql = "SELECT COUNT(*) AS total FROM `image_records`;"
        records_sql = "SELECT * FROM `image_records` ORDER BY `created_at` DESC LIMIT %s OFFSET %s;"

        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(count_sql)
            count_row = cursor.fetchone()
            total_records = int(count_row.get("total", 0)) if count_row else 0

            cursor.execute(records_sql, (per_page, offset))
            records = cursor.fetchall() or []

            # Format datetime fields
            serialized_records = []
            for rec in records:
                r_dict = dict(rec)
                for dt_field in ('created_at', 'updated_at', 'processed_at'):
                    if r_dict.get(dt_field) is not None and hasattr(r_dict[dt_field], 'strftime'):
                        r_dict[dt_field] = r_dict[dt_field].strftime('%Y-%m-%d %H:%M:%S')
                serialized_records.append(r_dict)

            total_pages = (total_records + per_page - 1) // per_page if total_records > 0 else 0

            return {
                "records": serialized_records,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total_records": total_records,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }
        except Exception as err:
            logger.error("Failed to retrieve paginated images: %s", str(err))
            raise DatabaseError(f"Failed to list paginated images: {str(err)}", original_exception=err)
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_image_details(self, image_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves detailed metadata for a single image by its UUID image_id.
        Formats datetime fields for serialization.
        """
        record = self.get_image_by_id(image_id)
        if not record:
            return None
        r_dict = dict(record)
        for dt_field in ('created_at', 'updated_at', 'processed_at'):
            if r_dict.get(dt_field) is not None and hasattr(r_dict[dt_field], 'strftime'):
                r_dict[dt_field] = r_dict[dt_field].strftime('%Y-%m-%d %H:%M:%S')
        return r_dict


# Default singleton instance
database_service = DatabaseService()

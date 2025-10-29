"""
Database Manager - Handle all DB operations
"""

import pymysql
import json
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()


class DbManager:
    def __init__(self):
        self.host = os.getenv('DB_HOST', '220.121.120.83')
        self.port = int(os.getenv('DB_PORT', 3306))
        self.user = os.getenv('DB_USER', 'tls_user')
        self.password = os.getenv('DB_PASSWORD', '')
        self.database = os.getenv('DB_NAME', 'tls-1029')

    def _get_connection(self):
        """Get database connection"""
        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset='utf8mb4'
        )

    def save_tls_fingerprint(self, device_name, browser, os_version,
                            tls_data, http2_data, ja3_hash,
                            akamai_fingerprint, collected_at):
        """
        Save TLS fingerprint to database

        Returns:
            int: TLS fingerprint ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            query = """
                INSERT INTO tls_fingerprints (
                    device_name, browser, os_version,
                    tls_data, http2_data,
                    ja3_hash, akamai_fingerprint,
                    collected_at, cipher_count, extension_count
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            cipher_count = len(tls_data.get('cipher_suites', []))
            extension_count = len(tls_data.get('extensions', []))

            cursor.execute(query, (
                device_name,
                browser,
                os_version,
                json.dumps(tls_data),
                json.dumps(http2_data),
                ja3_hash,
                akamai_fingerprint,
                collected_at,
                cipher_count,
                extension_count
            ))

            conn.commit()
            return cursor.lastrowid

        finally:
            cursor.close()
            conn.close()

    def save_cookies(self, device_name, browser, os_version,
                    tls_fingerprint_id, cookie_data, collected_at,
                    cookie_type='browser'):
        """
        Save cookies to database

        Args:
            cookie_type: Cookie source type
                - 'browser': Collected from browser (main-pc.py)
                - 'crawled': Updated during crawling (curlcffi.py)

        Returns:
            int: Cookie ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            query = """
                INSERT INTO cookies (
                    device_name, browser, os_version,
                    tls_fingerprint_id, cookie_type, cookie_data,
                    collected_at, is_valid
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """

            cursor.execute(query, (
                device_name,
                browser,
                os_version,
                tls_fingerprint_id,
                cookie_type,
                json.dumps(cookie_data),
                collected_at,
                1
            ))

            conn.commit()
            return cursor.lastrowid

        finally:
            cursor.close()
            conn.close()

    def get_latest_fingerprint(self):
        """
        Get latest TLS fingerprint and cookies from database

        Returns:
            dict: {
                'device_name': str,
                'tls_data': dict,
                'http2_data': dict,
                'cookies': list,
                'ja3_hash': str,
                'akamai_fingerprint': str,
                'collected_at': datetime
            }
        """
        conn = self._get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        try:
            # Get latest TLS fingerprint
            tls_query = """
                SELECT id, device_name, tls_data, http2_data,
                       ja3_hash, akamai_fingerprint, collected_at
                FROM tls_fingerprints
                ORDER BY collected_at DESC
                LIMIT 1
            """

            cursor.execute(tls_query)
            tls_row = cursor.fetchone()

            if not tls_row:
                return None

            tls_fingerprint_id = tls_row['id']

            # Get corresponding cookies
            cookie_query = """
                SELECT cookie_data
                FROM cookies
                WHERE tls_fingerprint_id = %s
                ORDER BY collected_at DESC
                LIMIT 1
            """

            cursor.execute(cookie_query, (tls_fingerprint_id,))
            cookie_row = cursor.fetchone()

            if not cookie_row:
                return None

            return {
                'device_name': tls_row['device_name'],
                'tls_data': json.loads(tls_row['tls_data']),
                'http2_data': json.loads(tls_row['http2_data']),
                'cookies': json.loads(cookie_row['cookie_data']),
                'ja3_hash': tls_row['ja3_hash'],
                'akamai_fingerprint': tls_row['akamai_fingerprint'],
                'collected_at': tls_row['collected_at']
            }

        finally:
            cursor.close()
            conn.close()

"""
TLS Fingerprint Extractor
- Extract REAL TLS information from browserleaks.com
- Collect actual cipher suites, extensions, supported groups
- Get real JA3 hash and Akamai fingerprint
"""

import asyncio
import nodriver as uc
import json
import hashlib
import sys
from pathlib import Path

# Load config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import WAIT_TIMES

class TlsExtractor:
    def __init__(self, page):
        """
        Args:
            page: nodriver Page object
        """
        self.page = page

    async def extract(self):
        """
        Extract REAL TLS fingerprint from browserleaks.com

        Returns:
            dict: {
                'tls_data': {...},
                'http2_data': {...}
            }
        """
        print(f"[TlsExtractor] Extracting REAL TLS information from browserleaks.com...")

        try:
            # Get current tab and open new tab for browserleaks
            current_url = self.page.url
            print(f"[TlsExtractor] Current page: {current_url}")

            # Navigate to browserleaks main page (NOT /json - full data)
            print(f"[TlsExtractor] Fetching FULL TLS data from browserleaks.com...")
            await self.page.get('https://tls.browserleaks.com/')
            await asyncio.sleep(WAIT_TIMES['tls_page'])

            # Get JSON data from <pre> tag
            json_text = await self.page.evaluate('document.querySelector("pre").textContent')

            if not json_text:
                print(f"[TlsExtractor] WARNING: Could not get browserleaks data, using fallback")
                return self._get_fallback_data()

            browserleaks_data = json.loads(json_text)

            # Extract COMPLETE TLS data from browserleaks
            tls_section = browserleaks_data.get('tls', {})

            # Cipher suites (with full details)
            cipher_suites = tls_section.get('cipher_suites', [])

            # Extensions (with full details)
            extensions = tls_section.get('extensions', [])

            # Supported groups (extract from extensions)
            supported_groups = []
            for ext in extensions:
                if ext.get('name') == 'supported_groups':
                    named_groups = ext.get('data', {}).get('named_groups', [])
                    supported_groups = [g.get('name', '') for g in named_groups]
                    break

            # Signature algorithms (extract from extensions)
            signature_algorithms = []
            for ext in extensions:
                if ext.get('name') == 'signature_algorithms':
                    algorithms = ext.get('data', {}).get('algorithms', [])
                    signature_algorithms = [a.get('name', '') for a in algorithms]
                    break

            # HTTP/2 SETTINGS (extract from http2 section)
            http2_section = browserleaks_data.get('http2', [])
            http2_settings = {}
            for frame in http2_section:
                if frame.get('name') == 'SETTINGS':
                    for setting in frame.get('settings', []):
                        setting_name = setting.get('name', '')
                        setting_value = setting.get('value', 0)
                        if not setting_name.startswith('GREASE'):
                            http2_settings[setting_name] = setting_value
                    break

            # Get JA3 and Akamai data
            ja3_hash = browserleaks_data.get('ja3_hash', '')
            ja3_text = browserleaks_data.get('ja3_text', '')
            akamai_hash = browserleaks_data.get('akamai_hash', '')
            akamai_text = browserleaks_data.get('akamai_text', '')

            tls_data = {
                'tls_version': tls_section.get('connection_version', {}).get('name', 'TLS 1.3'),
                'cipher_suites': cipher_suites,
                'extensions': extensions,
                'supported_groups': supported_groups,
                'signature_algorithms': signature_algorithms,
                'ja3_hash': ja3_hash,
                'ja3_text': ja3_text
            }

            http2_data = {
                'settings': http2_settings,
                'akamai_fingerprint': akamai_hash,
                'akamai_text': akamai_text
            }

            print(f"[TlsExtractor] Extracted REAL TLS data:")
            print(f"  - JA3 Hash: {tls_data['ja3_hash']}")
            print(f"  - Cipher suites: {len(cipher_suites)}")
            print(f"  - Extensions: {len(extensions)}")
            print(f"  - Supported groups: {len(supported_groups)}")
            print(f"  - Akamai Hash: {http2_data['akamai_fingerprint']}")

            return {
                'tls_data': tls_data,
                'http2_data': http2_data
            }

        except Exception as e:
            print(f"[TlsExtractor] ERROR: {e}")
            import traceback
            traceback.print_exc()
            print(f"[TlsExtractor] Using fallback data")
            return self._get_fallback_data()

    def _parse_akamai_settings(self, akamai_text):
        """Parse Akamai text to HTTP/2 SETTINGS"""
        # Format: "1:65536;2:0;4:6291456;6:262144;GREASE|15663105|0|m,a,s,p"
        if not akamai_text:
            return self._get_http2_settings()

        settings = {}
        parts = akamai_text.split('|')
        if len(parts) > 0:
            settings_str = parts[0]
            for setting in settings_str.split(';'):
                if ':' in setting:
                    try:
                        key, val = setting.split(':')
                        if key.isdigit():
                            setting_name = f'SETTINGS_{key}'
                            settings[setting_name] = int(val)
                    except:
                        pass

        # Map to standard names
        mapped = {}
        mapping = {
            'SETTINGS_1': 'SETTINGS_HEADER_TABLE_SIZE',
            'SETTINGS_2': 'SETTINGS_ENABLE_PUSH',
            'SETTINGS_3': 'SETTINGS_MAX_CONCURRENT_STREAMS',
            'SETTINGS_4': 'SETTINGS_INITIAL_WINDOW_SIZE',
            'SETTINGS_5': 'SETTINGS_MAX_FRAME_SIZE',
            'SETTINGS_6': 'SETTINGS_MAX_HEADER_LIST_SIZE'
        }

        for old_key, new_key in mapping.items():
            if old_key in settings:
                mapped[new_key] = settings[old_key]

        return mapped if mapped else self._get_http2_settings()

    def _get_cipher_name(self, cipher_id):
        """Get cipher suite name from ID"""
        cipher_names = {
            4865: 'TLS_AES_128_GCM_SHA256',
            4866: 'TLS_AES_256_GCM_SHA384',
            4867: 'TLS_CHACHA20_POLY1305_SHA256',
            49195: 'TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256',
            49199: 'TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256',
            49196: 'TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384',
            49200: 'TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384',
            52393: 'TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256',
            52392: 'TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256',
            49171: 'TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA',
            49172: 'TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA',
            156: 'TLS_RSA_WITH_AES_128_GCM_SHA256',
            157: 'TLS_RSA_WITH_AES_256_GCM_SHA384',
            47: 'TLS_RSA_WITH_AES_128_CBC_SHA',
            53: 'TLS_RSA_WITH_AES_256_CBC_SHA'
        }
        return cipher_names.get(cipher_id, f'UNKNOWN_{cipher_id}')

    def _get_extension_name(self, ext_id):
        """Get extension name from ID"""
        extension_names = {
            0: 'server_name',
            5: 'status_request',
            10: 'supported_groups',
            11: 'ec_point_formats',
            13: 'signature_algorithms',
            16: 'application_layer_protocol_negotiation',
            18: 'signed_certificate_timestamp',
            23: 'session_ticket',
            27: 'compress_certificate',
            35: 'session_ticket_tls',
            43: 'supported_versions',
            45: 'psk_key_exchange_modes',
            51: 'key_share',
            17613: 'application_settings',
            65037: 'encrypted_client_hello',
            65281: 'renegotiation_info'
        }
        return extension_names.get(ext_id, f'unknown_{ext_id}')

    def _get_curve_name(self, curve_id):
        """Get curve name from ID"""
        curve_names = {
            23: 'secp256r1',
            24: 'secp384r1',
            29: 'X25519',
            4588: 'GREASE'
        }
        return curve_names.get(curve_id, f'unknown_{curve_id}')

    def _get_fallback_data(self):
        """Fallback to hardcoded Chrome 136 defaults"""
        print(f"[TlsExtractor] Using fallback Chrome 136 defaults")

        tls_data = {
            'tls_version': 'TLS 1.3',
            'cipher_suites': self._get_chrome_cipher_suites(),
            'extensions': self._get_chrome_extensions(),
            'supported_groups': self._get_chrome_supported_groups(),
            'signature_algorithms': self._get_chrome_signature_algorithms()
        }

        http2_data = {
            'settings': self._get_http2_settings(),
            'akamai_fingerprint': self._generate_akamai_fingerprint()
        }

        return {
            'tls_data': tls_data,
            'http2_data': http2_data
        }

    def _get_chrome_cipher_suites(self):
        """
        Chrome TLS 1.3 default cipher suites (fallback)
        Based on Chrome 136+
        """
        return [
            {'id': 4865, 'name': 'TLS_AES_128_GCM_SHA256'},
            {'id': 4866, 'name': 'TLS_AES_256_GCM_SHA384'},
            {'id': 4867, 'name': 'TLS_CHACHA20_POLY1305_SHA256'},
            {'id': 49195, 'name': 'TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256'},
            {'id': 49199, 'name': 'TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256'},
            {'id': 49196, 'name': 'TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384'},
            {'id': 49200, 'name': 'TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384'},
            {'id': 52393, 'name': 'TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256'},
            {'id': 52392, 'name': 'TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256'},
            {'id': 49191, 'name': 'TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA'},
            {'id': 49171, 'name': 'TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA'},
            {'id': 49192, 'name': 'TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA'},
            {'id': 49172, 'name': 'TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA'},
            {'id': 156, 'name': 'TLS_RSA_WITH_AES_128_GCM_SHA256'},
            {'id': 157, 'name': 'TLS_RSA_WITH_AES_256_GCM_SHA384'},
            {'id': 47, 'name': 'TLS_RSA_WITH_AES_128_CBC_SHA'},
            {'id': 53, 'name': 'TLS_RSA_WITH_AES_256_CBC_SHA'}
        ]

    def _get_chrome_extensions(self):
        """
        Chrome TLS extensions
        """
        return [
            {'id': 0, 'name': 'server_name'},
            {'id': 10, 'name': 'supported_groups'},
            {'id': 11, 'name': 'ec_point_formats'},
            {'id': 13, 'name': 'signature_algorithms'},
            {'id': 16, 'name': 'application_layer_protocol_negotiation'},
            {'id': 18, 'name': 'signed_certificate_timestamp'},
            {'id': 22, 'name': 'encrypt_then_mac'},
            {'id': 23, 'name': 'extended_master_secret'},
            {'id': 27, 'name': 'compress_certificate'},
            {'id': 35, 'name': 'session_ticket'},
            {'id': 43, 'name': 'supported_versions'},
            {'id': 45, 'name': 'psk_key_exchange_modes'},
            {'id': 51, 'name': 'key_share'},
            {'id': 13172, 'name': 'next_protocol_negotiation'},
            {'id': 17513, 'name': 'application_settings'},
            {'id': 65281, 'name': 'renegotiation_info'}
        ]

    def _get_chrome_supported_groups(self):
        """
        Chrome supported groups (curves)
        """
        return [
            'X25519',
            'secp256r1',
            'secp384r1'
        ]

    def _get_chrome_signature_algorithms(self):
        """
        Chrome signature algorithms
        """
        return [
            'ecdsa_secp256r1_sha256',
            'rsa_pss_rsae_sha256',
            'rsa_pkcs1_sha256',
            'ecdsa_secp384r1_sha384',
            'rsa_pss_rsae_sha384',
            'rsa_pkcs1_sha384',
            'rsa_pss_rsae_sha512',
            'rsa_pkcs1_sha512'
        ]

    def _get_http2_settings(self):
        """
        Chrome HTTP/2 SETTINGS frame
        """
        return {
            'SETTINGS_HEADER_TABLE_SIZE': 65536,
            'SETTINGS_ENABLE_PUSH': 0,
            'SETTINGS_MAX_CONCURRENT_STREAMS': 1000,
            'SETTINGS_INITIAL_WINDOW_SIZE': 6291456,
            'SETTINGS_MAX_FRAME_SIZE': 16384,
            'SETTINGS_MAX_HEADER_LIST_SIZE': 262144
        }

    def _generate_akamai_fingerprint(self):
        """
        Generate Akamai HTTP/2 fingerprint
        Format: "1:65536;2:0;3:1000;4:6291456;5:16384;6:262144|15663105|0|m,a,s,p"
        """
        settings = self._get_http2_settings()

        # Format: SETTING_ID:VALUE
        parts = [
            f"1:{settings['SETTINGS_HEADER_TABLE_SIZE']}",
            f"2:{settings['SETTINGS_ENABLE_PUSH']}",
            f"3:{settings['SETTINGS_MAX_CONCURRENT_STREAMS']}",
            f"4:{settings['SETTINGS_INITIAL_WINDOW_SIZE']}",
            f"5:{settings['SETTINGS_MAX_FRAME_SIZE']}",
            f"6:{settings['SETTINGS_MAX_HEADER_LIST_SIZE']}"
        ]

        # Akamai format
        akamai_fp = ';'.join(parts) + '|15663105|0|m,a,s,p'

        return akamai_fp

    def generate_ja3_hash(self, tls_data):
        """
        Generate JA3 hash from TLS data

        Args:
            tls_data: TLS data dict

        Returns:
            str: JA3 hash (MD5)
        """
        # JA3 format: SSLVersion,Ciphers,Extensions,EllipticCurves,EllipticCurvePointFormats
        ssl_version = '771'  # TLS 1.2
        ciphers = ','.join([str(c['id']) for c in tls_data['cipher_suites']])
        extensions = ','.join([str(e['id']) for e in tls_data['extensions']])
        curves = ','.join(['29', '23', '24'])  # X25519, secp256r1, secp384r1
        point_formats = '0'  # uncompressed

        ja3_string = f"{ssl_version},{ciphers},{extensions},{curves},{point_formats}"
        ja3_hash = hashlib.md5(ja3_string.encode()).hexdigest()

        return ja3_hash

if __name__ == '__main__':
    print("[TlsExtractor] Test mode")
    print("[INFO] This module requires an active nodriver page")
    print("[INFO] Use via cookie_collector.py integration")

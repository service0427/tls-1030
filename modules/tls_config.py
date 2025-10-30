"""
TLS Configuration Builder - Build JA3/extra_fp for curl-cffi
"""

from curl_cffi.const import CurlSslVersion


class TlsConfig:
    @staticmethod
    def build_ja3_string(tls_data):
        """
        Build JA3 string from TLS data
        Format: SSLVersion,Ciphers,Extensions,EllipticCurves,EllipticCurvePointFormats

        Args:
            tls_data: TLS data from database

        Returns:
            str: JA3 string (or None if ja3_text exists in DB)
        """
        # Use ja3_text from DB if available
        ja3_text = tls_data.get('ja3_text')
        if ja3_text:
            return ja3_text

        # Otherwise build from components
        # 1. SSL Version (771 = TLS 1.2, 772 = TLS 1.3)
        tls_version = tls_data.get('tls_version', 'TLS 1.3')
        if '1.3' in str(tls_version):
            ssl_ver = '772'
        elif '1.2' in str(tls_version):
            ssl_ver = '771'
        else:
            ssl_ver = '771'

        # 2. Cipher Suites (filter out GREASE)
        ciphers = []
        for cipher in tls_data.get('cipher_suites', []):
            cipher_id = cipher.get('id')
            cipher_name = cipher.get('name', '')
            if cipher_id and 'GREASE' not in cipher_name:
                ciphers.append(str(cipher_id))
        cipher_str = '-'.join(ciphers)

        # 3. Extensions (filter out GREASE)
        extensions = []
        for ext in tls_data.get('extensions', []):
            ext_id = ext.get('id')
            ext_name = ext.get('name', '')
            if ext_id and 'GREASE' not in ext_name:
                extensions.append(str(ext_id))
        ext_str = '-'.join(extensions)

        # 4. Supported Groups (Elliptic Curves)
        # Map names to IDs
        curve_map = {
            'X25519': '29',
            'x25519': '29',
            'secp256r1': '23',
            'prime256v1': '23',
            'secp384r1': '24',
            'secp521r1': '25',
            'X25519Kyber768Draft00': '25497',  # Hybrid PQC
        }

        groups = []
        for group in tls_data.get('supported_groups', []):
            if 'GREASE' in group:
                continue
            group_id = curve_map.get(group, '')
            if group_id:
                groups.append(group_id)
        group_str = '-'.join(groups)

        # 5. EC Point Formats (usually just "0" for uncompressed)
        point_format = '0'

        # Build JA3 string
        ja3 = f"{ssl_ver},{cipher_str},{ext_str},{group_str},{point_format}"
        return ja3

    @staticmethod
    def build_extra_fp(tls_data):
        """
        Build extra_fp from TLS data for fine-tuning

        Args:
            tls_data: TLS data from database

        Returns:
            dict: extra_fp configuration
        """
        extra_fp = {}

        # TLS version
        tls_version = tls_data.get('tls_version', 'TLS 1.3')
        if '1.3' in str(tls_version):
            extra_fp['tls_min_version'] = CurlSslVersion.TLSv1_3
        elif '1.2' in str(tls_version):
            extra_fp['tls_min_version'] = CurlSslVersion.TLSv1_2

        # Enable GREASE and extension permutation
        extra_fp['tls_grease'] = True
        extra_fp['tls_permute_extensions'] = True

        # Signature algorithms
        sig_algs = tls_data.get('signature_algorithms', [])
        if sig_algs:
            extra_fp['tls_signature_algorithms'] = sig_algs

        # Certificate compression (default: brotli)
        extra_fp['tls_cert_compression'] = 'brotli'

        return extra_fp

    @staticmethod
    def build_headers(chrome_version, page_num=1, referer=None, cookie_header=''):
        """
        Build HTTP headers for request

        Args:
            chrome_version: Chrome version string (e.g., "142.0.7444.60")
            page_num: Page number (1 for HTML, 2+ for RSC)
            referer: Referer URL (for page 2+)
            cookie_header: Cookie header string

        Returns:
            dict: HTTP headers
        """
        major_version = chrome_version.split('.')[0]

        if page_num == 1:
            # Page 1: Regular HTML request
            headers = {
                'User-Agent': f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version}.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://www.coupang.com/',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
                'sec-ch-ua': f'"Google Chrome";v="{major_version}", "Chromium";v="{major_version}", "Not-A.Brand";v="99"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"'
            }
            # Only add Cookie header if cookie_header is provided
            if cookie_header:
                headers['Cookie'] = cookie_header
            return headers
        else:
            # Page 2+: Next.js RSC request
            headers = {
                'User-Agent': f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version}.0.0.0 Safari/537.36',
                'Accept': 'text/x-component',
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': referer,
                'rsc': '1',
                'next-router-state-tree': '%5B%22%22%2C%7B%22children%22%3A%5B%22srp%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%2Cnull%2Cnull%5D%7D%2Cnull%2Cnull%5D%7D%2Cnull%2Cnull%2Ctrue%5D',
                'next-url': '/srp',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'sec-ch-ua': f'"Chromium";v="{major_version}", "Google Chrome";v="{major_version}", "Not_A Brand";v="99"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"'
            }
            # Only add Cookie header if cookie_header is provided
            if cookie_header:
                headers['Cookie'] = cookie_header
            return headers

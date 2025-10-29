"""
TLS Configuration Builder - Build extra_fp for curl-cffi
"""

from curl_cffi.const import CurlSslVersion


class TlsConfig:
    @staticmethod
    def build_extra_fp(tls_data):
        """
        Build minimal extra_fp from TLS data
        (curl_cffi 0.13.0 supports limited parameters)

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

        # Enable GREASE and extension permutation for Chrome 110+
        extra_fp['tls_grease'] = True
        extra_fp['tls_permute_extensions'] = True

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

"""
Cookie Formatter - Common cookie format conversion utilities
Shared by PC (nodriver) and Mobile (Appium) collectors
"""

from typing import List, Dict, Set, Optional, Any


class CookieFormatter:
    """Format cookies to standardized structure for database storage"""

    @staticmethod
    def format_webdriver_cookie(cookie: Dict) -> Dict:
        """
        Format Appium/Selenium WebDriver cookie to standard format

        Args:
            cookie: WebDriver cookie dict

        Returns:
            dict: Standardized cookie format
        """
        return {
            'name': cookie.get('name'),
            'value': cookie.get('value'),
            'domain': cookie.get('domain', '.coupang.com'),
            'path': cookie.get('path', '/'),
            'expires': cookie.get('expiry'),  # WebDriver uses 'expiry'
            'httpOnly': cookie.get('httpOnly', False),
            'secure': cookie.get('secure', False),
            'sameSite': cookie.get('sameSite'),
        }

    @staticmethod
    def format_nodriver_cookie(cookie: Any) -> Dict:
        """
        Format nodriver cookie object to standard format

        Args:
            cookie: nodriver cookie object or dict

        Returns:
            dict: Standardized cookie format
        """
        if isinstance(cookie, dict):
            # Already a dict, standardize keys
            return {
                'name': cookie.get('name'),
                'value': cookie.get('value'),
                'domain': cookie.get('domain'),
                'path': cookie.get('path'),
                'expires': cookie.get('expires'),
                'httpOnly': cookie.get('httpOnly', False),
                'secure': cookie.get('secure', False),
                'sameSite': cookie.get('sameSite'),
            }
        else:
            # Object format (nodriver cookie object)
            return {
                'name': cookie.name,
                'value': cookie.value,
                'domain': cookie.domain,
                'path': cookie.path,
                'expires': cookie.expires if hasattr(cookie, 'expires') else None,
                'httpOnly': cookie.http_only if hasattr(cookie, 'http_only') else False,
                'secure': cookie.secure if hasattr(cookie, 'secure') else False,
                'sameSite': str(cookie.same_site) if hasattr(cookie, 'same_site') else None,
            }

    @staticmethod
    def parse_js_cookies(cookie_string: str, default_domain: str = '.coupang.com') -> List[Dict]:
        """
        Parse JavaScript document.cookie string to standard format

        Args:
            cookie_string: JavaScript cookie string (e.g., "name1=value1; name2=value2")
            default_domain: Default domain for parsed cookies

        Returns:
            list: List of standardized cookie dicts
        """
        cookies = []
        if not cookie_string:
            return cookies

        for cookie_pair in cookie_string.split('; '):
            if '=' in cookie_pair:
                name, value = cookie_pair.split('=', 1)
                cookies.append({
                    'name': name.strip(),
                    'value': value.strip(),
                    'domain': default_domain,
                    'path': '/',
                    'expires': None,
                    'httpOnly': False,
                    'secure': True,
                    'sameSite': 'None',
                })

        return cookies

    @staticmethod
    def merge_cookie_lists(
        existing_cookies: List[Dict],
        new_cookies: List[Dict],
        cookie_names: Optional[Set[str]] = None
    ) -> tuple[List[Dict], Set[str]]:
        """
        Merge new cookies into existing list, updating or adding as needed

        Args:
            existing_cookies: Current cookie list
            new_cookies: New cookies to merge
            cookie_names: Optional set of existing cookie names (for efficiency)

        Returns:
            tuple: (merged_cookies, updated_cookie_names)
        """
        if cookie_names is None:
            cookie_names = {c['name'] for c in existing_cookies}

        merged = existing_cookies.copy()

        for new_cookie in new_cookies:
            cookie_name = new_cookie['name']

            # Find existing cookie
            existing_idx = None
            for idx, existing in enumerate(merged):
                if existing['name'] == cookie_name:
                    existing_idx = idx
                    break

            if existing_idx is not None:
                # Update existing
                merged[existing_idx] = new_cookie
            else:
                # Add new
                merged.append(new_cookie)
                cookie_names.add(cookie_name)

        return merged, cookie_names

    @staticmethod
    def collect_webdriver_cookies(driver, js_cookie_string: Optional[str] = None) -> List[Dict]:
        """
        Collect and format cookies from WebDriver (Appium/Selenium)

        Args:
            driver: WebDriver instance
            js_cookie_string: Optional JavaScript document.cookie string

        Returns:
            list: Standardized cookie list
        """
        cookies_data = []
        cookie_names = set()

        # 1. Get WebDriver cookies (full info)
        try:
            cookies_wd = driver.get_cookies()
            for cookie in cookies_wd:
                formatted = CookieFormatter.format_webdriver_cookie(cookie)
                cookies_data.append(formatted)
                cookie_names.add(formatted['name'])
        except Exception as e:
            print(f"[CookieFormatter] Warning: Failed to get WebDriver cookies: {e}")

        # 2. Parse JavaScript cookies (add missing only)
        if js_cookie_string:
            js_cookies = CookieFormatter.parse_js_cookies(js_cookie_string)
            for js_cookie in js_cookies:
                if js_cookie['name'] not in cookie_names:
                    cookies_data.append(js_cookie)
                    cookie_names.add(js_cookie['name'])

        return cookies_data

    @staticmethod
    def format_cookie_list(cookies: List[Any], formatter_type: str = 'nodriver') -> List[Dict]:
        """
        Format a list of cookies to standard format

        Args:
            cookies: List of cookie objects/dicts
            formatter_type: 'nodriver' or 'webdriver'

        Returns:
            list: Standardized cookie list
        """
        if formatter_type == 'webdriver':
            formatter_func = CookieFormatter.format_webdriver_cookie
        else:
            formatter_func = CookieFormatter.format_nodriver_cookie

        formatted_cookies = []
        for cookie in cookies:
            try:
                formatted = formatter_func(cookie)
                formatted_cookies.append(formatted)
            except Exception as e:
                print(f"[CookieFormatter] Warning: Failed to format cookie: {e}")

        return formatted_cookies

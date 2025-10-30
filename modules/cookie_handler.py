"""
Cookie Handler - Convert cookies between different formats
"""


class CookieHandler:
    @staticmethod
    def to_header_string(cookies):
        """
        Convert cookie list to header string

        Args:
            cookies: List of cookie dicts

        Returns:
            str: Cookie header string (e.g., "name1=value1; name2=value2")
        """
        cookie_pairs = []
        for cookie in cookies:
            name = cookie.get('name', '')
            value = cookie.get('value', '')
            if name and value:
                cookie_pairs.append(f"{name}={value}")
        return '; '.join(cookie_pairs)

    @staticmethod
    def to_dict(cookies):
        """
        Convert cookie list to dictionary

        Args:
            cookies: List of cookie dicts or dict or JSON string

        Returns:
            dict: {name: value, ...}
        """
        import json

        # Handle JSON string
        if isinstance(cookies, str):
            try:
                cookies = json.loads(cookies)
            except:
                return {}

        # Already a dict
        if isinstance(cookies, dict):
            return cookies

        # Convert list to dict
        cookie_dict = {}
        for cookie in cookies:
            if isinstance(cookie, dict):
                name = cookie.get('name', '')
                value = cookie.get('value', '')
                if name and value:
                    cookie_dict[name] = value
            elif isinstance(cookie, str):
                # Handle "name=value" format
                if '=' in cookie:
                    name, value = cookie.split('=', 1)
                    cookie_dict[name.strip()] = value.strip()

        return cookie_dict

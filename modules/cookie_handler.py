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
            cookies: List of cookie dicts

        Returns:
            dict: {name: value, ...}
        """
        cookie_dict = {}
        for cookie in cookies:
            name = cookie.get('name', '')
            value = cookie.get('value', '')
            if name and value:
                cookie_dict[name] = value
        return cookie_dict

"""
File Manager - Handle all file I/O operations
"""

import json
from pathlib import Path
from datetime import datetime


class FileManager:
    def __init__(self, base_dir='output'):
        """
        Args:
            base_dir: Base directory for outputs (default: 'output')
        """
        self.base_dir = Path(base_dir)
        self.html_dir = self.base_dir / 'html'
        self.json_dir = self.base_dir / 'json'
        self.logs_dir = self.base_dir / 'logs'

        # Create directories if not exist
        self.html_dir.mkdir(parents=True, exist_ok=True)
        self.json_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def save_html(self, content, filename):
        """
        Save HTML content

        Args:
            content: HTML string
            filename: Filename (without path)

        Returns:
            str: Full file path
        """
        filepath = self.html_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return str(filepath)

    def save_json(self, data, filename):
        """
        Save JSON data

        Args:
            data: Dict or list
            filename: Filename (without path)

        Returns:
            str: Full file path
        """
        filepath = self.json_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return str(filepath)

    def save_cookies(self, cookies, chrome_version, timestamp=None):
        """
        Save cookies to JSON file

        Args:
            cookies: List of cookie dicts
            chrome_version: Chrome version string
            timestamp: Optional timestamp (default: current time)

        Returns:
            str: Full file path
        """
        if timestamp is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        filename = f'cookies_chrome{chrome_version}_{timestamp}.json'
        return self.save_json(cookies, filename)

    def save_request_headers(self, headers, chrome_version, timestamp=None):
        """
        Save request headers to JSON file

        Args:
            headers: Dict of headers
            chrome_version: Chrome version string
            timestamp: Optional timestamp (default: current time)

        Returns:
            str: Full file path
        """
        if timestamp is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        filename = f'request_headers_chrome{chrome_version}_{timestamp}.json'
        filepath = self.logs_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(headers, f, indent=2, ensure_ascii=False)
        return str(filepath)

    def save_page(self, content, page_num, chrome_version, ext='html'):
        """
        Save crawled page content

        Args:
            content: Page content string
            page_num: Page number
            chrome_version: Chrome version string
            ext: File extension (default: 'html')

        Returns:
            str: Full file path
        """
        major_version = chrome_version.split('.')[0]
        filename = f'page_{page_num}_chrome{major_version}.{ext}'

        if ext in ['html', 'htm']:
            return self.save_html(content, filename)
        else:
            # For RSC or other text formats
            filepath = self.html_dir / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return str(filepath)

    def save_results(self, results, filename):
        """
        Save crawling results summary

        Args:
            results: Results dict
            filename: Filename (without path)

        Returns:
            str: Full file path
        """
        return self.save_json(results, filename)

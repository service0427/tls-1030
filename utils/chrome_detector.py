"""
Chrome Version Detector
- Detect system-installed Chrome
- Scan chrome-versions/files directory
- Verify chrome.exe exists
- Extract version information
"""

import os
import glob
import re
import subprocess
from pathlib import Path

class ChromeDetector:
    def __init__(self, chrome_versions_path=None):
        """
        Args:
            chrome_versions_path: Path to chrome-versions/files directory
        """
        if chrome_versions_path is None:
            # Default path
            chrome_versions_path = os.getenv(
                'CHROME_VERSIONS_PATH',
                r'D:\dev\git\local-packet-coupang\chrome-versions\files'
            )

        self.chrome_versions_path = Path(chrome_versions_path)

        if not self.chrome_versions_path.exists():
            raise FileNotFoundError(f"Chrome versions path not found: {self.chrome_versions_path}")

    def get_system_chrome(self):
        """
        Get system-installed Chrome information

        Returns:
            dict: System Chrome info or None if not found
        """
        # Common Chrome installation paths
        possible_paths = [
            Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
            Path(r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'),
            Path(os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe')),
        ]

        for chrome_path in possible_paths:
            if chrome_path.exists():
                version = 'Unknown'

                # Method 1: Check version folders in parent directory
                try:
                    app_dir = chrome_path.parent
                    version_dirs = [d for d in app_dir.iterdir() if d.is_dir() and re.match(r'\d+\.\d+\.\d+\.\d+', d.name)]
                    if version_dirs:
                        # Get the latest version
                        version_dirs.sort(key=lambda x: [int(n) for n in x.name.split('.')], reverse=True)
                        version = version_dirs[0].name
                except Exception:
                    pass

                # Method 2: Use PowerShell to get file version
                if version == 'Unknown':
                    try:
                        ps_cmd = f'(Get-Item "{chrome_path}").VersionInfo.FileVersion'
                        result = subprocess.run(
                            ['powershell', '-Command', ps_cmd],
                            capture_output=True,
                            text=True,
                            timeout=3
                        )
                        version_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', result.stdout)
                        if version_match:
                            version = version_match.group(1)
                    except Exception:
                        pass

                # Method 3: Run chrome.exe --version (may not work in some cases)
                if version == 'Unknown':
                    try:
                        result = subprocess.run(
                            [str(chrome_path), '--version'],
                            capture_output=True,
                            text=True,
                            timeout=2,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                        )
                        version_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', result.stdout)
                        if version_match:
                            version = version_match.group(1)
                    except Exception:
                        pass

                return {
                    'version': version,
                    'folder': 'System Chrome',
                    'path': str(chrome_path),
                    'available': True,
                    'is_system': True
                }

        return None

    def list_versions(self):
        """
        List all available Chrome versions (system Chrome first)

        Returns:
            list: [{'version': '142.0.x.x', 'path': '...', 'available': True, 'is_system': True}, ...]
        """
        versions = []

        # 1. Add system Chrome first
        system_chrome = self.get_system_chrome()
        if system_chrome:
            versions.append(system_chrome)

        # 2. Scan subdirectories for portable Chrome versions
        for chrome_dir in self.chrome_versions_path.iterdir():
            if not chrome_dir.is_dir():
                continue

            # Extract version from folder name (e.g., chrome-136.0.7103.113)
            match = re.match(r'chrome-([\d.]+)', chrome_dir.name)
            if not match:
                continue

            version = match.group(1)

            # Try multiple possible paths
            possible_paths = [
                chrome_dir / 'chrome-win64' / 'chrome.exe',  # Standard structure
                chrome_dir / 'chrome.exe',                    # Direct
                chrome_dir / 'Application' / 'chrome.exe',    # Installed structure
            ]

            chrome_exe = None
            for path in possible_paths:
                if path.exists():
                    chrome_exe = path
                    break

            if chrome_exe is None:
                chrome_exe = possible_paths[0]  # Default to first path

            versions.append({
                'version': version,
                'folder': chrome_dir.name,
                'path': str(chrome_exe),
                'available': chrome_exe.exists(),
                'is_system': False
            })

        # Sort portable versions by version (newest first), but keep system Chrome at position 0
        if len(versions) > 1:
            portable_versions = versions[1:]
            portable_versions.sort(key=lambda x: [int(n) for n in x['version'].split('.')], reverse=True)
            versions = [versions[0]] + portable_versions

        return versions

    def get_version(self, version_query):
        """
        Get specific Chrome version

        Args:
            version_query: Version string (e.g., 'system', '136', '136.0', '136.0.7103.113', 'latest')

        Returns:
            dict: Version info or None if not found
        """
        versions = self.list_versions()

        if version_query == 'system':
            # Return system Chrome
            for v in versions:
                if v.get('is_system', False) and v['available']:
                    return v
            return None

        if version_query == 'latest':
            # Return newest available version
            for v in versions:
                if v['available']:
                    return v
            return None

        # Match version query
        for v in versions:
            if v['version'].startswith(version_query):
                return v

        return None

    def print_versions(self):
        """Print all available Chrome versions (system Chrome first)"""
        versions = self.list_versions()

        print(f"Chrome Versions Path: {self.chrome_versions_path}")
        print(f"Total {len(versions)} versions found:\n")

        for i, v in enumerate(versions, 1):
            status = "OK" if v['available'] else "MISSING"
            if v.get('is_system', False):
                print(f"  {i:2d}. Chrome {v['version']:<20} [SYSTEM] [{status}]")
            else:
                print(f"  {i:2d}. Chrome {v['version']:<20} [{status}]")

        return versions

if __name__ == '__main__':
    detector = ChromeDetector()
    detector.print_versions()

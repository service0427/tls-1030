"""
BrowserStack Device Selector Module
- Fetch device list from BrowserStack API (cache for 24 hours)
- 4-step selection: Manufacturer → Model → Browser → OS Version
- Save selection history for tracking progress
"""

import os
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class DeviceSelector:
    """BrowserStack device selector with 4-step selection and history tracking"""

    def __init__(self, username: str, access_key: str):
        self.username = username
        self.access_key = access_key
        self.api_url = "https://api.browserstack.com/automate/browsers.json"

        # Cache paths
        self.config_dir = Path(__file__).parent.parent / 'config'
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.cache_file = self.config_dir / 'browserstack_devices.json'
        self.history_file = self.config_dir / 'device_history.json'

        # Cache validity: 24 hours
        self.cache_duration = timedelta(hours=24)

    def fetch_devices(self, force_refresh: bool = False) -> List[Dict]:
        """
        Fetch device list from BrowserStack API or cache

        Args:
            force_refresh: Force refresh cache even if valid

        Returns:
            List of device configurations
        """
        # Check cache validity
        if not force_refresh and self.cache_file.exists():
            cache_age = datetime.now() - datetime.fromtimestamp(self.cache_file.stat().st_mtime)

            if cache_age < self.cache_duration:
                print(f"[DeviceSelector] Using cached devices (age: {cache_age.seconds // 3600}h)")
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)

        # Fetch from API
        print("[DeviceSelector] Fetching devices from BrowserStack API...")

        try:
            response = requests.get(
                self.api_url,
                auth=(self.username, self.access_key),
                timeout=30
            )
            response.raise_for_status()

            devices = response.json()

            # Save to cache
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(devices, f, indent=2, ensure_ascii=False)

            print(f"[DeviceSelector] Cached {len(devices)} devices")
            return devices

        except Exception as e:
            print(f"[ERROR] Failed to fetch devices: {e}")

            # Fallback to cache if exists
            if self.cache_file.exists():
                print("[WARNING] Using stale cache")
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)

            raise

    def classify_devices(self, devices: List[Dict]) -> Dict:
        """
        Classify devices by manufacturer, model, browser, os_version

        Structure:
        {
            "samsung": {
                "Galaxy S23": {
                    "chrome": {
                        "13.0": {device_config},
                        "14.0": {device_config}
                    }
                }
            },
            "apple": {...},
            "google": {...}
        }
        """
        classified = {}

        for device in devices:
            # Only process mobile devices
            if device.get('device') is None:
                continue

            device_name = device.get('device', '')
            browser = device.get('browser', device.get('browserName', '')).lower()
            os_version = device.get('os_version', device.get('os', ''))

            # Skip empty entries
            if not device_name or not browser or not os_version:
                continue

            # Determine manufacturer
            manufacturer = self._get_manufacturer(device_name)

            # Normalize model name
            model = self._normalize_model(device_name, manufacturer)

            # Build hierarchy
            if manufacturer not in classified:
                classified[manufacturer] = {}

            if model not in classified[manufacturer]:
                classified[manufacturer][model] = {}

            if browser not in classified[manufacturer][model]:
                classified[manufacturer][model][browser] = {}

            # Store device config
            classified[manufacturer][model][browser][os_version] = device

        return classified

    def _get_manufacturer(self, device_name: str) -> str:
        """Determine manufacturer from device name"""
        device_lower = device_name.lower()

        if 'samsung' in device_lower or 'galaxy' in device_lower:
            return 'samsung'
        elif 'iphone' in device_lower or 'ipad' in device_lower:
            return 'apple'
        elif 'pixel' in device_lower or 'nexus' in device_lower:
            return 'google'
        elif 'xiaomi' in device_lower or 'redmi' in device_lower or 'poco' in device_lower:
            return 'xiaomi'
        elif 'oneplus' in device_lower:
            return 'oneplus'
        elif 'oppo' in device_lower:
            return 'oppo'
        elif 'vivo' in device_lower:
            return 'vivo'
        elif 'huawei' in device_lower:
            return 'huawei'
        elif 'motorola' in device_lower or 'moto' in device_lower:
            return 'motorola'
        else:
            return 'other'

    def _normalize_model(self, device_name: str, manufacturer: str) -> str:
        """Normalize model name for consistency"""
        # Remove manufacturer prefix
        model = device_name

        prefixes = [
            'Samsung ', 'Apple ', 'Google ', 'Xiaomi ', 'OnePlus ',
            'Oppo ', 'Vivo ', 'Huawei ', 'Motorola '
        ]

        for prefix in prefixes:
            if model.startswith(prefix):
                model = model[len(prefix):]
                break

        return model.strip()

    def select_device_interactive(self, classified_devices: Dict) -> Optional[Dict]:
        """
        Interactive 4-step device selection

        Steps:
        1. Select manufacturer (Samsung, Apple, Google, etc.)
        2. Select model (Galaxy S23, iPhone 15, etc.)
        3. Select browser (Chrome, Safari, etc.)
        4. Select OS version (13.0, 14.0, etc.)

        Returns:
            Selected device configuration or None if cancelled
        """
        print("\n" + "=" * 60)
        print("BrowserStack Device Selection (4 Steps)")
        print("=" * 60 + "\n")

        # Step 1: Select Manufacturer
        print("[Step 1/4] Select Manufacturer:")
        manufacturers = sorted(classified_devices.keys())

        for idx, manufacturer in enumerate(manufacturers, 1):
            model_count = len(classified_devices[manufacturer])
            print(f"  [{idx}] {manufacturer.capitalize()} ({model_count} models)")

        print(f"  [0] Cancel")

        try:
            choice = input("\nSelect manufacturer (number): ").strip()
            if choice == '0':
                return None

            manufacturer_idx = int(choice) - 1
            if manufacturer_idx < 0 or manufacturer_idx >= len(manufacturers):
                print("[ERROR] Invalid selection")
                return None

            selected_manufacturer = manufacturers[manufacturer_idx]
        except (ValueError, KeyboardInterrupt):
            print("\n[CANCELLED]")
            return None

        # Step 2: Select Model
        print(f"\n[Step 2/4] Select Model ({selected_manufacturer.capitalize()}):")
        models = sorted(classified_devices[selected_manufacturer].keys())

        for idx, model in enumerate(models, 1):
            print(f"  [{idx}] {model}")

        print(f"  [0] Back")

        try:
            choice = input("\nSelect model (number): ").strip()
            if choice == '0':
                return self.select_device_interactive(classified_devices)

            model_idx = int(choice) - 1
            if model_idx < 0 or model_idx >= len(models):
                print("[ERROR] Invalid selection")
                return None

            selected_model = models[model_idx]
        except (ValueError, KeyboardInterrupt):
            print("\n[CANCELLED]")
            return None

        # Step 3: Select Browser
        print(f"\n[Step 3/4] Select Browser ({selected_model}):")
        browsers = sorted(classified_devices[selected_manufacturer][selected_model].keys())

        for idx, browser in enumerate(browsers, 1):
            os_count = len(classified_devices[selected_manufacturer][selected_model][browser])
            print(f"  [{idx}] {browser.upper()} ({os_count} OS versions)")

        print(f"  [0] Back")

        try:
            choice = input("\nSelect browser (number): ").strip()
            if choice == '0':
                return self.select_device_interactive(classified_devices)

            browser_idx = int(choice) - 1
            if browser_idx < 0 or browser_idx >= len(browsers):
                print("[ERROR] Invalid selection")
                return None

            selected_browser = browsers[browser_idx]
        except (ValueError, KeyboardInterrupt):
            print("\n[CANCELLED]")
            return None

        # Step 4: Select OS Version
        print(f"\n[Step 4/4] Select OS Version ({selected_browser.upper()}):")
        os_versions = sorted(
            classified_devices[selected_manufacturer][selected_model][selected_browser].keys(),
            key=lambda x: [int(n) if n.isdigit() else n for n in x.split('.')],
            reverse=True
        )

        for idx, os_version in enumerate(os_versions, 1):
            print(f"  [{idx}] {os_version}")

        print(f"  [0] Back")

        try:
            choice = input("\nSelect OS version (number): ").strip()
            if choice == '0':
                return self.select_device_interactive(classified_devices)

            os_idx = int(choice) - 1
            if os_idx < 0 or os_idx >= len(os_versions):
                print("[ERROR] Invalid selection")
                return None

            selected_os_version = os_versions[os_idx]
        except (ValueError, KeyboardInterrupt):
            print("\n[CANCELLED]")
            return None

        # Get final device config
        device_config = classified_devices[selected_manufacturer][selected_model][selected_browser][selected_os_version]

        # Add selection metadata
        device_config['_selection'] = {
            'manufacturer': selected_manufacturer,
            'model': selected_model,
            'browser': selected_browser,
            'os_version': selected_os_version,
            'selected_at': datetime.now().isoformat()
        }

        # Display selection summary
        print("\n" + "=" * 60)
        print("Selected Device:")
        print("=" * 60)
        print(f"  Manufacturer: {selected_manufacturer.capitalize()}")
        print(f"  Model:        {selected_model}")
        print(f"  Browser:      {selected_browser.upper()}")
        print(f"  OS Version:   {selected_os_version}")
        print(f"  Device Name:  {device_config.get('device', 'N/A')}")
        print("=" * 60 + "\n")

        return device_config

    def save_history(self, device_config: Dict) -> int:
        """
        Save device selection to history with auto-incrementing ID

        Returns:
            int: Selection ID
        """
        history = []

        # Load existing history
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except:
                history = []

        # Get next selection ID
        if history:
            max_id = max(entry.get('selection_id', 0) for entry in history)
            selection_id = max_id + 1
        else:
            selection_id = 1

        # Add new selection
        history_entry = {
            'selection_id': selection_id,
            'timestamp': datetime.now().isoformat(),
            'manufacturer': device_config['_selection']['manufacturer'],
            'model': device_config['_selection']['model'],
            'browser': device_config['_selection']['browser'],
            'os_version': device_config['_selection']['os_version'],
            'device_name': device_config.get('device', 'Unknown'),
            'os': device_config.get('os', device_config.get('os_version', 'Unknown')),
            'real_mobile': device_config.get('real_mobile', device_config.get('realMobile', False))
        }

        history.append(history_entry)

        # Save history (keep last 100 entries)
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(history[-100:], f, indent=2, ensure_ascii=False)

        print(f"[DeviceSelector] Selection saved as #{selection_id} (total: {len(history)})")
        return selection_id

    def print_history(self, limit: int = 10):
        """Print device selection history with selection IDs"""
        if not self.history_file.exists():
            print("[INFO] No selection history found")
            return

        with open(self.history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)

        if not history:
            print("[INFO] No selection history found")
            return

        print("\n" + "=" * 60)
        print(f"Device Selection History (Last {min(limit, len(history))})")
        print("=" * 60 + "\n")

        # Show most recent entries
        recent_entries = history[-limit:]
        for entry in reversed(recent_entries):
            selection_id = entry.get('selection_id', '?')
            timestamp = datetime.fromisoformat(entry['timestamp'])
            print(f"[#{selection_id}] {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"    {entry['manufacturer'].capitalize()} {entry['model']}")
            print(f"    {entry['browser'].upper()} / OS {entry['os_version']}")
            print(f"    Device: {entry['device_name']}")
            print()

        print("=" * 60)
        print(f"Use: python main-mobile.py --device <ID> --search \"keyword\"")
        print("=" * 60 + "\n")

    def get_last_selection(self) -> Optional[Dict]:
        """Get last selected device configuration"""
        if not self.history_file.exists():
            return None

        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)

            if not history:
                return None

            # Return last entry
            return history[-1]
        except:
            return None

    def get_selection_by_id(self, selection_id: int) -> Optional[Dict]:
        """
        Get device configuration by selection ID

        Args:
            selection_id: Selection ID from history

        Returns:
            dict: Device configuration or None if not found
        """
        if not self.history_file.exists():
            return None

        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)

            # Find entry by selection_id
            for entry in history:
                if entry.get('selection_id') == selection_id:
                    return entry

            return None
        except:
            return None


def test_device_selector():
    """Test device selector module"""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    username = os.getenv("BROWSERSTACK_USERNAME", "bsuser_wHW2oU")
    access_key = os.getenv("BROWSERSTACK_ACCESS_KEY", "fuymXXoQNhshiN5BsZhp")

    selector = DeviceSelector(username, access_key)

    # Fetch devices
    devices = selector.fetch_devices()
    print(f"\n[INFO] Total devices: {len(devices)}")

    # Classify devices
    classified = selector.classify_devices(devices)

    print(f"\n[INFO] Manufacturers: {', '.join(sorted(classified.keys()))}")

    # Show statistics
    total_configs = 0
    for manufacturer, models in classified.items():
        model_count = len(models)
        config_count = sum(
            len(browsers[browser])
            for model in models.values()
            for browsers in [model]
            for browser in browsers
        )
        total_configs += config_count
        print(f"  {manufacturer.capitalize()}: {model_count} models, {config_count} configurations")

    print(f"\n[INFO] Total configurations: {total_configs}")

    # Interactive selection
    print("\n[TEST] Starting interactive selection...\n")
    selected = selector.select_device_interactive(classified)

    if selected:
        print("\n[SUCCESS] Device selected!")
        selector.save_history(selected)

        # Show history
        selector.print_history(5)
    else:
        print("\n[INFO] Selection cancelled")


if __name__ == '__main__':
    test_device_selector()

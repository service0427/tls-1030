"""
TLS-1030 Mobile Cookie & TLS Collector (BrowserStack Local + Appium)
- BrowserStack Local tunnel for IP consistency
- Real mobile device testing via Appium
- 4-step device selection (Manufacturer → Model → Browser → OS)
- TLS fingerprint + Cookie collection
- Selection history tracking
- DB upload with main-pc.py compatible format
"""

import argparse
import sys
import os
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import warnings

# Load .env file
load_dotenv()

# Suppress warnings
if sys.platform == 'win32':
    warnings.filterwarnings('ignore', category=ResourceWarning)

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from modules import DbManager, FileManager
from config import TIMEOUTS
from utils.device_selector import DeviceSelector

# BrowserStack credentials
BROWSERSTACK_USERNAME = os.getenv("BROWSERSTACK_USERNAME", "bsuser_wHW2oU")
BROWSERSTACK_ACCESS_KEY = os.getenv("BROWSERSTACK_ACCESS_KEY", "fuymXXoQNhshiN5BsZhp")
BROWSERSTACK_HUB = f"https://{BROWSERSTACK_USERNAME}:{BROWSERSTACK_ACCESS_KEY}@hub-cloud.browserstack.com/wd/hub"

# BrowserStack Local binary path
BSLOCAL_PATH = Path(__file__).parent / 'tools' / 'BrowserStackLocal.exe'


class BrowserStackLocalManager:
    """BrowserStack Local tunnel manager"""

    def __init__(self, access_key, binary_path=None):
        self.access_key = access_key
        self.binary_path = binary_path or BSLOCAL_PATH
        self.process = None

    def download_binary(self):
        """Download BrowserStack Local binary for Windows"""
        print("\n[BrowserStack Local] Downloading binary...")

        # Create tools directory
        tools_dir = self.binary_path.parent
        tools_dir.mkdir(parents=True, exist_ok=True)

        # Download URL for Windows
        download_url = "https://www.browserstack.com/browserstack-local/BrowserStackLocal-win32.zip"

        try:
            import urllib.request
            import zipfile

            zip_path = tools_dir / 'BrowserStackLocal.zip'

            print(f"  Downloading from: {download_url}")
            urllib.request.urlretrieve(download_url, zip_path)

            print(f"  Extracting to: {tools_dir}")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(tools_dir)

            # Remove zip file
            zip_path.unlink()

            print(f"  ✅ Binary downloaded: {self.binary_path}")
            return True

        except Exception as e:
            print(f"  ❌ Download failed: {e}")
            return False

    def start(self, force_local=True, verbose=False):
        """Start BrowserStack Local tunnel"""

        # Check if binary exists
        if not self.binary_path.exists():
            print(f"[ERROR] BrowserStack Local binary not found: {self.binary_path}")
            print("\nDownloading binary automatically...")
            if not self.download_binary():
                print("\n[ERROR] Failed to download binary. Please download manually from:")
                print("        https://www.browserstack.com/local-testing/automate")
                return False

        print(f"\n[BrowserStack Local] Starting tunnel...")
        print(f"  Binary: {self.binary_path}")

        # Build command
        cmd = [
            str(self.binary_path),
            '--key', self.access_key,
        ]

        if force_local:
            cmd.append('--force-local')

        if verbose:
            cmd.append('--verbose')

        try:
            # Start process
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Wait for tunnel to be ready
            print("  Waiting for tunnel connection...")
            max_wait = 30
            for i in range(max_wait):
                time.sleep(1)

                # Check if process is still running
                if self.process.poll() is not None:
                    stdout, stderr = self.process.communicate()
                    print(f"\n[ERROR] Tunnel process exited unexpectedly:")
                    print(f"STDOUT: {stdout}")
                    print(f"STDERR: {stderr}")
                    return False

                # Simple check: if process alive for 10s, assume connected
                if i >= 10:
                    print(f"  ✅ Tunnel connected ({i+1}s)")
                    return True

            print(f"  ❌ Tunnel connection timeout ({max_wait}s)")
            self.stop()
            return False

        except Exception as e:
            print(f"  ❌ Failed to start tunnel: {e}")
            return False

    def stop(self):
        """Stop BrowserStack Local tunnel"""
        if self.process:
            print("\n[BrowserStack Local] Stopping tunnel...")
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
                print("  ✅ Tunnel stopped")
            except subprocess.TimeoutExpired:
                print("  ⚠️ Force killing tunnel...")
                self.process.kill()
                self.process.wait()
            except Exception as e:
                print(f"  ⚠️ Error stopping tunnel: {e}")
            finally:
                self.process = None


class MobileCollector:
    """Mobile device TLS and Cookie collector using Appium"""

    def __init__(self, device_config, browserstack_hub):
        self.device_config = device_config
        self.browserstack_hub = browserstack_hub
        self.driver = None

    def create_driver(self):
        """Create Appium WebDriver session"""
        from appium import webdriver
        from appium.options.android import UiAutomator2Options
        from appium.options.ios import XCUITestOptions

        # Debug: Print device_config
        print(f"\n[DEBUG] device_config received:")
        import json
        print(json.dumps(self.device_config, indent=2, default=str))

        device_name = self.device_config.get('device', self.device_config.get('deviceName', 'Unknown'))
        os_name = self.device_config.get('os', 'Unknown')

        print(f"\n[Appium] Creating session for {device_name} ({os_name})...")

        # Determine platform
        is_android = 'android' in os_name.lower()
        is_ios = 'ios' in os_name.lower()

        # Build capabilities based on platform
        if is_android:
            options = UiAutomator2Options()
            options.platform_name = 'Android'
        elif is_ios:
            options = XCUITestOptions()
            options.platform_name = 'iOS'
        else:
            print(f"  ⚠️ Unknown OS: {os_name}, assuming Android")
            options = UiAutomator2Options()
            options.platform_name = 'Android'

        # Browser name
        browser = self.device_config.get('browser', self.device_config.get('browserName', 'Chrome'))

        # BrowserStack requires browser name at top level for mobile browser testing
        if browser.lower() in ['chrome', 'safari', 'firefox', 'edge']:
            options.browser_name = browser
        # For native browser (e.g., "android"), use Chrome as fallback
        elif 'android' in browser.lower():
            options.browser_name = 'Chrome'
        else:
            options.browser_name = browser

        # BrowserStack specific capabilities
        bstack_options = {
            'deviceName': device_name,  # ← 중요: device name은 bstack:options에!
            'osVersion': self.device_config.get('os_version', '12.0'),  # ← OS version 필수!
            'realMobile': 'true',
            'local': 'true',  # ← 중요: BrowserStack Local 사용
            'debug': 'true',
            'networkLogs': 'true',
            'consoleLogs': 'verbose',
            'userName': BROWSERSTACK_USERNAME,
            'accessKey': BROWSERSTACK_ACCESS_KEY,
            'projectName': 'Coupang TLS Collection',
            'buildName': f'Mobile TLS - {datetime.now().strftime("%Y%m%d_%H%M%S")}',
            'sessionName': f'{device_name} - TLS & Cookie Collection'
        }

        options.set_capability('bstack:options', bstack_options)

        try:
            self.driver = webdriver.Remote(
                command_executor=self.browserstack_hub,
                options=options
            )
            print(f"  ✅ Session created: {self.driver.session_id}")
            return True

        except Exception as e:
            print(f"  ❌ Failed to create session: {e}")
            import traceback
            traceback.print_exc()
            return False

    def collect_tls_fingerprint(self):
        """Collect TLS fingerprint from browserleaks.com"""
        print("\n[TLS Collection] Accessing browserleaks.com...")

        try:
            # Navigate to TLS fingerprint page
            self.driver.get('https://tls.browserleaks.com/')
            print("  Page loaded, waiting for data...")

            # Wait for page to load
            time.sleep(5)

            # Extract TLS data using JavaScript
            tls_script = """
                // Try to find TLS data in various places
                var preElement = document.querySelector('pre');
                if (preElement && preElement.textContent) {
                    try {
                        return JSON.parse(preElement.textContent);
                    } catch (e) {
                        console.log('Failed to parse pre element:', e);
                    }
                }

                // Check for global TLS data variable
                if (window.tlsData) {
                    return window.tlsData;
                }

                return null;
            """

            tls_data = None
            for attempt in range(10):
                tls_data = self.driver.execute_script(tls_script)
                if tls_data:
                    print(f"  ✅ TLS data collected ({attempt+1} attempts)")
                    break
                time.sleep(1)

            if not tls_data:
                # Fallback: Get page source and try to extract
                print("  ⚠️ JavaScript extraction failed, trying page source...")
                page_source = self.driver.page_source

                # Look for JSON data in page
                import re
                json_match = re.search(r'<pre[^>]*>(.*?)</pre>', page_source, re.DOTALL)
                if json_match:
                    try:
                        tls_data = json.loads(json_match.group(1))
                        print("  ✅ TLS data extracted from page source")
                    except:
                        pass

            if not tls_data:
                print("  ❌ Failed to extract TLS data")
                return None

            # Extract key fingerprints
            ja3_hash = tls_data.get('ja3_hash', '')
            akamai_hash = tls_data.get('akamai_hash', '')

            print(f"  JA3: {ja3_hash}")
            print(f"  Akamai: {akamai_hash}")

            return {
                'tls_data': tls_data.get('tls', {}),
                'http2_data': tls_data.get('http2', []),
                'ja3_hash': ja3_hash,
                'akamai_fingerprint': akamai_hash
            }

        except Exception as e:
            print(f"  ❌ TLS collection failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def collect_cookies(self, search_keyword=None):
        """Collect cookies from Coupang"""
        from collectors.cookie_formatter import CookieFormatter

        print(f"\n[Cookie Collection] Accessing Coupang...")

        try:
            # Navigate to Coupang mobile
            self.driver.get('https://m.coupang.com/')
            print("  Coupang main page loaded")
            time.sleep(3)

            # Get cookies using JavaScript
            cookies_js = self.driver.execute_script('return document.cookie')
            print(f"  JavaScript cookies: {cookies_js[:100]}..." if cookies_js else "  No JS cookies")

            # Use CookieFormatter to collect and format cookies
            cookies_data = CookieFormatter.collect_webdriver_cookies(self.driver, cookies_js)
            cookie_names = {c['name'] for c in cookies_data}

            print(f"  ✅ Total unique cookies: {len(cookies_data)}")

            # Perform search if requested
            if search_keyword:
                print(f"\n  Searching for: {search_keyword}")
                try:
                    # Inject keyword into window object
                    self.driver.execute_script(f'window.__searchKeyword = {json.dumps(search_keyword)};')

                    # PC 버전과 동일한 React 검색 스크립트
                    search_script = """
const keyword = window.__searchKeyword;
const input = document.querySelector('input.is-speech[name="q"]');

// 헤더 버튼(참고용): 폼 밖일 수 있음
const headerBtn = document.querySelector('button.headerSearchBtn[type="submit"]');

if (!input) {
  console.warn("검색 input을 못 찾았어.");
} else {
  // 1) 리액트 컨트롤드 인풋: 네이티브 세터 + 이벤트로 상태 반영
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
  setter?.call(input, keyword);
  input.dispatchEvent(new Event('input',  { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));

  // 2) form 찾기
  let form = input.closest('form');
  if (!form) form = document.querySelector('form[role="search"]') || document.querySelector('form');

  // 3) 2초 지연 후 제출
  setTimeout(() => {
    if (form) {
      const innerSubmit = form.querySelector('button[type="submit"], input[type="submit"]');

      try {
        if (form.requestSubmit) {
          form.requestSubmit(innerSubmit || undefined);
        } else {
          form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })) || form.submit();
        }
        console.log(`2초 후 폼 제출로 "${keyword}" 검색`);
      } catch (e) {
        console.warn("requestSubmit 실패 -> 버튼 클릭 폴백 시도:", e);
        if (headerBtn) {
          headerBtn.click();
          console.log(`2초 후 헤더 버튼 클릭 폴백으로 "${keyword}" 검색`);
        } else {
          console.warn("제출 경로를 찾지 못했어.");
        }
      }
    } else if (headerBtn) {
      headerBtn.click();
      console.log(`2초 후 헤더 버튼 클릭으로 "${keyword}" 검색`);
    } else {
      console.warn("form/버튼 모두 없음.");
    }
  }, 2000);
}
"""

                    self.driver.execute_script(search_script)

                    print(f"  Search script executed, waiting for results...")
                    # 2초 스크립트 delay + 페이지 로드 + 추가 버퍼
                    time.sleep(5)

                    # Verify search results loaded
                    for attempt in range(10):
                        try:
                            has_results = self.driver.execute_script(
                                'return document.querySelector(".search-product-list") !== null || document.querySelector("#productList") !== null || document.body.innerHTML.includes("search")'
                            )
                            if has_results:
                                print(f"  ✅ Search results loaded")
                                break
                        except:
                            pass
                        time.sleep(0.5)

                    # Get updated cookies after search
                    cookies_js_after = self.driver.execute_script('return document.cookie')
                    new_cookies = CookieFormatter.collect_webdriver_cookies(self.driver, cookies_js_after)

                    # Merge with existing cookies
                    cookies_data, cookie_names = CookieFormatter.merge_cookie_lists(
                        cookies_data, new_cookies, cookie_names
                    )

                    print(f"  ✅ Cookies after search: {len(cookies_data)}")

                except Exception as e:
                    print(f"  ⚠️ Search failed: {e}")
                    import traceback
                    traceback.print_exc()

            return {
                'cookies': cookies_data,
                'cookie_count': len(cookies_data),
                'collected_at': datetime.now()
            }

        except Exception as e:
            print(f"  ❌ Cookie collection failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def close(self):
        """Close driver session"""
        if self.driver:
            try:
                self.driver.quit()
                print("\n[Appium] Session closed")
            except:
                pass


def main():
    parser = argparse.ArgumentParser(
        description='TLS-1030 Mobile Cookie & TLS Collector (BrowserStack Local + Appium)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # List device statistics
  python main-mobile.py --list

  # Show selection history
  python main-mobile.py --history

  # Select device interactively (4 steps)
  python main-mobile.py --select

  # Use last selected device
  python main-mobile.py --last

  # Select device directly by name
  python main-mobile.py --device "Samsung Galaxy S21 Plus"

  # Select with specific OS version
  python main-mobile.py --device "Samsung Galaxy S21 Plus" --os-version "11.0"

  # Collect with search
  python main-mobile.py --last --search 노트북
  python main-mobile.py --device "Samsung Galaxy S21 Plus" --search 노트북

  # Refresh device cache
  python main-mobile.py --refresh
        '''
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='Show device statistics by manufacturer'
    )

    parser.add_argument(
        '--history',
        action='store_true',
        help='Show device selection history'
    )

    parser.add_argument(
        '--select',
        action='store_true',
        help='Interactive device selection (4 steps)'
    )

    parser.add_argument(
        '--last',
        action='store_true',
        help='Use last selected device'
    )

    parser.add_argument(
        '--device',
        type=int,
        default=None,
        help='Use device by selection ID (see --history for IDs)'
    )

    parser.add_argument(
        '--refresh',
        action='store_true',
        help='Refresh device cache from BrowserStack API'
    )

    parser.add_argument(
        '--search',
        type=str,
        nargs='?',
        const='노트북',
        default=None,
        help='Perform search with keyword (default: "노트북")'
    )

    args = parser.parse_args()

    # Initialize device selector
    selector = DeviceSelector(BROWSERSTACK_USERNAME, BROWSERSTACK_ACCESS_KEY)

    # --list: Show statistics
    if args.list:
        devices = selector.fetch_devices(force_refresh=args.refresh)
        classified = selector.classify_devices(devices)

        print("\n" + "=" * 60)
        print("BrowserStack Device Statistics")
        print("=" * 60 + "\n")

        total_configs = 0
        for manufacturer in sorted(classified.keys()):
            models = classified[manufacturer]
            model_count = len(models)
            config_count = sum(
                len(browsers[browser])
                for model in models.values()
                for browsers in [model]
                for browser in browsers
            )
            total_configs += config_count
            print(f"  {manufacturer.capitalize()}: {model_count} models, {config_count} configurations")

        print(f"\n  Total: {total_configs} configurations")
        print("=" * 60 + "\n")
        return 0

    # --history: Show selection history
    if args.history:
        selector.print_history(20)
        return 0

    # --refresh: Refresh device cache
    if args.refresh:
        print("[INFO] Refreshing device cache from BrowserStack API...")
        devices = selector.fetch_devices(force_refresh=True)
        print(f"[SUCCESS] Cached {len(devices)} devices")
        return 0

    # Device selection
    device_config = None

    if args.device:
        # Use device by selection ID
        selection = selector.get_selection_by_id(args.device)
        if not selection:
            print(f"[ERROR] Device #{args.device} not found in history.")
            print("\nUse --history to see available device IDs")
            return 1

        print(f"\n[INFO] Using device #{args.device}:")
        print(f"  {selection['manufacturer'].capitalize()} {selection['model']}")
        print(f"  {selection['browser'].upper()} / OS {selection['os_version']}")
        print(f"  Device: {selection['device_name']}\n")

        # Rebuild device_config from history
        device_config = {
            'device': selection['device_name'],
            'os': selection['os'],
            'browser': selection['browser'],
            'os_version': selection['os_version'],
            'real_mobile': selection.get('real_mobile', True),
            '_selection': {
                'manufacturer': selection['manufacturer'],
                'model': selection['model'],
                'browser': selection['browser'],
                'os_version': selection['os_version']
            }
        }

    elif args.last:
        # Use last selected device
        last_selection = selector.get_last_selection()
        if not last_selection:
            print("[ERROR] No previous selection found. Use --select to choose a device.")
            return 1

        print("\n[INFO] Using last selected device:")
        print(f"  {last_selection['manufacturer'].capitalize()} {last_selection['model']}")
        print(f"  {last_selection['browser'].upper()} / OS {last_selection['os_version']}")
        print(f"  Device: {last_selection['device_name']}\n")

        # Rebuild device_config from history
        device_config = {
            'device': last_selection['device_name'],
            'os': last_selection['os'],
            'browser': last_selection['browser'],
            'os_version': last_selection['os_version'],
            'real_mobile': last_selection.get('real_mobile', True),
            '_selection': {
                'manufacturer': last_selection['manufacturer'],
                'model': last_selection['model'],
                'browser': last_selection['browser'],
                'os_version': last_selection['os_version']
            }
        }

    elif args.select:
        # Interactive selection
        devices = selector.fetch_devices(force_refresh=args.refresh)
        classified = selector.classify_devices(devices)
        device_config = selector.select_device_interactive(classified)

        if not device_config:
            print("\n[CANCELLED] Device selection cancelled")
            return 0

        # Save selection to history
        selector.save_history(device_config)

    else:
        # No selection method specified
        print("[ERROR] Please specify device selection method:")
        print("  --select         Interactive 4-step selection")
        print("  --device <ID>    Use device by selection ID (see --history)")
        print("  --last           Use last selected device")
        print("\nOr use --list, --history, --refresh for other operations")
        return 1

    # Print configuration
    print("\n" + "=" * 60)
    print("TLS-1030 Mobile Cookie & TLS Collector")
    print("=" * 60)
    print(f"Device: {device_config.get('device', 'Unknown')}")
    print(f"OS: {device_config.get('os', 'Unknown')}")
    print(f"Browser: {device_config.get('browser', 'Unknown').upper()}")
    print(f"BrowserStack Local: Enabled (IP consistency)")
    if args.search:
        print(f"Search Keyword: {args.search}")
    print("=" * 60 + "\n")

    # Initialize BrowserStack Local manager
    local_manager = BrowserStackLocalManager(BROWSERSTACK_ACCESS_KEY)

    # Initialize collector
    collector = None

    try:
        # Step 1: Start BrowserStack Local tunnel
        print("[1/5] Starting BrowserStack Local tunnel...")
        if not local_manager.start():
            print("\n[ERROR] Failed to start BrowserStack Local tunnel")
            return 1

        # Step 2: Create Appium session
        print("\n[2/5] Creating Appium session...")
        collector = MobileCollector(device_config, BROWSERSTACK_HUB)
        if not collector.create_driver():
            print("\n[ERROR] Failed to create Appium session")
            return 1

        # Step 3: Collect TLS fingerprint
        print("\n[3/5] Collecting TLS fingerprint...")
        tls_result = collector.collect_tls_fingerprint()

        if not tls_result:
            print("\n[ERROR] TLS collection failed")
            return 1

        print(f"\n  ✅ TLS Collection successful!")
        print(f"  - JA3: {tls_result['ja3_hash']}")
        print(f"  - Akamai: {tls_result['akamai_fingerprint']}")

        # Step 4: Collect cookies
        print("\n[4/5] Collecting cookies from Coupang...")
        cookie_result = collector.collect_cookies(search_keyword=args.search)

        if not cookie_result:
            print("\n[ERROR] Cookie collection failed")
            return 1

        print(f"\n  ✅ Cookie Collection successful!")
        print(f"  - Cookies: {cookie_result['cookie_count']}")

        # Step 5: Save to database
        print("\n[5/5] Uploading to database...")

        db = DbManager()
        file_manager = FileManager()

        # Prepare device name
        selection = device_config.get('_selection', {})
        device_name = f"{selection.get('manufacturer', 'Unknown').capitalize()} {selection.get('model', 'Unknown')}"
        if selection.get('browser'):
            device_name += f" ({selection['browser'].upper()})"

        # Save TLS fingerprint
        tls_fingerprint_id = db.save_tls_fingerprint(
            device_name=device_name,
            browser=device_config.get('browser', 'unknown'),
            os_version=device_config.get('os', 'Unknown'),
            tls_data=tls_result['tls_data'],
            http2_data=tls_result['http2_data'],
            ja3_hash=tls_result['ja3_hash'],
            akamai_fingerprint=tls_result['akamai_fingerprint'],
            collected_at=cookie_result['collected_at']
        )

        print(f"  - TLS fingerprint saved (ID: {tls_fingerprint_id})")

        # Save cookies (from mobile browser)
        cookie_id = db.save_cookies(
            device_name=device_name,
            browser=device_config.get('browser', 'unknown'),
            os_version=device_config.get('os', 'Unknown'),
            tls_fingerprint_id=tls_fingerprint_id,
            cookie_data=cookie_result['cookies'],
            collected_at=cookie_result['collected_at'],
            cookie_type='mobile'
        )

        print(f"  - Cookies saved (ID: {cookie_id}, type: 'mobile')")

        # Save selection history
        selector.save_history(device_config)

        # Save to local files (optional)
        timestamp = cookie_result['collected_at'].strftime('%Y%m%d_%H%M%S')
        device_slug = device_name.lower().replace(' ', '-').replace('(', '').replace(')', '')
        file_manager.save_cookies(cookie_result['cookies'], f"mobile-{device_slug}", timestamp)

        print(f"\n[SUCCESS] All data saved successfully!")
        print(f"  - TLS Fingerprint ID: {tls_fingerprint_id}")
        print(f"  - Cookie ID: {cookie_id}")
        print(f"  - Device: {device_name}")
        print(f"  - Files saved to: output/")

        return 0

    except KeyboardInterrupt:
        print("\n\n[CANCELLED] User interrupted")
        return 1

    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # Cleanup
        if collector:
            collector.close()

        local_manager.stop()

        print("\n[CLEANUP] Done")


if __name__ == '__main__':
    sys.exit(main())

"""
TLS-1030 PC Cookie & TLS Collector
- Chrome version selection
- User profile management
- TLS fingerprint + Cookie collection
- DB upload with modular architecture
"""

import argparse
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import warnings

# Load .env file
load_dotenv()

# Suppress subprocess cleanup warnings on Windows
if sys.platform == 'win32':
    warnings.filterwarnings('ignore', category=ResourceWarning)

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.chrome_detector import ChromeDetector
from collectors.cookie_collector import collect_cookies
from modules import DbManager, FileManager
from config import TIMEOUTS


def main():
    parser = argparse.ArgumentParser(
        description='TLS-1030 PC Cookie & TLS Collector',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # List available Chrome versions
  python main-pc.py --list

  # Collect with system Chrome (default)
  python main-pc.py

  # Collect with specific Chrome version
  python main-pc.py --version 136

  # Collect with search
  python main-pc.py --search 노트북 --page 3

  # Collect with custom user profile
  python main-pc.py --user my-profile
        '''
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available Chrome versions'
    )

    parser.add_argument(
        '--version',
        type=str,
        default=None,
        help='Chrome version to use (e.g., "system", "136"). Default: system'
    )

    parser.add_argument(
        '--user',
        type=str,
        default=None,
        help='User profile name (default: Chrome version)'
    )

    parser.add_argument(
        '--headless',
        action='store_true',
        help='Run Chrome in headless mode'
    )

    parser.add_argument(
        '--search',
        type=str,
        nargs='?',
        const='노트북',
        default=None,
        help='Perform search with keyword (default: "노트북")'
    )

    parser.add_argument(
        '--page',
        type=int,
        default=2,
        help='Number of pages to collect (default: 2, only works with --search)'
    )

    args = parser.parse_args()

    # Initialize detector
    try:
        detector = ChromeDetector()
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        return 1

    # List versions mode
    if args.list:
        print("\n" + "=" * 60)
        print("Available Chrome Versions")
        print("=" * 60 + "\n")
        versions = detector.print_versions()
        print(f"\n[INFO] Total {len(versions)} versions available")
        return 0

    # If no version specified, show list and prompt for selection
    if args.version is None:
        print("\n" + "=" * 60)
        print("Available Chrome Versions")
        print("=" * 60 + "\n")
        versions = detector.print_versions()

        print(f"\n[INFO] Total {len(versions)} versions available")
        print("\nSelect Chrome version (enter number or version string):")
        print("[HINT] Press Enter to use System Chrome (default)")

        try:
            selection = input("> ").strip()

            # Default to system if empty
            if not selection:
                args.version = 'system'
            # Try as index first
            elif selection.isdigit():
                idx = int(selection) - 1
                if 0 <= idx < len(versions):
                    args.version = versions[idx]['version']
                else:
                    print(f"[ERROR] Invalid selection. Please choose 1-{len(versions)}")
                    return 1
            else:
                # Use as version string
                args.version = selection
        except (KeyboardInterrupt, EOFError):
            print("\n[CANCELLED] Exiting...")
            return 0

    # Get selected Chrome version
    chrome_info = detector.get_version(args.version)

    if chrome_info is None:
        print(f"[ERROR] Chrome version '{args.version}' not found")
        print("\n[TIP] Use --list to see all available versions")
        return 1

    if not chrome_info['available']:
        print(f"[ERROR] Chrome {chrome_info['version']} binary not found at:")
        print(f"        {chrome_info['path']}")
        return 1

    # Setup user profile directory
    user_folder = args.user if args.user else chrome_info['version']
    user_dir = Path(__file__).parent / 'user' / user_folder
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / 'cookies').mkdir(exist_ok=True)
    (user_dir / 'logs').mkdir(exist_ok=True)
    (user_dir / 'profile').mkdir(exist_ok=True)

    # Print configuration
    print("\n" + "=" * 60)
    print("TLS-1030 PC Cookie & TLS Collector")
    print("=" * 60)
    print(f"Chrome Version: {chrome_info['version']}")
    print(f"Chrome Binary:  {chrome_info['path']}")
    print(f"User Profile:   {user_folder}")
    print(f"Profile Dir:    {user_dir}")
    print(f"Headless Mode:  {args.headless}")
    if args.search:
        print(f"Search Keyword: {args.search}")
        print(f"Max Pages:      {args.page}")
    print("=" * 60 + "\n")

    # Run collection
    if args.search:
        print(f"[1/3] Starting cookie, TLS, and search collection...")
    else:
        print("[1/3] Starting cookie and TLS collection...")

    try:
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

        def run_collection():
            max_pages = args.page if args.search else 1
            return collect_cookies(
                chrome_path=chrome_info['path'],
                user_data_dir=str(user_dir / 'profile'),
                headless=args.headless,
                search_keyword=args.search,
                max_pages=max_pages
            )

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_collection)
            try:
                result = future.result(timeout=TIMEOUTS['total_collection'])
            except FuturesTimeoutError:
                print(f"\n[ERROR] Collection timeout ({TIMEOUTS['total_collection']}s)")
                return 1

        print(f"\n[2/3] Collection successful!")
        print(f"  - Cookies: {result['cookie_count']}")
        print(f"  - JA3: {result['ja3_hash']}")
        print(f"  - Akamai FP: {result['akamai_fingerprint']}")

    except TimeoutError as e:
        print(f"\n[ERROR] Collection timeout: {e}")
        return 1
    except Exception as e:
        print(f"\n[ERROR] Collection failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Save to DB using DbManager
    print(f"\n[3/3] Uploading to database...")

    try:
        from datetime import datetime

        db = DbManager()
        file_manager = FileManager()

        # Prepare device name
        device_name = f"Chrome {chrome_info['version']}"
        if user_folder != chrome_info['version']:
            device_name += f" ({user_folder})"

        # Convert ISO string to datetime if needed
        collected_at = result['collected_at']
        if isinstance(collected_at, str):
            collected_at = datetime.fromisoformat(collected_at)

        # Save TLS fingerprint
        tls_fingerprint_id = db.save_tls_fingerprint(
            device_name=device_name,
            browser='chrome',
            os_version='Windows 10',
            tls_data=result['tls_data'],
            http2_data=result['http2_data'],
            ja3_hash=result['ja3_hash'],
            akamai_fingerprint=result['akamai_fingerprint'],
            collected_at=collected_at
        )

        print(f"  - TLS fingerprint saved (ID: {tls_fingerprint_id})")

        # Save cookies (from browser)
        cookie_id = db.save_cookies(
            device_name=device_name,
            browser='chrome',
            os_version='Windows 10',
            tls_fingerprint_id=tls_fingerprint_id,
            cookie_data=result['cookies'],
            collected_at=collected_at,
            cookie_type='browser'
        )

        print(f"  - Cookies saved (ID: {cookie_id}, type: 'browser')")

        # Save to local files (optional)
        timestamp = collected_at.strftime('%Y%m%d_%H%M%S')
        file_manager.save_cookies(result['cookies'], chrome_info['version'], timestamp)
        file_manager.save_request_headers(result.get('all_request_headers', {}), chrome_info['version'], timestamp)

        print(f"\n[SUCCESS] All data saved successfully!")
        print(f"  - TLS Fingerprint ID: {tls_fingerprint_id}")
        print(f"  - Cookie ID: {cookie_id}")
        print(f"  - Files saved to: output/")

        return 0

    except Exception as e:
        print(f"\n[ERROR] Database upload failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

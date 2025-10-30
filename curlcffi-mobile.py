"""
curl-cffi Multi-Page Crawler (MOBILE Version)
- Loads latest MOBILE TLS fingerprint and cookies from database
- Forces TLS 1.3 → TLS 1.2 conversion for curl-cffi JA3 compatibility
- Crawls multiple pages using curl-cffi with extra_fp
- Uses Session for automatic cookie management
- Saves HTML/RSC responses to output directory
- Saves updated cookies to database with type='mobile'
"""

import sys
import time
import random
import json
from datetime import datetime
from urllib.parse import quote
from curl_cffi import requests
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from modules import DbManager, TlsConfig, CookieHandler, FileManager
from utils import generate_traceid
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()


def get_latest_mobile_fingerprint():
    """
    Get latest MOBILE TLS fingerprint from database

    Returns:
        dict: TLS fingerprint data with cookies, or None if not found
    """
    try:
        conn = pymysql.connect(
            host=os.getenv('DB_HOST', '220.121.120.83'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USER', 'tls_user'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'tls-1029'),
            charset='utf8mb4'
        )
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Query for mobile cookies (exclude Windows 10 = PC)
        query = """
            SELECT
                c.id as cookie_id,
                c.device_name,
                c.browser,
                c.os_version,
                c.cookie_type,
                c.cookie_data,
                c.collected_at,
                t.id as tls_fingerprint_id,
                t.tls_data,
                t.http2_data,
                t.ja3_hash,
                t.akamai_fingerprint
            FROM cookies c
            JOIN tls_fingerprints t ON c.tls_fingerprint_id = t.id
            WHERE c.os_version != 'Windows 10'
            ORDER BY c.collected_at DESC
            LIMIT 1
        """

        cursor.execute(query)
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        if not result:
            return None

        # Parse JSON fields
        result['tls_data'] = json.loads(result['tls_data'])
        result['http2_data'] = json.loads(result['http2_data'])
        result['cookies'] = json.loads(result['cookie_data'])

        return result

    except Exception as e:
        print(f"[ERROR] Database query failed: {e}")
        return None


def save_mobile_cookies(device_name, browser, os_version, tls_fingerprint_id, cookie_data):
    """
    Save updated mobile cookies to database

    Returns:
        int: Cookie ID
    """
    try:
        conn = pymysql.connect(
            host=os.getenv('DB_HOST', '220.121.120.83'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USER', 'tls_user'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'tls-1029'),
            charset='utf8mb4'
        )
        cursor = conn.cursor()

        query = """
            INSERT INTO cookies (
                device_name, browser, os_version,
                tls_fingerprint_id, cookie_type, cookie_data,
                collected_at, is_valid
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        cursor.execute(query, (
            device_name,
            browser,
            os_version,
            tls_fingerprint_id,
            'mobile',  # cookie_type
            json.dumps(cookie_data),
            datetime.now(),
            True
        ))

        conn.commit()
        cookie_id = cursor.lastrowid

        cursor.close()
        conn.close()

        return cookie_id

    except Exception as e:
        print(f"[ERROR] Failed to save cookies: {e}")
        return None


def force_tls12_ja3(ja3_string):
    """
    Force TLS 1.3 (772) → TLS 1.2 (771)

    curl-cffi only supports TLS 1.2 with JA3 mode.
    Mobile devices often use TLS 1.3, so we need to convert.

    Args:
        ja3_string: Original JA3 string (may be TLS 1.3)

    Returns:
        str: Modified JA3 string with TLS 1.2 (771)
    """
    parts = ja3_string.split(',')
    if len(parts) == 5:
        version, ciphers, extensions, groups, point_formats = parts

        # Replace 772 (TLS 1.3) with 771 (TLS 1.2)
        if version == '772':
            version = '771'
            print(f"  [JA3 Fix] TLS 1.3 (772) → TLS 1.2 (771)")

        return f"{version},{ciphers},{extensions},{groups},{point_formats}"

    return ja3_string


def verify_tls(session, ja3_string, extra_fp, headers, output_file="tls-mobile.json"):
    """
    Verify TLS fingerprint by connecting to browserleaks.com
    Saves JSON response for TLS verification

    Args:
        session: curl-cffi Session object
        ja3_string: JA3 fingerprint string
        extra_fp: TLS fingerprint configuration
        headers: Request headers
        output_file: Output JSON file path

    Returns:
        dict: TLS data from browserleaks, or None if failed
    """
    print(f"\n{'='*60}")
    print(f"TLS VERIFICATION (Mobile)")
    print(f"{'='*60}\n")

    verify_url = "https://tls.browserleaks.com/"

    try:
        print(f"  Connecting to: {verify_url}")
        print(f"  Using JA3: {ja3_string[:60]}...")
        start_time = time.time()

        response = session.get(
            verify_url,
            headers=headers,
            ja3=ja3_string,
            extra_fp=extra_fp,
            timeout=10
        )

        elapsed_ms = int((time.time() - start_time) * 1000)

        if response.status_code == 200:
            # Response is pure JSON
            tls_data = json.loads(response.text)
            content_length = len(response.text)

            print(f"  Status: {response.status_code}")
            print(f"  Time: {elapsed_ms} ms")
            print(f"  Size: {content_length:,} bytes")
            print(f"  JA3 Hash: {tls_data.get('ja3_hash', 'Unknown')}")
            print(f"  Akamai Hash: {tls_data.get('akamai_hash', 'Unknown')}")

            # Save JSON to file
            output_path = Path(__file__).parent / output_file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(tls_data, f, indent=2, ensure_ascii=False)

            print(f"  Saved to: {output_path}")
            print(f"  Result: SUCCESS\n")
            return tls_data
        else:
            print(f"  Status: {response.status_code}")
            print(f"  Result: FAILED\n")
            return None

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        print(f"  Result: FAILED\n")
        return None


def compare_tls_data(db_tls_data, browserleaks_data):
    """
    Compare DB TLS data with browserleaks TLS data
    Print only differences

    Args:
        db_tls_data: TLS data from database
        browserleaks_data: TLS data from browserleaks.com

    Returns:
        bool: True if identical, False if differences found
    """
    print(f"\n{'='*60}")
    print(f"TLS COMPARISON")
    print(f"{'='*60}")
    print(f"  Note: JA3 Hash changes per connection (GREASE randomization)")
    print(f"        TLS 1.3 was converted to 1.2 for curl-cffi compatibility")
    print(f"        Comparing core TLS components...\n")

    differences = []

    # Extract browserleaks TLS section
    bl_tls = browserleaks_data.get('tls', {})

    # 1. Compare TLS Version (skip - we forced TLS 1.2)
    db_version = db_tls_data.get('tls_version', '')
    bl_version = bl_tls.get('connection_version', {}).get('name', '')

    if db_version and 'TLS 1.3' in db_version:
        print(f"  [Note] Original device uses TLS 1.3, converted to 1.2 for curl-cffi")

    # 2. Compare Cipher Suites (names only, excluding GREASE)
    db_ciphers = [c.get('name', '') for c in db_tls_data.get('cipher_suites', [])]
    bl_ciphers = [c.get('name', '') for c in bl_tls.get('cipher_suites', [])]

    # Filter out GREASE
    db_ciphers_filtered = [c for c in db_ciphers if c != 'GREASE']
    bl_ciphers_filtered = [c for c in bl_ciphers if c != 'GREASE']

    if db_ciphers_filtered != bl_ciphers_filtered:
        differences.append({
            'field': 'Cipher Suites',
            'db_value': f"{len(db_ciphers_filtered)} items",
            'actual_value': f"{len(bl_ciphers_filtered)} items"
        })

    # 3. Compare Supported Groups (excluding GREASE)
    # DB: Try top-level first (PC), then extensions (Mobile)
    db_groups_raw = db_tls_data.get('supported_groups', [])
    if not db_groups_raw:
        # Mobile: Extract from extensions
        for ext in db_tls_data.get('extensions', []):
            if ext.get('name') == 'supported_groups':
                named_groups = ext.get('data', {}).get('named_groups', [])
                db_groups_raw = [g.get('name', '') for g in named_groups]
                break

    db_groups = [g for g in db_groups_raw if 'GREASE' not in str(g).upper()]

    # Extract from extensions in browserleaks data
    bl_groups_raw = []
    for ext in bl_tls.get('extensions', []):
        if ext.get('name') == 'supported_groups':
            named_groups = ext.get('data', {}).get('named_groups', [])
            bl_groups_raw = [g.get('name', '') for g in named_groups]
            break

    bl_groups = [g for g in bl_groups_raw if 'GREASE' not in g.upper()]

    if db_groups != bl_groups:
        differences.append({
            'field': 'Supported Groups',
            'db_value': f"{len(db_groups)} items",
            'actual_value': f"{len(bl_groups)} items"
        })

    # Print results
    if not differences:
        print(f"  [OK] TLS fingerprints match (considering TLS version conversion)!\n")
        return True
    else:
        print(f"  [DIFF] Found {len(differences)} difference(s):\n")

        for diff in differences:
            print(f"  [{diff['field']}]")
            print(f"    DB:     {diff['db_value']}")
            print(f"    Actual: {diff['actual_value']}")
            print()

        return False


def build_search_url(keyword, page=1, traceid=None):
    """
    Build Coupang mobile search URL

    Args:
        keyword: Search keyword
        page: Page number (1, 2, 3, ...)
        traceid: Trace ID (reuse for pagination)

    Returns:
        tuple: (url, traceid)
    """
    if traceid is None:
        traceid = generate_traceid()

    encoded_keyword = quote(keyword)

    if page == 1:
        # First page: mobile URL
        url = f"https://m.coupang.com/nm/search?q={encoded_keyword}&traceId={traceid}"
    else:
        # Page 2+: pagination
        url = f"https://m.coupang.com/nm/search?q={encoded_keyword}&traceId={traceid}&page={page}"

    return url, traceid


def validate_response(content, page_num):
    """
    Validate response content for mobile

    Args:
        content: Response text
        page_num: Page number

    Returns:
        tuple: (has_products, is_blocked)
    """
    content_length = len(content)

    # Mobile: Simple HTML
    has_products = 'product' in content.lower() or 'search' in content.lower()
    is_blocked = content_length < 5000 or 'ERR_' in content or 'location.reload' in content

    return has_products, is_blocked


def crawl_multipage(keyword="노트북", max_pages=3):
    """
    Crawl multiple pages using curl-cffi (MOBILE version)

    Args:
        keyword: Search keyword
        max_pages: Number of pages to crawl

    Returns:
        bool: True if all pages successful
    """
    print(f"\n{'='*60}")
    print(f"curl-cffi Multi-Page Crawler (MOBILE)")
    print(f"{'='*60}\n")

    # Initialize managers
    file_manager = FileManager()

    # Load latest MOBILE TLS fingerprint and cookies from DB
    print(f"[1/3] Loading latest MOBILE TLS fingerprint from database...")
    data = get_latest_mobile_fingerprint()

    if not data:
        print(f"[ERROR] No MOBILE TLS fingerprint found in database")
        print(f"[INFO] Please run main-mobile.py first to collect mobile TLS data")
        return False

    device_name = data['device_name']
    browser = data.get('browser', 'Chrome')

    print(f"  Device: {device_name}")
    print(f"  Browser: {browser}")
    print(f"  Collected: {data['collected_at']}")
    print(f"  JA3 Hash: {data['ja3_hash']}")
    print(f"  Cookies: {len(data['cookies'])} items")

    # Build TLS configuration
    print(f"\n[2/3] Building TLS configuration (Mobile)...")

    # Build JA3 string from DB TLS data (same as PC version)
    ja3_string = TlsConfig.build_ja3_string(data['tls_data'])

    # Debug: Check original ja3_text from DB
    original_ja3 = data['tls_data'].get('ja3_text', '')
    if original_ja3:
        orig_parts = original_ja3.split(',')
        if len(orig_parts) >= 3:
            orig_exts = orig_parts[2]
            print(f"  [DEBUG] Original extensions from DB: {orig_exts[:100]}...")
            print(f"  [DEBUG] Extension 0 in original: {'0' in orig_exts.split('-')}")

    # Debug: Check if extension 0 is present in built JA3
    if ja3_string:
        parts = ja3_string.split(',')
        if len(parts) >= 3:
            extensions = parts[2]
            has_ext_0 = '0' in extensions.split('-')
            print(f"  [DEBUG] Built extensions: {extensions[:100]}...")
            print(f"  [DEBUG] Extension 0 in built JA3: {has_ext_0}")
            print(f"  [DEBUG] UNSUPPORTED_EXTENSIONS: {TlsConfig.UNSUPPORTED_EXTENSIONS}")
        if len(parts) >= 5:
            groups = parts[3]
            point_formats = parts[4]
            print(f"  [DEBUG] Supported groups: [{groups}]")
            print(f"  [DEBUG] Point formats: [{point_formats}]")

    # Mobile: Force TLS 1.3 -> 1.2 conversion (curl-cffi JA3 mode only supports TLS 1.2)
    ja3_string = force_tls12_ja3(ja3_string)

    extra_fp = TlsConfig.build_extra_fp(data['tls_data'])
    cookie_dict = CookieHandler.to_dict(data['cookies'])

    # Check if extensions were filtered
    original_ja3 = data['tls_data'].get('ja3_text', '')
    if original_ja3 and original_ja3 != ja3_string:
        print(f"  Note: Filtered unsupported TLS extensions for compatibility")

    print(f"  TLS version: {data['tls_data'].get('tls_version')}")
    print(f"  JA3 string: {ja3_string[:80]}{'...' if len(ja3_string) > 80 else ''}")
    print(f"  JA3 hash (DB): {data['ja3_hash']}")
    print(f"  extra_fp: {extra_fp}")

    # Create Session for automatic cookie management
    session = requests.Session()

    # Set cookies
    for name, value in cookie_dict.items():
        session.cookies.set(name, value, domain='.coupang.com', path='/')

    print(f"  Session initialized with {len(cookie_dict)} cookies")
    print(f"  Initial cookies: {', '.join(list(cookie_dict.keys())[:5])}{'...' if len(cookie_dict) > 5 else ''}")

    # Verify TLS fingerprint before crawling
    # Use mobile User-Agent from device
    verify_headers = {
        'User-Agent': data['tls_data'].get('user_agent', 'Mozilla/5.0 (Linux; Android 13) Mobile'),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
    }

    browserleaks_data = verify_tls(session, ja3_string, extra_fp, verify_headers, "tls-mobile.json")

    # Compare DB TLS data with actual browserleaks data
    if browserleaks_data:
        compare_tls_data(data['tls_data'], browserleaks_data)

    # Initialize session by visiting homepage first
    print(f"\n[Session Init] Visiting Coupang mobile homepage...")
    try:
        homepage_url = "https://m.coupang.com/"
        homepage_headers = {
            'User-Agent': data['tls_data'].get('user_agent', 'Mozilla/5.0 (Linux; Android 13) Mobile'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
        }

        homepage_response = session.get(
            homepage_url,
            headers=homepage_headers,
            ja3=ja3_string,
            extra_fp=extra_fp,
            timeout=10
        )
        print(f"  Status: {homepage_response.status_code}")
        print(f"  Size: {len(homepage_response.text):,} bytes")
        print(f"  Session initialized\n")
    except Exception as e:
        print(f"  Warning: Homepage visit failed: {e}")
        print(f"  Continuing anyway...\n")

    # Start crawling
    print(f"\n[3/3] Crawling {max_pages} pages (Mobile)...")
    print(f"  Keyword: {keyword}")
    print(f"  Target pages: {max_pages}\n")

    page_results = []
    traceid = None

    for page_num in range(1, max_pages + 1):
        print(f"  [Page {page_num}]")

        # Build URL
        url, traceid = build_search_url(keyword, page_num, traceid)
        print(f"    URL: {url[:70]}...")

        # Build mobile headers - MUST use same User-Agent as TLS collection
        user_agent = data['tls_data'].get('user_agent', 'Mozilla/5.0 (Linux; Android 13) Mobile')

        headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Referer': page_results[-1]['url'] if page_num > 1 else 'https://m.coupang.com/',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin' if page_num > 1 else 'none',
            'Sec-Fetch-User': '?1',
            'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
        }

        # Debug: Show cookies before request
        try:
            current_cookies = session.cookies.get_dict()
            print(f"    [DEBUG] Cookies before request: {len(current_cookies)} items")
        except Exception as e:
            print(f"    [DEBUG] Could not read session cookies: {e}")

        try:
            # Send request using Session
            start_time = time.time()
            response = session.get(
                url,
                headers=headers,
                ja3=ja3_string,
                extra_fp=extra_fp,
                timeout=10
            )
            elapsed_ms = int((time.time() - start_time) * 1000)

            # Debug: Show cookies after request
            try:
                updated_cookies = session.cookies.get_dict()
                print(f"    [DEBUG] Cookies after request: {len(updated_cookies)} items")
                if len(updated_cookies) != len(current_cookies):
                    new_cookies = set(updated_cookies.keys()) - set(current_cookies.keys())
                    if new_cookies:
                        print(f"    [DEBUG] New cookies: {', '.join(list(new_cookies)[:3])}")
            except Exception as e:
                print(f"    [DEBUG] Could not read updated cookies: {e}")

            content = response.text
            content_length = len(content)

            # Validate response
            has_products, is_blocked = validate_response(content, page_num)

            print(f"    ─────────────────────────────────────")
            print(f"    Status: {response.status_code}")
            print(f"    Size: {content_length:,} bytes")
            print(f"    Time: {elapsed_ms} ms")
            print(f"    Products: {'Yes' if has_products else 'No'}")
            print(f"    Blocked: {'Yes' if is_blocked else 'No'}")

            if has_products and not is_blocked:
                print(f"    Result: SUCCESS")

                # Save page content
                ext = f'mobile-p{page_num}.html'
                filepath = file_manager.save_page(content, page_num, f'mobile-{browser}', ext)
                print(f"    Saved: {filepath}")

                page_results.append({
                    'page': page_num,
                    'url': url,
                    'status': response.status_code,
                    'size': content_length,
                    'time_ms': elapsed_ms,
                    'success': True,
                    'file': filepath
                })

                # Delay between pages
                if page_num < max_pages:
                    delay = random.uniform(0.5, 1.5)
                    print(f"    Waiting {delay:.1f}s...\n")
                    time.sleep(delay)
            else:
                print(f"    Result: FAILED")

                # Save failed response
                ext = f'mobile-p{page_num}.failed.html'
                filepath = file_manager.save_page(content, page_num, f'mobile-{browser}', ext)
                print(f"    Saved: {filepath}")

                page_results.append({
                    'page': page_num,
                    'url': url,
                    'status': response.status_code,
                    'size': content_length,
                    'time_ms': elapsed_ms,
                    'success': False,
                    'file': filepath
                })

                # Stop if blocked
                if is_blocked:
                    print(f"\n    [STOPPED] Page {page_num} blocked\n")
                    break

        except Exception as e:
            print(f"    ERROR: {e}\n")
            import traceback
            traceback.print_exc()
            page_results.append({
                'page': page_num,
                'url': url,
                'success': False,
                'error': str(e)
            })
            break

    # Save updated cookies to database
    print(f"\n{'='*60}")
    print(f"COOKIE UPDATE (Mobile)")
    print(f"{'='*60}")

    try:
        # Get final cookies from session
        final_cookies = []
        cookie_dict = session.cookies.get_dict()

        for name, value in cookie_dict.items():
            final_cookies.append({
                'name': name,
                'value': value,
                'domain': '.coupang.com',
                'path': '/',
                'expires': None,
                'httpOnly': False,
                'secure': True,
                'sameSite': 'None',
            })

        print(f"Final cookies: {len(final_cookies)} items")

        # Save to database with cookie_type='mobile'
        cookie_id = save_mobile_cookies(
            device_name=device_name,
            browser=browser,
            os_version=data.get('os_version', 'Unknown'),
            tls_fingerprint_id=data['tls_fingerprint_id'],
            cookie_data=final_cookies
        )

        if cookie_id:
            print(f"Cookies saved to DB (ID: {cookie_id}, type: 'mobile')")
        else:
            print(f"Failed to save cookies to DB")

    except Exception as e:
        print(f"Cookie save error: {e}")
        import traceback
        traceback.print_exc()

    # Save results summary
    print(f"\n{'='*60}")
    print(f"SUMMARY (Mobile)")
    print(f"{'='*60}")
    print(f"Device: {device_name}")
    print(f"Total pages: {len(page_results)}")

    successful_pages = [r for r in page_results if r.get('success')]
    print(f"Successful: {len(successful_pages)}")

    for result in page_results:
        status = "SUCCESS" if result.get('success') else "FAILED"
        print(f"  Page {result['page']}: {status}")

    # Save results to JSON
    results_file = file_manager.save_results({
        'keyword': keyword,
        'max_pages': max_pages,
        'device_name': device_name,
        'browser': browser,
        'device_type': 'mobile',
        'results': page_results,
        'summary': {
            'total': len(page_results),
            'successful': len(successful_pages)
        }
    }, f'results_mobile_{browser.lower()}.json')

    print(f"\nResults saved: {results_file}")

    return len(successful_pages) == max_pages


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python curlcffi-mobile.py <keyword> [max_pages]")
        print("Example: python curlcffi-mobile.py 노트북 3")
        print("\nNote: Uses latest MOBILE TLS fingerprint from database")
        print("      Automatically converts TLS 1.3 → 1.2 for curl-cffi compatibility")
        sys.exit(1)

    keyword = sys.argv[1]
    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    success = crawl_multipage(keyword, max_pages)
    sys.exit(0 if success else 1)

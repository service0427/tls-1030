"""
curl-cffi Multi-Page Crawler
- Loads latest TLS fingerprint and cookies from database
- Crawls multiple pages using curl-cffi with extra_fp
- Uses Session for automatic cookie management
- Saves HTML/RSC responses to output directory
- Saves updated cookies to database
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


def verify_tls(session, extra_fp, headers, output_file="tls.json"):
    """
    Verify TLS fingerprint by connecting to browserleaks.com
    Saves JSON response for TLS verification

    Args:
        session: curl-cffi Session object
        extra_fp: TLS fingerprint configuration
        headers: Request headers
        output_file: Output JSON file path

    Returns:
        dict: TLS data from browserleaks, or None if failed
    """
    print(f"\n{'='*60}")
    print(f"TLS VERIFICATION")
    print(f"{'='*60}\n")

    verify_url = "https://tls.browserleaks.com/"

    try:
        print(f"  Connecting to: {verify_url}")
        start_time = time.time()

        response = session.get(
            verify_url,
            headers=headers,
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
    print(f"{'='*60}\n")

    differences = []

    # Extract browserleaks TLS section
    bl_tls = browserleaks_data.get('tls', {})

    # 1. Compare JA3 Hash
    db_ja3 = db_tls_data.get('ja3_hash', '')
    bl_ja3 = browserleaks_data.get('ja3_hash', '')

    if db_ja3 != bl_ja3:
        differences.append({
            'field': 'JA3 Hash',
            'db_value': db_ja3,
            'actual_value': bl_ja3
        })

    # 2. Compare TLS Version
    db_version = db_tls_data.get('tls_version', '')
    bl_version = bl_tls.get('connection_version', {}).get('name', '')

    if db_version != bl_version:
        differences.append({
            'field': 'TLS Version',
            'db_value': db_version,
            'actual_value': bl_version
        })

    # 3. Compare Cipher Suites (names only)
    db_ciphers = [c.get('name', '') for c in db_tls_data.get('cipher_suites', [])]
    bl_ciphers = [c.get('name', '') for c in bl_tls.get('cipher_suites', [])]

    # Filter out GREASE
    db_ciphers_filtered = [c for c in db_ciphers if c != 'GREASE']
    bl_ciphers_filtered = [c for c in bl_ciphers if c != 'GREASE']

    if db_ciphers_filtered != bl_ciphers_filtered:
        differences.append({
            'field': 'Cipher Suites',
            'db_value': f"{len(db_ciphers_filtered)} items:\n      " + '\n      '.join(db_ciphers_filtered),
            'actual_value': f"{len(bl_ciphers_filtered)} items:\n      " + '\n      '.join(bl_ciphers_filtered)
        })

    # 4. Compare Supported Groups
    db_groups = db_tls_data.get('supported_groups', [])

    # Extract from extensions in browserleaks data
    bl_groups = []
    for ext in bl_tls.get('extensions', []):
        if ext.get('name') == 'supported_groups':
            named_groups = ext.get('data', {}).get('named_groups', [])
            bl_groups = [g.get('name', '') for g in named_groups]
            break

    if db_groups != bl_groups:
        differences.append({
            'field': 'Supported Groups',
            'db_value': f"{len(db_groups)} items:\n      " + '\n      '.join(db_groups),
            'actual_value': f"{len(bl_groups)} items:\n      " + '\n      '.join(bl_groups)
        })

    # 5. Compare Signature Algorithms
    db_sig_algs = db_tls_data.get('signature_algorithms', [])

    # Extract from extensions in browserleaks data
    bl_sig_algs = []
    for ext in bl_tls.get('extensions', []):
        if ext.get('name') == 'signature_algorithms':
            algorithms = ext.get('data', {}).get('algorithms', [])
            bl_sig_algs = [a.get('name', '') for a in algorithms]
            break

    if db_sig_algs != bl_sig_algs:
        differences.append({
            'field': 'Signature Algorithms',
            'db_value': f"{len(db_sig_algs)} items:\n      " + '\n      '.join(db_sig_algs),
            'actual_value': f"{len(bl_sig_algs)} items:\n      " + '\n      '.join(bl_sig_algs)
        })

    # Print results
    if not differences:
        print(f"  ✓ TLS fingerprints match perfectly!\n")
        return True
    else:
        print(f"  ✗ Found {len(differences)} difference(s):\n")

        for diff in differences:
            print(f"  [{diff['field']}]")
            print(f"    DB:     {diff['db_value']}")
            print(f"    Actual: {diff['actual_value']}")
            print()

        return False


def build_search_url(keyword, page=1, traceid=None):
    """
    Build Coupang search URL

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
        # First page: no page parameter
        url = f"https://www.coupang.com/np/search?component=&q={encoded_keyword}&traceId={traceid}&channel=user"
    else:
        # Page 2+: Next.js RSC request with _rsc parameter
        rsc_param = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=5))
        url = f"https://www.coupang.com/np/search?q={encoded_keyword}&traceId={traceid}&channel=user&page={page}&_rsc={rsc_param}"

    return url, traceid


def validate_response(content, page_num):
    """
    Validate response content

    Args:
        content: Response text
        page_num: Page number

    Returns:
        tuple: (has_products, is_blocked)
    """
    content_length = len(content)

    if page_num == 1:
        # Page 1: Regular HTML
        has_products = 'product-list' in content or 'search-product' in content
        is_blocked = content_length < 5000 or 'ERR_' in content or 'location.reload' in content
    else:
        # Page 2+: RSC response (Next.js React Server Component format)
        has_products = '"product' in content.lower() or 'search-product' in content or 'srp_' in content
        is_blocked = content_length < 50000  # RSC responses are usually large

    return has_products, is_blocked


def crawl_multipage(keyword="노트북", max_pages=3):
    """
    Crawl multiple pages using curl-cffi

    Args:
        keyword: Search keyword
        max_pages: Number of pages to crawl

    Returns:
        bool: True if all pages successful
    """
    print(f"\n{'='*60}")
    print(f"curl-cffi Multi-Page Crawler")
    print(f"{'='*60}\n")

    # Initialize managers
    db = DbManager()
    file_manager = FileManager()

    # Load latest TLS fingerprint and cookies from DB
    print(f"[1/3] Loading latest TLS fingerprint from database...")
    data = db.get_latest_fingerprint()

    if not data:
        print(f"[ERROR] No TLS fingerprint found in database")
        print(f"[INFO] Please run main-pc.py first to collect TLS data")
        return False

    device_name = data['device_name']
    chrome_version = device_name.split()[1] if 'Chrome' in device_name else 'Unknown'

    print(f"  Device: {device_name}")
    print(f"  Collected: {data['collected_at']}")
    print(f"  JA3 Hash: {data['ja3_hash']}")
    print(f"  Cookies: {len(data['cookies'])} items")

    # Build TLS configuration
    print(f"\n[2/3] Building TLS configuration...")
    extra_fp = TlsConfig.build_extra_fp(data['tls_data'])
    cookie_dict = CookieHandler.to_dict(data['cookies'])

    print(f"  TLS version: {data['tls_data'].get('tls_version')}")
    print(f"  extra_fp: {extra_fp}")

    # Create Session for automatic cookie management
    session = requests.Session()

    # Properly set cookies using response.cookies format (curl-cffi compatible)
    # Convert dict to cookies and add to session
    for name, value in cookie_dict.items():
        session.cookies.set(name, value, domain='.coupang.com', path='/')

    print(f"  Session initialized with {len(cookie_dict)} cookies")

    # Debug: Show initial cookies
    print(f"  Initial cookies: {', '.join(list(cookie_dict.keys())[:5])}{'...' if len(cookie_dict) > 5 else ''}")

    # Verify TLS fingerprint before crawling
    verify_headers = TlsConfig.build_headers(chrome_version, 1, None, cookie_header='')
    browserleaks_data = verify_tls(session, extra_fp, verify_headers, "tls.json")

    # Compare DB TLS data with actual browserleaks data
    if browserleaks_data:
        compare_tls_data(data['tls_data'], browserleaks_data)

    # Start crawling
    print(f"\n[3/3] Crawling {max_pages} pages...")
    print(f"  Keyword: {keyword}")
    print(f"  Target pages: {max_pages}\n")

    page_results = []
    traceid = None

    for page_num in range(1, max_pages + 1):
        print(f"  [Page {page_num}]")

        # Build URL
        url, traceid = build_search_url(keyword, page_num, traceid)
        print(f"    URL: {url[:70]}...")

        # Build headers (Session manages cookies automatically, so pass empty string)
        referer = page_results[-1]['url'] if page_num > 1 else None
        headers = TlsConfig.build_headers(chrome_version, page_num, referer, cookie_header='')

        # Debug: Show cookies before request
        try:
            current_cookies = session.cookies.get_dict()
            print(f"    [DEBUG] Cookies before request: {len(current_cookies)} items")
            print(f"    [DEBUG] Cookie names: {', '.join(list(current_cookies.keys())[:3])}{'...' if len(current_cookies) > 3 else ''}")
        except Exception as e:
            print(f"    [DEBUG] Could not read session cookies: {e}")

        try:
            # Send request using Session (cookies managed automatically)
            start_time = time.time()
            response = session.get(
                url,
                headers=headers,
                extra_fp=extra_fp,
                timeout=10
            )
            elapsed_ms = int((time.time() - start_time) * 1000)

            # Session automatically handles Set-Cookie (curl-cffi feature)
            # Debug: Show cookies after auto-update
            try:
                updated_cookies = session.cookies.get_dict()
                print(f"    [DEBUG] Cookies after request: {len(updated_cookies)} items")
                if len(updated_cookies) != len(current_cookies):
                    print(f"    [DEBUG] ✓ Cookie count changed: {len(current_cookies)} -> {len(updated_cookies)}")
                    # Show what changed
                    new_cookies = set(updated_cookies.keys()) - set(current_cookies.keys())
                    if new_cookies:
                        print(f"    [DEBUG] New cookies: {', '.join(list(new_cookies)[:3])}{'...' if len(new_cookies) > 3 else ''}")
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
                ext = 'html' if page_num == 1 else 'rsc.txt'
                filepath = file_manager.save_page(content, page_num, chrome_version, ext)
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

                # Save failed response for debugging
                ext = 'failed.html' if page_num == 1 else 'failed.rsc.txt'
                filepath = file_manager.save_page(content, page_num, chrome_version, ext)
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
            page_results.append({
                'page': page_num,
                'url': url,
                'success': False,
                'error': str(e)
            })
            break

    # Save updated cookies to database
    print(f"\n{'='*60}")
    print(f"COOKIE UPDATE")
    print(f"{'='*60}")

    try:
        # Get final cookies from session
        final_cookies = []

        # Try different methods to get cookies
        try:
            # Method 1: Try get_dict() first
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
            print(f"Final cookies (dict method): {len(final_cookies)} items")

        except (AttributeError, TypeError):
            # Method 2: Fallback to jar iteration
            import http.cookiejar
            if hasattr(session.cookies, 'jar') and isinstance(session.cookies.jar, http.cookiejar.CookieJar):
                for cookie in session.cookies.jar:
                    final_cookies.append({
                        'name': cookie.name,
                        'value': cookie.value,
                        'domain': cookie.domain,
                        'path': cookie.path,
                        'expires': cookie.expires,
                        'httpOnly': getattr(cookie, 'http_only', False),
                        'secure': cookie.secure,
                        'sameSite': None,
                    })
                print(f"Final cookies (jar method): {len(final_cookies)} items")
            else:
                print(f"Warning: Could not extract cookies from session")
                final_cookies = data['cookies']  # Use original cookies
                print(f"Using original cookies: {len(final_cookies)} items")

        # Save to database with cookie_type='crawled'
        # Maintain link to original TLS fingerprint
        cookie_id = db.save_cookies(
            device_name=device_name,
            browser='chrome',
            os_version='Windows 10',
            tls_fingerprint_id=data['tls_fingerprint_id'],  # Keep original fingerprint link
            cookie_data=final_cookies,
            collected_at=datetime.now(),
            cookie_type='crawled'
        )

        print(f"Cookies saved to DB (ID: {cookie_id}, type: 'crawled')")

    except Exception as e:
        print(f"Cookie save error: {e}")

    # Save results summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total pages: {len(page_results)}")

    successful_pages = [r for r in page_results if r.get('success')]
    print(f"Successful: {len(successful_pages)}")

    for result in page_results:
        status = "SUCCESS" if result.get('success') else "FAILED"
        print(f"  Page {result['page']}: {status}")

    # Save results to JSON
    major_version = chrome_version.split('.')[0]
    results_file = file_manager.save_results({
        'keyword': keyword,
        'max_pages': max_pages,
        'chrome_version': chrome_version,
        'device_name': device_name,
        'results': page_results,
        'summary': {
            'total': len(page_results),
            'successful': len(successful_pages)
        }
    }, f'results_chrome{major_version}.json')

    print(f"\nResults saved: {results_file}")

    return len(successful_pages) == max_pages


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python curlcffi.py <keyword> [max_pages]")
        print("Example: python curlcffi.py 노트북 3")
        print("\nNote: Uses latest TLS fingerprint from database")
        sys.exit(1)

    keyword = sys.argv[1]
    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    success = crawl_multipage(keyword, max_pages)
    sys.exit(0 if success else 1)

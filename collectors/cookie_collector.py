"""
Cookie Collector using nodriver
- Launch Chrome with specific version
- Navigate to Coupang
- Collect cookies
"""

import asyncio
import nodriver as uc
from pathlib import Path
import json
from datetime import datetime
from .tls_extractor import TlsExtractor
import warnings
import sys
import os

# Load config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import TIMEOUTS, WAIT_TIMES

# Suppress ResourceWarning and RuntimeError for subprocess cleanup on Windows
if sys.platform == 'win32':
    warnings.filterwarnings('ignore', category=ResourceWarning)
    warnings.filterwarnings('ignore', message='Event loop is closed')

class CookieCollector:
    def __init__(self, chrome_path, user_data_dir, headless=False, search_keyword=None, max_pages=1):
        """
        Args:
            chrome_path: Path to chrome.exe
            user_data_dir: User data directory for Chrome profile
            headless: Run in headless mode
            search_keyword: Optional search keyword
            max_pages: Number of pages to navigate (default: 1)
        """
        self.chrome_path = chrome_path
        self.user_data_dir = Path(user_data_dir)
        self.headless = headless
        self.search_keyword = search_keyword
        self.max_pages = max_pages
        self.browser = None
        self.page = None
        self.all_request_headers = []  # Store all captured headers

    async def launch(self):
        """Launch Chrome browser"""
        print(f"[CookieCollector] Launching Chrome from: {self.chrome_path}")
        print(f"[CookieCollector] User data dir: {self.user_data_dir}")

        config = uc.Config()
        config.browser_executable_path = self.chrome_path
        config.user_data_dir = str(self.user_data_dir)

        # Launch browser
        self.browser = await uc.start(config)
        self.page = await self.browser.get('about:blank')

        print(f"[CookieCollector] Chrome launched successfully")

        return self.browser, self.page

    async def navigate_to_coupang(self):
        """Navigate to Coupang main page"""
        print(f"[CookieCollector] Navigating to Coupang...")

        await self.page.get('https://www.coupang.com/')
        await asyncio.sleep(WAIT_TIMES['main_page'])

        print(f"[CookieCollector] Page loaded successfully")

    async def check_if_blocked(self):
        """
        Check if page is blocked/captcha

        Returns:
            bool: True if blocked, False if normal
        """
        try:
            # Get page content with timeout
            html = await asyncio.wait_for(
                self.page.evaluate('document.documentElement.outerHTML'),
                timeout=TIMEOUTS['blocking_check']
            )

            # Check blocking indicators
            if not html or len(html) < 5000:
                return True

            # Check for known blocking patterns
            blocking_patterns = [
                'location.reload',
                'captcha',
                'blocked',
                'Access Denied',
                'ERR_HTTP2_PROTOCOL_ERROR',  # Chrome 131+ HTTP/2 issue
                'ERR_',
                'bot detection',
                'error-code'  # Chrome error page
            ]

            for pattern in blocking_patterns:
                if pattern.lower() in html.lower():
                    return True

            # Check if search results exist (for search page)
            if 'np/search' in self.page.url:
                if 'product-list' not in html:
                    return True

            return False

        except asyncio.TimeoutError:
            print(f"[CookieCollector] Block check timed out - assuming blocked")
            return True
        except Exception as e:
            print(f"[CookieCollector] Block check error: {e}")
            return True

    async def perform_search(self, keyword):
        """
        Perform search using React-aware method with CDP network monitoring

        Args:
            keyword: Search keyword

        Returns:
            dict: Request headers captured via CDP
        """
        print(f"[CookieCollector] Performing search for: {keyword}")

        # Enable network monitoring
        await self.page.send(uc.cdp.network.enable())

        # Store captured request headers
        request_headers = []

        def capture_request(event):
            """Capture request headers (sync handler)"""
            try:
                url = str(event.request.url)
                if 'np/search' in url:
                    headers = dict(event.request.headers) if hasattr(event.request, 'headers') else {}
                    captured = {
                        'page': 1,
                        'url': url,
                        'method': event.request.method if hasattr(event.request, 'method') else 'GET',
                        'headers': headers,
                        'timestamp': datetime.now().isoformat()
                    }
                    request_headers.append(captured)
                    self.all_request_headers.append(captured)
                    print(f"[CookieCollector] Captured search request (page 1): {url[:100]}")
            except Exception as e:
                print(f"[CookieCollector] Handler error: {e}")

        # Add listener for network requests
        self.page.add_handler(uc.cdp.network.RequestWillBeSent, capture_request)

        # First, inject keyword into window object
        await self.page.evaluate(f'window.__searchKeyword = {json.dumps(keyword)};')

        # Execute search script
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

        await self.page.evaluate(search_script)

        # Wait for search to complete and page to fully load
        print(f"[CookieCollector] Waiting for search results to load...")
        await asyncio.sleep(WAIT_TIMES['search_page'] + 3)  # 2초 스크립트 delay + 페이지 로드 + 추가 버퍼

        # Wait for page to be fully loaded (check for product list)
        for attempt in range(15):  # Increased to 15 attempts (7.5 seconds)
            try:
                has_results = await self.page.evaluate(
                    'document.querySelector(".search-product-list") !== null || document.querySelector("#productList") !== null'
                )
                if has_results:
                    print(f"[CookieCollector] ✓ Search results loaded successfully")
                    break
            except:
                pass
            await asyncio.sleep(0.5)
        else:
            print(f"[CookieCollector] ⚠ Could not verify search results loaded")

        # Disable network monitoring
        try:
            await self.page.send(uc.cdp.network.disable())
        except Exception as e:
            print(f"[CookieCollector] Network disable warning: {e}")

        print(f"[CookieCollector] Search completed")

        return request_headers[0] if request_headers else None

    async def navigate_to_next_page(self, page_num):
        """
        Navigate to next page by clicking next button with CDP monitoring

        Args:
            page_num: Target page number for logging

        Returns:
            bool: True if navigation successful, False otherwise
        """
        print(f"[CookieCollector] Navigating to page {page_num}...")

        try:
            # Enable network monitoring
            await self.page.send(uc.cdp.network.enable())

            # Store captured request headers for this page
            page_request_headers = []

            def capture_page_request(event):
                """Capture request headers for page navigation"""
                try:
                    url = str(event.request.url)
                    # Capture ALL coupang.com requests
                    if 'coupang.com' in url:
                        headers = dict(event.request.headers) if hasattr(event.request, 'headers') else {}
                        captured = {
                            'page': page_num,
                            'url': url,
                            'method': event.request.method if hasattr(event.request, 'method') else 'GET',
                            'headers': headers,
                            'timestamp': datetime.now().isoformat()
                        }
                        page_request_headers.append(captured)
                        self.all_request_headers.append(captured)
                        # Only print significant requests
                        if any(pattern in url for pattern in ['np/search', 'browse', 'products', 'api']):
                            print(f"[CookieCollector] Captured request (page {page_num}): {url[:100]}")
                except Exception as e:
                    print(f"[CookieCollector] Handler error: {e}")

            # Add listener
            self.page.add_handler(uc.cdp.network.RequestWillBeSent, capture_page_request)

            # Log current URL before click
            current_url = self.page.url
            print(f"[CookieCollector] Current URL before click: {current_url[:100]}")

            # Save HTML for debugging
            try:
                html_content = await self.page.evaluate('document.documentElement.outerHTML')
                debug_dir = self.user_data_dir.parent / 'logs'
                debug_dir.mkdir(parents=True, exist_ok=True)
                debug_file = debug_dir / f'page_{page_num}_before_click.html'
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print(f"[CookieCollector] HTML saved to: {debug_file}")
            except Exception as e:
                print(f"[CookieCollector] Failed to save HTML: {e}")

            # Wait for next button to appear and be clickable
            print(f"[CookieCollector] Waiting for next page button...")
            button_found = False

            # Wait a bit for page to stabilize
            await asyncio.sleep(WAIT_TIMES['button_stabilize'])

            for attempt in range(WAIT_TIMES['button_find_attempts']):
                try:
                    # Try to click the button directly
                    click_result = await self.page.evaluate('''
                        (function() {
                            const btn = document.querySelector('a[data-page="next"]');
                            if (btn) {
                                return { found: true, text: btn.textContent.trim(), href: btn.href };
                            }
                            return { found: false };
                        })()
                    ''')

                    # Check result type and extract data
                    if isinstance(click_result, dict):
                        if click_result.get('found'):
                            print(f"[CookieCollector] ✓ Button found: '{click_result.get('text')}'")
                            button_found = True
                            break
                    elif isinstance(click_result, list) and len(click_result) > 0:
                        # Sometimes nodriver returns list instead of dict
                        print(f"[CookieCollector] ✓ Button found (detected)")
                        button_found = True
                        break

                    # Not found, print debug info every attempt
                    if attempt % 2 == 0:
                        max_attempts = WAIT_TIMES['button_find_attempts']
                        print(f"[CookieCollector] Button not found (attempt {attempt + 1}/{max_attempts}), waiting...")

                except Exception as e:
                    if attempt == 0:
                        print(f"[CookieCollector] Check error (will retry): {type(e).__name__}")

                await asyncio.sleep(WAIT_TIMES['button_retry_interval'])

            if not button_found:
                max_wait_time = WAIT_TIMES['button_stabilize'] + (WAIT_TIMES['button_find_attempts'] * WAIT_TIMES['button_retry_interval'])
                print(f"[CookieCollector] ERROR: Next button not found after {max_wait_time:.1f} seconds")
                print(f"[CookieCollector] Check saved HTML at: {debug_dir / f'page_{page_num}_before_click.html'}")
                return False

            # Click next page button
            print(f"[CookieCollector] Clicking next button...")

            click_success = await self.page.evaluate('''
                (function() {
                    const btn = document.querySelector('a[data-page="next"]');
                    if (btn) {
                        btn.click();
                        return true;
                    }
                    return false;
                })()
            ''')

            if not click_success:
                print(f"[CookieCollector] ERROR: Failed to click next button")
                return False

            print(f"[CookieCollector] ✓ Next button clicked!")
            print(f"[CookieCollector]   Method: document.querySelector('a[data-page=\"next\"]').click()")

            # Wait for URL to change
            await asyncio.sleep(WAIT_TIMES['after_click'])

            # Log URL after navigation
            new_url = self.page.url
            print(f"[CookieCollector] New URL after click: {new_url[:100]}")

            # Wait for page to be fully loaded (increased wait time)
            await asyncio.sleep(WAIT_TIMES['search_page'])

            # Verify page content is loaded
            content_loaded = False
            for attempt in range(10):
                try:
                    has_content = await self.page.evaluate(
                        'document.querySelector(".search-product-list") !== null || document.querySelector("#productList") !== null'
                    )
                    if has_content:
                        content_loaded = True
                        print(f"[CookieCollector] ✓ Page {page_num} content loaded successfully")
                        break
                except:
                    pass
                await asyncio.sleep(0.5)

            if not content_loaded:
                print(f"[CookieCollector] WARNING: Could not verify page {page_num} content loaded")

            # Disable network monitoring
            try:
                await self.page.send(uc.cdp.network.disable())
            except Exception as e:
                print(f"[CookieCollector] Network disable warning: {e}")

            # Final success summary
            final_url = self.page.url
            print(f"\n[CookieCollector] ═══ Page {page_num} SUCCESS ═══")
            print(f"[CookieCollector]   URL: ...{final_url[-60:] if len(final_url) > 60 else final_url}")
            print(f"[CookieCollector]   Content: {'✓ Loaded' if content_loaded else '⚠ Warning'}")
            print(f"[CookieCollector] ═══════════════════════════════\n")

            return True

        except Exception as e:
            print(f"[CookieCollector] Navigation failed: {e}")
            return False

    async def get_cookies(self):
        """
        Get all cookies from current page

        Returns:
            list: Cookie objects
        """
        print(f"[CookieCollector] Collecting cookies...")

        try:
            # Method 1: Try CDP first (with short timeout)
            cookies = await asyncio.wait_for(
                self.page.send(uc.cdp.network.get_all_cookies()),
                timeout=TIMEOUTS['cookie_collection']
            )

            # Handle different response formats
            if isinstance(cookies, list):
                cookie_list = cookies
            elif hasattr(cookies, 'cookies'):
                cookie_list = cookies.cookies
            else:
                # Fallback: try to extract from dict
                cookie_list = cookies.get('cookies', []) if isinstance(cookies, dict) else []

            print(f"[CookieCollector] Collected {len(cookie_list)} cookies via CDP")
            return cookie_list

        except (asyncio.TimeoutError, Exception) as e:
            print(f"[CookieCollector] CDP failed ({e}), using JavaScript fallback...")

            # Method 2: JavaScript fallback - get cookies via document.cookie
            try:
                from .cookie_formatter import CookieFormatter

                cookie_string = await self.page.evaluate('document.cookie')

                # Parse cookie string using CookieFormatter
                cookie_list = CookieFormatter.parse_js_cookies(cookie_string)

                print(f"[CookieCollector] Collected {len(cookie_list)} cookies via JavaScript")
                return cookie_list

            except Exception as js_error:
                print(f"[CookieCollector] ERROR: Both methods failed - {js_error}")
                return []

    async def close(self):
        """Close browser"""
        if self.browser:
            try:
                # Stop browser gracefully
                self.browser.stop()
                await asyncio.sleep(WAIT_TIMES['browser_cleanup'])
                print(f"[CookieCollector] Browser closed")
            except Exception as e:
                # Ignore cleanup errors
                print(f"[CookieCollector] Browser closed (with cleanup warning)")

    async def collect(self):
        """
        Main collection workflow

        Returns:
            dict: {
                'cookies': [...],
                'main_page_cookies': [...],
                'search_page_cookies': [...],
                'tls_data': {...},
                'http2_data': {...},
                'collected_at': '2024-10-29T12:00:00',
                'cookie_count': 89,
                'search_blocked': False
            }
        """
        try:
            # 1. Launch browser
            await self.launch()

            # 2. Navigate to Coupang main page
            await self.navigate_to_coupang()

            # 2.5. Get main page cookies (baseline)
            print(f"[CookieCollector] Collecting main page cookies...")
            main_page_cookies = await self.get_cookies()
            print(f"[CookieCollector] Main page cookies: {len(main_page_cookies)}")

            # 3. Perform search if keyword provided
            request_headers = None
            search_blocked = False
            search_page_cookies = None

            if self.search_keyword:
                request_headers = await self.perform_search(self.search_keyword)

                # 3.5. Check if search was blocked on page 1
                search_blocked = await self.check_if_blocked()

                if search_blocked:
                    print(f"[CookieCollector] WARNING: Search page 1 appears to be blocked!")
                    print(f"[CookieCollector] Using main page cookies instead")
                    cookie_list = main_page_cookies
                else:
                    print(f"[CookieCollector] Search page 1 is normal")

                    # 3.6. Navigate to additional pages if max_pages > 1
                    if self.max_pages > 1:
                        print(f"[CookieCollector] Navigating to {self.max_pages - 1} additional pages...")

                        for page_num in range(2, self.max_pages + 1):
                            print(f"[CookieCollector] Moving to page {page_num}...")

                            # Navigate to next page with monitoring
                            nav_success = await self.navigate_to_next_page(page_num)

                            if not nav_success:
                                print(f"[CookieCollector] Could not navigate to page {page_num}")
                                break

                            # Check if blocked
                            page_blocked = await self.check_if_blocked()

                            if page_blocked:
                                print(f"[CookieCollector] WARNING: Page {page_num} appears to be blocked!")
                                break

                            print(f"[CookieCollector] Page {page_num} is normal")

                    # Collect cookies from final page
                    search_page_cookies = await self.get_cookies()
                    print(f"[CookieCollector] Final page cookies: {len(search_page_cookies)}")
                    cookie_list = search_page_cookies

                    # Wait 2 seconds before closing
                    print(f"[CookieCollector] Waiting 2 seconds before closing browser...")
                    await asyncio.sleep(2)
            else:
                # No search, use main page cookies
                cookie_list = main_page_cookies

            # 4. Extract TLS fingerprint
            tls_extractor = TlsExtractor(self.page)
            tls_info = await tls_extractor.extract()

            # 6. Convert cookies to serializable format using CookieFormatter
            from .cookie_formatter import CookieFormatter
            cookies_data = CookieFormatter.format_cookie_list(cookie_list, formatter_type='nodriver')

            # 7. Generate JA3 hash
            ja3_hash = tls_extractor.generate_ja3_hash(tls_info['tls_data'])

            # Convert cookie lists for storage using CookieFormatter
            main_cookies_data = CookieFormatter.format_cookie_list(main_page_cookies, formatter_type='nodriver')

            search_cookies_data = []
            if search_page_cookies:
                search_cookies_data = CookieFormatter.format_cookie_list(search_page_cookies, formatter_type='nodriver')

            result = {
                'cookies': cookies_data,
                'main_page_cookies': main_cookies_data,
                'search_page_cookies': search_cookies_data,
                'search_blocked': search_blocked,
                'tls_data': tls_info['tls_data'],
                'http2_data': tls_info['http2_data'],
                'ja3_hash': ja3_hash,
                'akamai_fingerprint': tls_info['http2_data']['akamai_fingerprint'],
                'collected_at': datetime.now().isoformat(),
                'cookie_count': len(cookies_data),
                'all_request_headers': self.all_request_headers  # Include all page headers
            }

            # Save request headers to log file if any captured
            if self.all_request_headers:
                log_dir = self.user_data_dir.parent / 'logs'
                log_dir.mkdir(parents=True, exist_ok=True)

                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                log_file = log_dir / f'request_headers_{timestamp}.json'

                with open(log_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'search_keyword': self.search_keyword,
                        'max_pages': self.max_pages,
                        'captured_at': datetime.now().isoformat(),
                        'total_requests': len(self.all_request_headers),
                        'requests': self.all_request_headers
                    }, f, indent=2, ensure_ascii=False)

                print(f"[CookieCollector] Request headers saved to: {log_file}")

            print(f"[CookieCollector] Collection completed:")
            print(f"  - Main page cookies: {len(main_cookies_data)}")
            if search_page_cookies:
                print(f"  - Search page cookies: {len(search_cookies_data)}")
            print(f"  - Using cookies: {len(cookies_data)} ({'main' if search_blocked else 'search'})")
            print(f"  - Search blocked: {search_blocked}")
            print(f"  - JA3 Hash: {ja3_hash}")

            return result

        finally:
            await self.close()

# Async wrapper for main-pc.py
def collect_cookies(chrome_path, user_data_dir, headless=False, search_keyword=None, max_pages=1):
    """
    Synchronous wrapper for cookie collection

    Args:
        chrome_path: Path to chrome.exe
        user_data_dir: User data directory
        headless: Headless mode
        search_keyword: Optional search keyword
        max_pages: Number of pages to navigate (default: 1)

    Returns:
        dict: Collection result
    """
    collector = CookieCollector(chrome_path, user_data_dir, headless, search_keyword, max_pages)

    # Run async collection with proper cleanup
    try:
        result = asyncio.run(collector.collect())
        return result
    except RuntimeError as e:
        # Ignore "Event loop is closed" errors during cleanup
        if "Event loop is closed" in str(e):
            # This is expected, return the result if we have it
            raise
        raise
    finally:
        # Force cleanup of any remaining asyncio resources
        try:
            import gc
            gc.collect()
        except:
            pass

if __name__ == '__main__':
    # Test
    import sys

    if len(sys.argv) < 2:
        print("Usage: python cookie_collector.py <chrome_path>")
        sys.exit(1)

    chrome_path = sys.argv[1]
    user_data_dir = Path(__file__).parent.parent / 'user' / 'default' / 'profile'

    result = collect_cookies(chrome_path, user_data_dir)

    print(f"\n[Result]")
    print(f"  Cookies: {result['cookie_count']}")
    print(f"  Time: {result['collected_at']}")

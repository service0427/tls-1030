# TLS-1030 - Refactored TLS Fingerprint Collection & Crawling

Modular architecture for TLS fingerprint collection and curl-cffi based web crawling.

## Features

- **Modular Design**: Reusable modules for DB, TLS, cookies, and file management
- **main-pc.py**: Collect TLS fingerprints and cookies using nodriver
- **curlcffi.py**: Multi-page crawling using curl-cffi with collected TLS data
- **Clean Output**: All temporary files organized in `output/` directory

## Directory Structure

```
tls-1030/
├── main-pc.py          # TLS & cookie collector
├── curlcffi.py         # Multi-page crawler
├── config.py           # Configuration settings
├── requirements.txt    # Python dependencies
├── .env                # Environment variables (create from .env.example)
│
├── modules/            # Shared modules
│   ├── db_manager.py       # Database operations
│   ├── tls_config.py       # TLS configuration builder
│   ├── cookie_handler.py   # Cookie format conversion
│   └── file_manager.py     # File I/O operations
│
├── utils/              # Utilities
│   ├── traceid.py          # TraceID generator
│   └── chrome_detector.py  # Chrome version detection
│
├── collectors/         # Data collectors
│   ├── cookie_collector.py # Main collector logic
│   └── tls_extractor.py    # TLS data extraction
│
├── output/             # All outputs saved here
│   ├── html/               # HTML/RSC responses
│   ├── json/               # JSON results and cookies
│   └── logs/               # Request headers and logs
│
└── user/               # User data directories
    └── {version}/          # Per-version user profiles
```

## Setup

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials
   ```

3. **Verify Chrome versions**
   ```bash
   python main-pc.py --list
   ```

## Usage

### 1. Collect TLS Fingerprint & Cookies

```bash
# Collect with system Chrome (default)
python main-pc.py

# Collect with specific version
python main-pc.py --version 142

# Collect with search (multi-page)
python main-pc.py --search 노트북 --page 3

# List available Chrome versions
python main-pc.py --list
```

### 2. Crawl Using curl-cffi

```bash
# Crawl 3 pages (uses latest TLS data from DB)
python curlcffi.py 노트북 3

# Crawl 5 pages with different keyword
python curlcffi.py 마우스 5
```

## Output Files

All outputs are saved to organized directories:

- **HTML/RSC**: `output/html/page_{num}_chrome{ver}.{ext}`
- **Results**: `output/json/results_chrome{ver}.json`
- **Cookies**: `output/json/cookies_chrome{ver}_{timestamp}.json`
- **Logs**: `output/logs/request_headers_chrome{ver}_{timestamp}.json`

## Module Usage Examples

### DbManager

```python
from modules import DbManager

db = DbManager()

# Get latest TLS fingerprint
data = db.get_latest_fingerprint()

# Save TLS fingerprint
tls_id = db.save_tls_fingerprint(
    device_name="Chrome 142.0.7444.60",
    browser='chrome',
    os_version='Windows 10',
    tls_data=tls_data,
    http2_data=http2_data,
    ja3_hash=ja3_hash,
    akamai_fingerprint=akamai_fp,
    collected_at=datetime.now()
)
```

### TlsConfig

```python
from modules import TlsConfig

# Build extra_fp for curl-cffi
extra_fp = TlsConfig.build_extra_fp(tls_data)

# Build headers for page 1 (HTML)
headers = TlsConfig.build_headers(
    chrome_version="142.0.7444.60",
    page_num=1,
    cookie_header=cookie_str
)

# Build headers for page 2+ (RSC)
headers = TlsConfig.build_headers(
    chrome_version="142.0.7444.60",
    page_num=2,
    referer=previous_url,
    cookie_header=cookie_str
)
```

### CookieHandler

```python
from modules import CookieHandler

# Convert to header string
cookie_header = CookieHandler.to_header_string(cookies)

# Convert to dictionary
cookie_dict = CookieHandler.to_dict(cookies)
```

### FileManager

```python
from modules import FileManager

fm = FileManager()

# Save HTML page
fm.save_html(html_content, 'page_1.html')

# Save JSON results
fm.save_json(results, 'results.json')

# Save page with auto-naming
fm.save_page(content, page_num=1, chrome_version='142', ext='html')
```

## Differences from tls-1029

1. **Modular Architecture**: All common logic extracted to reusable modules
2. **Clean Output**: No temporary files in root directory
3. **Simplified Scripts**: main-pc.py and curlcffi.py are much cleaner
4. **Better Separation**: DB, TLS, cookies, files all in separate modules
5. **Easier Testing**: Each module can be tested independently

## Notes

- Uses curl_cffi 0.13.0 with limited `extra_fp` support
- Only `tls_min_version`, `tls_grease`, and `tls_permute_extensions` are used
- Page 2+ uses Next.js RSC (React Server Components) format
- Automatic latest TLS data selection from database

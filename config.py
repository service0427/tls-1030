"""
Configuration settings
"""

# Database settings (loaded from .env)
# DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

# Chrome versions path
CHROME_VERSIONS_PATH = r'D:\dev\git\local-packet-coupang\chrome-versions\files'

# Timeouts (seconds)
TIMEOUTS = {
    'total_collection': 120,
    'page_load': 10,
    'search_load': 15,
    'element_wait': 5,
    'blocking_check': 2,
    'cookie_collection': 5,
}

# Wait times (seconds)
WAIT_TIMES = {
    'main_page': 2,
    'search_page': 3,
    'after_search': 3,
    'page_verification': 7.5,
    'between_pages': (3, 5),  # Random range
    'tls_page': 3,
    'blocking_check': 2,
    'browser_cleanup': 0.5,

    # Page navigation settings (for navigate_to_next_page)
    'button_stabilize': 0.5,      # Wait before searching for next button
    'button_find_attempts': 3,    # Max attempts to find next button (attempts * retry_interval = max wait)
    'button_retry_interval': 0.2, # Interval between button search attempts
    'after_click': 0.3,           # Wait after clicking next button
}

# Output directories
OUTPUT_DIRS = {
    'base': 'output',
    'html': 'output/html',
    'json': 'output/json',
    'logs': 'output/logs',
}

# User data directory (for main-pc.py)
USER_DATA_DIR = 'user'

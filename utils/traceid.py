"""
TraceID Generator for Coupang Search
"""
import time
import string


def generate_traceid():
    """
    Generate Coupang traceId (timestamp-based base36)

    Returns:
        str: 8-character traceId (e.g., 'mha2ebbm')
    """
    # Current time in milliseconds
    timestamp_ms = int(time.time() * 1000)

    # base36 characters (0-9, a-z)
    base36_chars = string.digits + string.ascii_lowercase

    # Convert to base36
    result = []
    ts = timestamp_ms
    while ts > 0:
        result.append(base36_chars[ts % 36])
        ts //= 36

    # Reverse and return (8 characters)
    return ''.join(reversed(result))


if __name__ == '__main__':
    # Test
    print("Testing traceId generation:")
    for i in range(5):
        traceid = generate_traceid()
        print(f"  {i+1}: {traceid}")
        time.sleep(0.1)

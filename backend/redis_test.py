"""
Test Redis Connection
Verify that the Redis database is properly configured and accessible
"""

import os
import redis
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

def test_redis_connection():
    """Test Redis connection and basic operations"""
    print(f"Testing Redis connection to: {REDIS_URL}")
    print("-" * 60)

    try:
        # Connect to Redis
        r = redis.from_url(REDIS_URL, decode_responses=True)

        # Test connection
        pong = r.ping()
        print(f"[OK] Connection successful: {pong}")

        # Test basic operations
        print("\nTesting basic operations...")

        # Set a test key
        r.set('test_key', 'test_value')
        print("[OK] SET test_key = 'test_value'")

        # Get the value back
        value = r.get('test_key')
        print(f"[OK] GET test_key = '{value}'")

        # Test expiration
        r.setex('temp_key', 10, 'temporary_value')
        print("[OK] SETEX temp_key (10 second expiration)")

        # Get server info
        info = r.info()
        print(f"\n[OK] Redis Server Info:")
        print(f"  - Version: {info.get('redis_version')}")
        print(f"  - Used Memory: {info.get('used_memory_human')}")
        print(f"  - Connected Clients: {info.get('connected_clients')}")

        # Clean up test keys
        r.delete('test_key', 'temp_key')
        print(f"\n[OK] Test keys cleaned up")

        print("-" * 60)
        print("All tests passed! Redis is ready to use.")
        return True

    except Exception as e:
        print(f"[FAIL] Connection failed: {e}")
        return False

if __name__ == '__main__':
    success = test_redis_connection()
    exit(0 if success else 1)

import json
import functools
import redis
import logging

logger = logging.getLogger(__name__)

def get_redis_client(redis_url):
    """
    Initialize Redis client.
    """
    try:
        client = redis.from_url(redis_url, decode_responses=True)
        client.ping()
        logger.info("Successfully connected to Redis.")
        return client
    except Exception as e:
        logger.warning(f"Failed to connect to Redis. Caching will be disabled. Error: {e}")
        return None

def cache_response(redis_client, prefix, expire=300):
    """
    Decorator to cache API responses in Redis.
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if not redis_client:
                return f(*args, **kwargs)
            
            # Simple key based on function name and args
            cache_key = f"{prefix}:{f.__name__}:{args}:{kwargs}"
            
            try:
                cached_val = redis_client.get(cache_key)
                if cached_val:
                    logger.info(f"Cache hit for key: {cache_key}")
                    return json.loads(cached_val)
            except Exception as e:
                logger.error(f"Error reading from cache: {e}")
            
            response = f(*args, **kwargs)
            
            try:
                # If response is a tuple (data, status_code), cache only if 200
                data = response
                if isinstance(response, tuple) and len(response) == 2:
                    if response[1] != 200:
                        return response
                    data = response[0]
                
                # Check if it's a Flask Response object
                from flask import Response
                if isinstance(data, Response):
                    # We don't easily cache Response objects here without more logic
                    return response

                redis_client.setex(cache_key, expire, json.dumps(data))
                logger.info(f"Cached response for key: {cache_key}")
            except Exception as e:
                logger.error(f"Error writing to cache: {e}")
                
            return response
        return wrapper
    return decorator

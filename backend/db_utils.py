import time
import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

logger = logging.getLogger(__name__)

def get_db_connection(mongo_uri, database_name, max_retries=5, retry_delay=2):
    """
    Establish a connection to MongoDB with retry logic.
    """
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    
    for i in range(max_retries):
        try:
            # The ismaster command is cheap and does not require auth.
            client.admin.command('ismaster')
            logger.info("Successfully connected to MongoDB.")
            return client[database_name], client
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            if i < max_retries - 1:
                logger.warning(f"MongoDB connection failed (attempt {i+1}/{max_retries}). Retrying in {retry_delay}s... Error: {e}")
                time.sleep(retry_delay)
            else:
                logger.error(f"Could not connect to MongoDB after {max_retries} attempts.")
                raise e
    return None, None

def check_db_health(db):
    """
    Check if the database is accessible.
    """
    try:
        db.command('ping')
        return True
    except Exception:
        return False

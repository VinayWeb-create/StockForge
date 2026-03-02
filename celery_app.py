from celery import Celery
import config

app_config = config.get_config()

def make_celery(app_name):
    celery = Celery(
        app_name,
        broker=app_config.REDIS_URL,
        backend=app_config.REDIS_URL
    )
    
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
    )
    
    return celery

celery = make_celery('stockforge')

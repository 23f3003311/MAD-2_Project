import os
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_caching import Cache
from flask_mail import Mail
from celery import Celery
db = SQLAlchemy()
jwt = JWTManager()
cache = Cache()
mail = Mail()
_redis_url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
celery = Celery(
    broker=_redis_url,
    backend=_redis_url,
)

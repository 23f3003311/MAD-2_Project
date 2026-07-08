
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
os.environ["CELERY_WORKER"] = "true"
from app import create_app
from extensions import celery
flask_app = create_app()
import tasks.export_csv       
import tasks.daily_reminder   
import tasks.monthly_report   
__all__ = ["celery"]

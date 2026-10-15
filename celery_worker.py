import os
from celery import Celery
from celery.schedules import crontab
from config import Config

def make_celery(app_name=__name__):
    broker_url = os.environ.get('CELERY_BROKER_URL', Config.CELERY_BROKER_URL)
    result_backend = os.environ.get('CELERY_RESULT_BACKEND', Config.CELERY_RESULT_BACKEND)

    celery_app = Celery(
        app_name,
        broker=broker_url,
        backend=result_backend,
        include=['tasks']
    )

    celery_app.conf.update(
        timezone=Config.CELERY_TIMEZONE,
        enable_utc=True,
        task_serializer='json',
        result_serializer='json',
        accept_content=['json'],
        task_track_started=True,
        broker_connection_timeout=2.0,
        broker_connection_retry_on_startup=False,
        # Celery Beat Periodic Schedule
        beat_schedule={
            'send-daily-examination-reminders': {
                'task': 'tasks.send_daily_reminders',
                'schedule': crontab(hour=8, minute=0),  # Runs daily at 8:00 AM IST
            },
            'generate-monthly-admin-report': {
                'task': 'tasks.generate_monthly_admin_report_task',
                'schedule': crontab(day_of_month=1, hour=0, minute=0),  # 1st of every month
            }
        }
    )

    return celery_app

celery = make_celery()

if __name__ == '__main__':
    celery.start()

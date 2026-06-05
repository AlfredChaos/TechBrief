import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "techbrief.settings.local")

app = Celery("techbrief")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    return {
        "task_id": self.request.id,
        "name": self.name,
    }

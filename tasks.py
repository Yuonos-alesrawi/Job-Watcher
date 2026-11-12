from celery import Celery

import watcher
from config import CHECK_EVERY_SECONDS, REDIS_URL

app = Celery("job_watcher", broker=REDIS_URL)
app.conf.beat_schedule = {
    "check-jobs": {"task": "tasks.check_jobs", "schedule": float(CHECK_EVERY_SECONDS)},
}


@app.task(name="tasks.check_jobs")
def check_jobs():
    return watcher.run_check()

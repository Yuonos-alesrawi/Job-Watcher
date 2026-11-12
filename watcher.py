import logging
import time

import notify
import sources
import storage
from config import MAX_ALERTS_PER_RUN, PAUSE_BETWEEN_COMPANIES, load_companies
from filters import evaluate

log = logging.getLogger("watcher")


def format_alert(job, result):
    return f"{job.title}\n{job.company} | {job.location or 'n/a'} | score {result.score}\n{job.url}"


def run_check(companies=None, db_path=None):
    companies = load_companies() if companies is None else companies
    conn = storage.connect(db_path)
    summary = {"fetched": 0, "new": 0, "kept": 0, "excluded": 0, "errors": 0}
    alerts = []

    for entry in companies:
        try:
            jobs = list(sources.fetch(entry["source"], entry["name"]))
        except Exception as exc:  # one broken board must not stop the run
            log.warning("fetch failed for %s/%s: %s", entry["source"], entry["name"], exc)
            summary["errors"] += 1
            continue
        summary["fetched"] += len(jobs)
        for job in jobs:
            if not storage.is_new(conn, job):
                continue
            summary["new"] += 1
            result = evaluate(job)
            storage.save(conn, job, result)
            if result.keep:
                summary["kept"] += 1
                alerts.append((result.score, job, result))
            else:
                summary["excluded"] += 1
                log.info("excluded %s | %s | %s", job.company, job.title, ",".join(result.reasons))
        time.sleep(PAUSE_BETWEEN_COMPANIES)

    alerts.sort(key=lambda a: -a[0])
    for _, job, result in alerts[:MAX_ALERTS_PER_RUN]:
        notify.send(format_alert(job, result))
    if len(alerts) > MAX_ALERTS_PER_RUN:
        log.info("%d more matches not sent (limit %d)", len(alerts) - MAX_ALERTS_PER_RUN, MAX_ALERTS_PER_RUN)
    return summary

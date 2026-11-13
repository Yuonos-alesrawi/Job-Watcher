import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import notify
import sources
import storage
from config import (
    DEAD_BOARD_RETRY_DAYS, MAX_ALERTS_PER_RUN, MAX_WORKERS, PAUSE_BETWEEN_COMPANIES,
    PER_SOURCE_CONCURRENCY, load_companies,
)
from filters import evaluate

log = logging.getLogger("watcher")


def format_alert(job, result):
    return f"{job.title}\n{job.company} | {job.location or 'n/a'} | score {result.score}\n{job.url}"


def _fetch_one(entry, gates):
    """Runs in a worker thread: network only, no database access."""
    with gates[entry["source"]]:  # cap simultaneous requests to one site
        try:
            jobs = list(sources.fetch(entry["source"], entry["name"]))
            return entry, jobs, None
        except Exception as exc:  # one broken board must not stop the run
            return entry, None, exc
        finally:
            time.sleep(PAUSE_BETWEEN_COMPANIES)


def _http_status(exc):
    resp = getattr(exc, "response", None)
    return getattr(resp, "status_code", None)


def run_check(companies=None, db_path=None):
    companies = load_companies() if companies is None else companies
    conn = storage.connect(db_path)
    summary = {"fetched": 0, "new": 0, "kept": 0, "excluded": 0, "errors": 0, "skipped_dead": 0}
    alerts = []

    dead = storage.dead_boards(conn, DEAD_BOARD_RETRY_DAYS)
    todo = []
    for entry in companies:
        if storage.board_key(entry["source"], entry["name"]) in dead:
            summary["skipped_dead"] += 1
        else:
            todo.append(entry)

    gates = {s: threading.Semaphore(PER_SOURCE_CONCURRENCY) for s in sources.FETCHERS}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(_fetch_one, e, gates) for e in todo
                   if e["source"] in gates]
        for e in todo:
            if e["source"] not in gates:
                log.warning("unknown source %r for %s", e["source"], e["name"])
                summary["errors"] += 1

        # all database work happens here, in the main thread, as results arrive
        for fut in as_completed(futures):
            entry, jobs, exc = fut.result()
            if exc is not None:
                status = _http_status(exc)
                log.warning("fetch failed for %s/%s: %s", entry["source"], entry["name"], exc)
                summary["errors"] += 1
                if status in (404, 410):
                    storage.mark_board(conn, entry["source"], entry["name"], status)
                continue
            summary["fetched"] += len(jobs)
            for job in jobs:
                if not storage.is_new(conn, job):
                    continue
                summary["new"] += 1
                result = evaluate(job)
                storage.save(conn, job, result, commit=False)
                if result.keep:
                    summary["kept"] += 1
                    alerts.append((result.score, job, result))
                else:
                    summary["excluded"] += 1
                    log.info("excluded %s | %s | %s", job.company, job.title, ",".join(result.reasons))
            conn.commit()  # one commit per company instead of one per job

    alerts.sort(key=lambda a: -a[0])
    for _, job, result in alerts[:MAX_ALERTS_PER_RUN]:
        notify.send(format_alert(job, result))
    if len(alerts) > MAX_ALERTS_PER_RUN:
        log.info("%d more matches not sent (limit %d)", len(alerts) - MAX_ALERTS_PER_RUN, MAX_ALERTS_PER_RUN)
    if summary["skipped_dead"]:
        log.info("%d boards skipped (404 in the last %d days)", summary["skipped_dead"], DEAD_BOARD_RETRY_DAYS)
    return summary

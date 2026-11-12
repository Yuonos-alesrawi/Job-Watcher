"""Run one check without Celery. Use --dry-run to test with an in-memory DB."""
import argparse
import logging

import watcher

p = argparse.ArgumentParser()
p.add_argument("--dry-run", action="store_true", help="do not write seen.db (uses memory)")
args = p.parse_args()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
print(watcher.run_check(db_path=":memory:" if args.dry_run else None))

# job_watcher

Watches public job boards (Greenhouse, Lever and Ashby) every hour, drops the postings that break your rules, and sends the rest to Telegram.

## 1) Trial run (no Celery, no Telegram)

```
pip install -r requirements.txt
python run_once.py --dry-run
```
Matching jobs are printed to the screen. Excluded jobs show up in the log together with the reason.

## 2) Company list

Edit `companies.json`. The name is the last part of the company's job-board URL:

- `boards.greenhouse.io/<name>` -> `{"source": "greenhouse", "name": "<name>"}`
- `jobs.lever.co/<name>` -> `{"source": "lever", "name": "<name>"}`
- `jobs.ashbyhq.com/<name>` -> `{"source": "ashby", "name": "<name>"}`

The three names already in the file are examples only. Check that they are correct or replace them with your own list.

## 3) Telegram

1. Open @BotFather, create a bot with `/newbot`, and copy the token.
2. Send any message to your bot, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy the `chat.id`.
3. Copy `.env.example` to `.env` and fill in both values.

## 4) Running continuously

With Docker Compose (Redis, worker and beat):
```
docker compose up --build
```
Or manually (needs a running Redis):
```
celery -A tasks worker -l info
celery -A tasks beat -l info
```

## Exclusion rules (filters.py)

Every exclusion has a named reason:

| Reason | What it catches |
|---|---|
| `us_only` / `work_auth_us` / `citizenship` | "US based only", "authorized to work in the U.S.", "U.S. citizen" |
| `no_sponsorship` | "unable to provide visa sponsorship" and similar wording |
| `clearance` | Secret clearance, TS/SCI, public trust |
| `onsite_only` / `not_remote` / `hybrid_or_onsite` | "ON SITE ONLY", no sign of remote work, hybrid |
| `region_restricted` | "Remote - US", "Remote (Canada)", or a specific city, unless Worldwide / EMEA / Anywhere is stated |
| `senior_title` / `role_mismatch` | senior, lead, staff and similar titles, or a non-engineering title |
| `experience_years` | "3+ years ... experience" |

The order of alerts is decided by `score`: how many of your skills appear in the posting, worldwide wording, and the word "junior" in the title.

## Limits you should know about

- The tests (`python test_job_watcher.py`) run offline with fake data. **The code has not been tried against the real APIs**, so run `run_once.py --dry-run` first and check the results.
- The rules are text-based and can be wrong on some phrasings. Review the excluded-jobs log during the first days and adjust `filters.py`.
- The first run may find dozens of old postings. At most 20 alerts are sent per run (`MAX_ALERTS_PER_RUN`); the rest are recorded as seen.
- A passing job does not mean the company hires from your country. Check eligibility before applying.
- Do not lower `PAUSE_BETWEEN_COMPANIES` and do not check more often than hourly, out of respect for the public APIs.
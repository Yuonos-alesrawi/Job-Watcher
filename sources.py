"""Fetch jobs from the public job-board APIs and normalise them to Job."""
import html
import re

import requests

from config import REQUEST_TIMEOUT, USER_AGENT
from models import Job


def _get(url, **params):
    r = requests.get(
        url, params=params or None, timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    )
    r.raise_for_status()
    return r.json()


def _strip_html(s):
    s = html.unescape(s or "")           # Greenhouse returns escaped HTML
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def fetch_greenhouse(token):
    data = _get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs", content="true")
    for j in data.get("jobs", []):
        yield Job(
            source="greenhouse", company=token, job_id=str(j["id"]),
            title=j.get("title", ""),
            location=(j.get("location") or {}).get("name", "") or "",
            remote=None, url=j.get("absolute_url", ""),
            text=_strip_html(j.get("content", "")),
        )


def _lever_lists_text(lists):
    """Lever keeps responsibilities/requirements in 'lists', not in descriptionPlain."""
    parts = []
    for item in lists or []:
        parts.append(item.get("text", "") or "")
        parts.append(_strip_html(item.get("content", "")))
    return " ".join(p for p in parts if p)


def fetch_lever(slug):
    data = _get(f"https://api.lever.co/v0/postings/{slug}", mode="json")
    for j in data:
        cats = j.get("categories") or {}
        location = cats.get("location", "") or ""
        commitment = cats.get("commitment", "") or ""
        wt = (j.get("workplaceType") or "").lower()
        remote = True if wt == "remote" else (False if wt in ("on-site", "onsite", "hybrid") else None)
        if remote is None and re.search("remote", f"{location} {commitment}", re.I):
            remote = True
        # Lever splits a posting: the opening text, then "lists" (responsibilities,
        # requirements...), then "additional". All three are needed for the filters.
        parts = [f"Team: {cats.get('team', '') or ''}. Commitment: {commitment}.", j.get("descriptionPlain", "") or ""]
        for section in j.get("lists") or []:
            parts.append(section.get("text", "") or "")
            parts.append(_strip_html(section.get("content", "")))
        parts.append(j.get("additionalPlain", "") or "")
        yield Job(
            source="lever", company=slug, job_id=str(j["id"]),
            title=j.get("text", ""), location=location, remote=remote,
            url=j.get("hostedUrl", ""), text=" ".join(p for p in parts if p).strip(),
        )


def fetch_ashby(name):
    data = _get(f"https://api.ashbyhq.com/posting-api/job-board/{name}")
    for j in data.get("jobs", []):
        yield Job(
            source="ashby", company=name, job_id=str(j["id"]),
            title=j.get("title", ""), location=j.get("location", "") or "",
            remote=j.get("isRemote"), url=j.get("jobUrl", ""),
            text=j.get("descriptionPlain", "") or "",
        )


FETCHERS = {"greenhouse": fetch_greenhouse, "lever": fetch_lever, "ashby": fetch_ashby}


def fetch(source, name):
    return FETCHERS[source](name)

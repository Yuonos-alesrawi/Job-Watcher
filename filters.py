"""Rule-based pre-filter. Every exclusion has a named reason so you can audit it."""
import re
from dataclasses import dataclass, field

from config import REQUIRE_JUNIOR_SIGNAL

I = re.I

# --- hard exclusions found in the ads we reviewed (searched in title + location + text)
HARD_EXCLUDE = [
    ("us_only", re.compile(r"\b(u\.?s\.?a?|united states)[- ]?(based|only)\b|must (be located|reside|live) in the (u\.?s\.?|united states)", I)),
    ("work_auth_us", re.compile(r"(legally |currently )?(authorized|eligible) to work in the (u\.?s\.?a?|united states)|work authorization in the (u\.?s\.?|united states)", I)),
    ("no_sponsorship", re.compile(r"(unable|not able|cannot|can't|will not|won't|not) (to )?(be )?(eligible for |able to )?(provide |offer |support )?(visa |immigration |work visa )?sponsorship|no (visa |immigration )?sponsorship|without (the need for )?(visa )?sponsorship", I)),
    ("clearance", re.compile(r"security clearance|secret clearance|top secret|ts/sci|public trust|active secret", I)),
    ("citizenship", re.compile(r"\bu\.?s\.? citizen(ship)?\b|citizen(ship)? of the (u\.?s\.?|united states)", I)),
    ("onsite_only", re.compile(r"on[- ]?site only|in[- ]office only|must (start|work) (out of|from|in) (the|our) (\w+ )?office", I)),
    # "we are only considering candidates based in Eastern Europe", "applicants must be located in ..."
    ("text_region_restricted", re.compile(r"only (considering|hiring|accepting) (candidates|applicants)?\s*(based|located|residing|from|in)\b|(candidates|applicants) (must|need to|should) (be )?(based|located|residing|living) in", I)),
    # recruiting-agency / staff-leasing / freelance postings
    ("agency_posting", re.compile(r"bodyleasing|body[- ]?leasing|for agencies|agencies only|\bfreelance\b|\bc2c\b|corp[- ]to[- ]corp|contractor only", I)),
]

# "Candidates outside the U.S. would be engaged as independent contractors" makes the
# US work-authorization sentence irrelevant for you, so those two reasons are skipped.
CONTRACTOR_OK = re.compile(r"(outside|non[- ]?)\s*(of )?(the )?(u\.?s\.?a?|united states)[^.]{0,80}contractors?", I)
CONTRACTOR_SKIPPED = {"us_only", "work_auth_us"}

TITLE_ROLE = re.compile(r"\b(engineer|developer|programmer|software|scientist|swe)\b|python|back[- ]?end", I)
TITLE_NONDEV = re.compile(r"\b(analyst|consultant|marketing|sales|account\w*|recruit\w*|designer|specialist|coordinator)\b", I)
TITLE_SENIOR = re.compile(r"\b(senior|sr\.?|staff|principal|lead|manager|director|head|vp|architect|distinguished)\b", I)
TITLE_JUNIOR = re.compile(r"\b(junior|jr\.?|entry[- ]level|graduate|intern|associate|early career|trainee)\b|\b(engineer|developer) i\b", I)
TEXT_JUNIOR = re.compile(r"\b(?:junior|entry[- ]level|new[- ]grads?|new graduates?|recent graduates?|internship|early[- ]career)\b|\b0\s*[-\u2013]\s*[12]\s*years?\b", I)

# Only worldwide-style markers count as "open". Europe / EMEA / a country is a restriction.
GLOBAL_LOC = re.compile(r"worldwide|anywhere|global|open globally|mena|any ?time ?zone", I)
REMOTE_WORD = re.compile(r"remote|work from anywhere|distributed|anywhere|worldwide|open globally", I)
FULLY_REMOTE_TEXT = re.compile(r"fully remote|100% remote|remote[- ]first|work from anywhere", I)
ONSITE_LOC = re.compile(r"\bhybrid\b|on[- ]?site|in[- ]office", I)

# 2+ years of experience (a range like "0-2" or "1-2" is fine), or "several years".
YEARS = re.compile(
    r"(?<![\d\-\u2013\u2014])\b(?:[2-9]|1\d)\s*\+?\s*(?:[-\u2013]\s*\d+\s*)?years?\b[^.\n]{0,50}\b(?:experience|professional|industry|full[- ]stack|back[- ]?end|front[- ]?end|software|engineering|development|programming)"
    r"|\b(?:several|many|multiple) years\b", I)

MY_SKILLS = [re.compile(p, I) for p in (
    r"\bpython\b", r"\bdjango\b", r"\bfastapi\b", r"\bflask\b", r"\bcelery\b", r"\bredis\b",
    r"\bdocker\b", r"\brest(ful)?\b", r"\bwebsockets?\b", r"\bpostgres(ql)?\b", r"\bsql\b",
    r"\bgit\b", r"\bpandas\b", r"\bscikit", r"\btensorflow\b", r"\bback[- ]?end\b",
)]


@dataclass
class Result:
    keep: bool
    reasons: list = field(default_factory=list)  # why excluded (empty if kept)
    score: int = 0                               # ranking only, higher = better


def evaluate(job):
    title, loc, text = job.title or "", job.location or "", job.text or ""
    reasons = []

    if not TITLE_ROLE.search(title) or TITLE_NONDEV.search(title):
        reasons.append("role_mismatch")
    if TITLE_SENIOR.search(title):
        reasons.append("senior_title")
    if REQUIRE_JUNIOR_SIGNAL and not (TITLE_JUNIOR.search(title) or TEXT_JUNIOR.search(text)):
        reasons.append("no_junior_signal")

    remote = job.remote
    if remote is None:
        remote = bool(REMOTE_WORD.search(loc) or REMOTE_WORD.search(title) or FULLY_REMOTE_TEXT.search(text))
    if not remote:
        reasons.append("not_remote")
    else:
        if ONSITE_LOC.search(loc):
            reasons.append("hybrid_or_onsite")
        # "Remote - US", "Remote (Canada)", "Europe", "Cairo": anything beyond plain "remote"
        # without a worldwide marker is a region restriction.
        if loc and not GLOBAL_LOC.search(loc):
            leftover = re.sub(r"remote|[-\u2013\u2014,()/|:\s]+", "", loc, flags=I)
            if leftover:
                reasons.append("region_restricted")

    hay = f"{title}\n{loc}\n{text}"
    contractor_ok = bool(CONTRACTOR_OK.search(hay))
    for label, pattern in HARD_EXCLUDE:
        if contractor_ok and label in CONTRACTOR_SKIPPED:
            continue
        if pattern.search(hay):
            reasons.append(label)
    if YEARS.search(text):
        reasons.append("experience_years")

    score = sum(1 for p in MY_SKILLS if p.search(f"{title} {text}"))
    if GLOBAL_LOC.search(loc) or re.search(r"worldwide|work from anywhere|any ?time ?zone", text, I):
        score += 2
    if TITLE_JUNIOR.search(title):
        score += 2

    return Result(keep=not reasons, reasons=reasons, score=score)

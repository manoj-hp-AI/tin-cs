# Validate the ledger and the report

Use this code unchanged. It checks facts the run has already recorded; it never fetches a page.
Build one `ledger` dict, call `check_ledger(ledger)` and fix every problem it returns by
correcting the evidence, not by loosening a classification. Write the report, then call
`check_report(ledger, report_text)`. `counts(ledger)` gives the totals to state in the report.

```text
ledger = {
  "own_domains": ["example.com"],          # the business's own site(s), from project files
  "max_targets": 8,                        # the max_targets input, 3-12
  "opened": 12,                            # pages actually opened; must equal len(pages)
  "pages": [{
    "url": "https://...",                  # final URL after redirects
    "status": "pursue" | "hold" | "reject",
    "reason": "",                          # "" for pursue; a code below for hold and reject
    "checked": "YYYY-MM-DD",               # the run date (UTC)
    "published": "YYYY-MM-DD" | None,      # date visible on the page, never guessed
    "options_count": 9,                    # options the page evaluates or lists
    "competitors_listed": ["Name"],
    "company_listed": False,
    "paid": False,                         # placement is paid, sponsored or an undisclosed affiliate list
    "publisher_is_competitor": False,
    "route": {"kind": "pr" | "form" | "email" | "none", "url": "https://..."},
    "ask": "...", "blurb": "...", "disclosure": "...",   # pursue pages only
    "blurb_facts": ["project/file/path.md"],             # pursue pages only
    "check_first": ["..."],                              # pursue pages only, optional
  }],
}
```

```python
import re
from datetime import date
from urllib.parse import urlsplit

MAX_PAGES = 25
FRESH_DAYS = 731  # two years
STATUSES = ("pursue", "hold", "reject")
REJECT_REASONS = (
    "ALREADY_LISTED",
    "COMPETITOR_OWNED",
    "PAY_TO_PLAY",
    "THIN",
    "STALE",
    "MISFIT",
    "NO_PATH",
    "UNVERIFIABLE",
)
HOLD_REASONS = ("UNDATED", "NO_PATH", "OVERFLOW")
ROUTE_KINDS = ("pr", "form", "email", "none")
HEADINGS = (
    "## Company fact card",
    "## Placement pack",
    "## Held pages",
    "## Rejected pages",
    "## Limits",
)
HYPE = re.compile(
    r"\b(best|leading|number one|world-class|cutting-edge|revolutionary|game-changing"
    r"|award-winning|industry-leading|top-rated)\b|#1",
    re.I,
)


def host(url):
    """Lower-case host without a leading www., or None when the URL is not http(s)."""
    if not isinstance(url, str):
        return None
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    name = parts.hostname.lower()
    return name[4:] if name.startswith("www.") else name


def _is_own(name, own):
    return any(name == domain or name.endswith("." + domain) for domain in own)


def _day(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(value)
    return date.fromisoformat(value)


def _text(page, key, low, high):
    value = page.get(key)
    if not isinstance(value, str) or not low <= len(value.split()) <= high:
        return [f"{key} must be {low}-{high} words"]
    return []


def _check_page(page, own):
    if not isinstance(page, dict):
        return ["must be an object"]
    problems = []
    name = host(page.get("url"))
    if name is None:
        problems.append("url must be an http(s) URL")
    status, reason = page.get("status"), page.get("reason", "")
    if status not in STATUSES:
        return problems + [f"status must be one of {STATUSES}"]
    try:
        checked, published = _day(page.get("checked")), _day(page.get("published"))
    except ValueError:
        return problems + ["checked and published must be YYYY-MM-DD (published may be null)"]
    if checked is None:
        return problems + ["checked date is required"]
    age = (checked - published).days if published else None
    route = page.get("route")
    kind = route.get("kind") if isinstance(route, dict) else None
    if kind not in ROUTE_KINDS:
        problems.append(f"route.kind must be one of {ROUTE_KINDS}")

    if status == "reject":
        if reason not in REJECT_REASONS:
            problems.append(f"reject reason must be one of {REJECT_REASONS}")
        evidence = {
            "PAY_TO_PLAY": page.get("paid") is True,
            "COMPETITOR_OWNED": page.get("publisher_is_competitor") is True,
            "ALREADY_LISTED": page.get("company_listed") is True,
            "STALE": age is not None and age > FRESH_DAYS,
            "NO_PATH": kind == "none",
        }
        if reason in evidence and not evidence[reason]:
            problems.append(f"{reason} is not supported by the recorded evidence")
    elif status == "hold":
        if reason not in HOLD_REASONS:
            problems.append(f"hold reason must be one of {HOLD_REASONS}")
        if reason == "UNDATED" and published is not None:
            problems.append("UNDATED needs published to be null")
        if reason == "NO_PATH" and kind != "none":
            problems.append("NO_PATH needs route.kind none")
    else:
        problems += _check_pursue(page, name, own, age, kind)
    return problems


def _check_pursue(page, name, own, age, kind):
    problems = []
    if page.get("reason", "") != "":
        problems.append("a pursue page has no reason code")
    if name and _is_own(name, own):
        problems.append("the business's own domain is not a placement target")
    for key in ("company_listed", "paid", "publisher_is_competitor"):
        if page.get(key) is not False:
            problems.append(f"{key} must be recorded as false for a pursue page")
    options = page.get("options_count")
    if type(options) is not int or options < 3:
        problems.append("options_count must be at least 3")
    competitors = page.get("competitors_listed")
    if not isinstance(competitors, list) or not competitors:
        problems.append("competitors_listed must name at least one competitor on the page")
    if age is None or not 0 <= age <= FRESH_DAYS:
        problems.append("published must be a visible date within the last 24 months")
    if kind not in ("pr", "form", "email"):
        problems.append("a pursue page needs a published route: pr, form or email")
    else:
        url = page["route"].get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://", "mailto:")):
            problems.append("route.url must be an http(s) or mailto address printed on the site")
    problems += _text(page, "ask", 1, 40) + _text(page, "blurb", 12, 60)
    problems += _text(page, "disclosure", 1, 40)
    blurb = page.get("blurb")
    if isinstance(blurb, str) and HYPE.search(blurb):
        problems.append("blurb contains an unsupported superlative; state a fact instead")
    facts = page.get("blurb_facts")
    if not isinstance(facts, list) or not facts:
        problems.append("blurb_facts must cite at least one project file")
    elif any(not isinstance(item, str) or "://" in item for item in facts):
        problems.append("blurb_facts must be project file paths, not web addresses")
    return problems


def check_ledger(ledger):
    """Return a list of problems. An empty list means the ledger may be written up."""
    pages = ledger.get("pages")
    if not isinstance(pages, list):
        return ["pages must be a list"]
    problems = []
    own = [str(d).lower().removeprefix("www.") for d in ledger.get("own_domains") or []]
    if not own:
        problems.append("own_domains must name the business's own site")
    limit = ledger.get("max_targets")
    if type(limit) is not int or not 3 <= limit <= 12:
        problems.append("max_targets must be an integer from 3 to 12")
    if ledger.get("opened") != len(pages) or len(pages) > MAX_PAGES:
        problems.append(f"opened must equal the number of ledger pages, at most {MAX_PAGES}")
    urls, blurbs, hosts, pursued = set(), set(), {}, 0
    for number, page in enumerate(pages, 1):
        problems += [f"page {number}: {item}" for item in _check_page(page, own)]
        if not isinstance(page, dict):
            continue
        url = str(page.get("url", "")).rstrip("/")
        if url in urls:
            problems.append(f"page {number}: duplicate url")
        urls.add(url)
        if page.get("status") == "pursue":
            pursued += 1
            key = " ".join(str(page.get("blurb", "")).lower().split())
            if key in blurbs:
                problems.append(f"page {number}: blurb duplicates another page's blurb")
            blurbs.add(key)
            name = host(page.get("url")) or ""
            hosts[name] = hosts.get(name, 0) + 1
            if hosts[name] == 3:
                problems.append(f"at most 2 pursue pages may come from {name}")
    if type(limit) is int and pursued > limit:
        problems.append(f"{pursued} pursue pages exceed max_targets {limit}; hold the overflow")
    return problems


def counts(ledger):
    """Totals to state in the report."""
    pages = ledger["pages"]
    total = {status: sum(1 for p in pages if p["status"] == status) for status in STATUSES}
    return {"opened": len(pages), **total}


def check_report(ledger, text):
    """Return a list of problems with the written report; empty means it matches the ledger."""
    problems = []
    if not re.search(r"^Status: (complete|incomplete)\s*$", text, re.M):
        problems.append("missing a 'Status: complete' or 'Status: incomplete' line")
    problems += [f"missing section {heading!r}" for heading in HEADINGS if heading not in text]
    for page in ledger["pages"]:
        if page["url"] not in text:
            problems.append(f"page missing from the report: {page['url']}")
        elif page["status"] == "pursue" and page["blurb"] not in text:
            problems.append(f"blurb differs from the ledger for {page['url']}")
    return problems
```

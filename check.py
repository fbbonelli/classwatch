#!/usr/bin/env python3
"""ClassWatch — cloud checker.

Runs on GitHub Actions every 10 minutes. Needs no laptop and no login:
Bentley's course listing is public.

  - fetches the sections on watchlist.json
  - compares against state.json (committed in the repo, so it survives runs)
  - pushes to ntfy when a class flips full -> open
  - rewrites docs/index.html, which GitHub Pages serves as the live dashboard

Env:
  NTFY_TOPIC   (required for alerts)  ntfy topic to publish to
  NTFY_SERVER  (optional)             default https://ntfy.sh
  FORCE_CHECK  (optional)             "1" ignores active-hours gating
"""

import json, os, re, html, sys, subprocess
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dashboard  # noqa: E402

WATCHLIST = os.path.join(HERE, "watchlist.json")
STATE     = os.path.join(HERE, "state.json")
OUT       = os.path.join(HERE, "docs", "index.html")
# Machine-readable status the dashboard's "Check now" button fetches from
# raw.githubusercontent.com (which sends CORS headers, unlike Bentley).
STATUS    = os.path.join(HERE, "docs", "status.json")
# Written only when a class actually flips to open. The workflow watches for this
# to decide whether to publish immediately — it can't just diff state.json,
# because _health.last_ok makes that file differ on every single check.
SEAT_CHANGE_FLAG = os.path.join(HERE, "SEAT_CHANGE")

URL = "https://bentleyapps.azurewebsites.net/course-listing/index.php"
LISTING_URL = "https://bentleyapps.azurewebsites.net/course-listing/"
# Served with Access-Control-Allow-Origin: *, and NOT behind the Pages CDN cache,
# so the button always sees the newest committed check.
STATUS_URL = ("https://raw.githubusercontent.com/fbbonelli/classwatch/"
              "main/docs/status.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
EASTERN = ZoneInfo("America/New_York")
TERMS = {"202609": "Fall 2026", "202601": "Spring 2026", "202605": "Summer Full 2026"}

ACTIVE_HOURS = (7, 23)
REALERT_MINUTES = 60


HISTORY_DAYS = 7


def log(m):
    print(f"[{datetime.now(EASTERN):%Y-%m-%d %H:%M ET}] {m}", flush=True)


def append_history(entry):
    """Record one check in status.json's history, trimmed to HISTORY_DAYS.

    History lives inside status.json rather than its own file so the dashboard's
    "Check now" button refreshes the log and the seat counts in one fetch —
    otherwise tapping it would leave a visibly stale log.
    """
    doc = load(STATUS, {})
    hist = doc.get("history", [])
    hist.append(entry)
    cutoff = datetime.now(EASTERN) - timedelta(days=HISTORY_DAYS)
    kept = []
    for h in hist:
        try:
            if datetime.fromisoformat(h["t"]) >= cutoff:
                kept.append(h)
        except (ValueError, KeyError, TypeError):
            continue  # drop unparseable rows rather than letting them pile up
    doc["history"] = kept
    save(STATUS, doc)
    return kept


def load(p, d):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return json.loads(json.dumps(d))


def save(p, d):
    with open(p, "w") as f:
        json.dump(d, f, indent=2)
        f.write("\n")


# ------------------------------------------------------------------ scraping

def fetch(term, depts):
    args = ["curl", "-sS", "--fail", "--max-time", "60", "-A", UA,
            "--data-urlencode", "submit=Submit",
            "--data-urlencode", f"acad_period[]={term}"]
    for d in sorted(set(depts)):
        args += ["--data-urlencode", f"dept[]={d}"]
    args.append(URL)
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"fetch failed (curl {r.returncode}): {r.stderr.strip()[:200]}")
    return r.stdout


def _strip(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ")).strip()


def parse(page):
    out = []
    for m in re.finditer(r"<div class='course-grid'>(.*?)(?=<div class='course-grid'>|<h2|\Z)", page, re.S):
        block = re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S)
        t = re.search(r"<div class='course'>(.*?)</div>", block, re.S)
        if not t:
            continue
        title = _strip(t.group(1))
        body = _strip(re.sub(r"<div class='course'>.*?</div>", "", block, flags=re.S))
        st = re.search(r"Status:\s*(\w+)", body)
        se = re.search(r"Seats Available:\s*(-?\d+)", body)
        ins = re.search(r"Instructor:\s*(.*?)\s*Status:", body)
        mp = re.search(r"<div class='meeting-pattern'>(.*?)</div>", block, re.S)
        dm = re.search(r"Delivery Mode:\s*([^;]*?)\s*(?:Course Tags:|$)", body)
        out.append({
            "code": title.split(" - ")[0].strip(),
            "title": title,
            "name": title.split(" - ", 1)[1].strip() if " - " in title else title,
            "instructor": ins.group(1).strip() if ins else "",
            "status": st.group(1) if st else "?",
            "seats": int(se.group(1)) if se else None,
            "meeting": _strip(mp.group(1)) if mp else "",
            "mode": dm.group(1).strip() if dm else "",
        })
    return out


def dept_of(m):
    return m.strip().split()[0].upper()


def matches(want, code):
    want = re.sub(r"\s+", " ", want.strip().upper())
    code = re.sub(r"\s+", " ", code.strip().upper())
    return code == want if "-" in want else (code == want or code.startswith(want + "-"))


def is_open(r):
    return r["status"].lower() == "open" and (r["seats"] or 0) > 0


# ------------------------------------------------------------------ alerting

def ntfy(title, message, urgent=True):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        log("  ntfy: NTFY_TOPIC not set — no phone alert sent")
        return False
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    r = subprocess.run(
        ["curl", "-sS", "--fail", "--max-time", "25",
         "-H", f"Title: {title}",
         "-H", f"Priority: {'urgent' if urgent else 'default'}",
         "-H", "Tags: mortar_board",
         "--data-binary", message, f"{server}/{topic}"],
        capture_output=True, text=True)
    ok = r.returncode == 0
    log(f"  ntfy: {'sent' if ok else 'FAILED ' + r.stderr.strip()[:120]}")
    return ok


# ------------------------------------------------------------------ main

def main():
    # One-shot proof that the cloud can reach your phone: verifies NTFY_TOPIC is
    # set correctly in repo secrets and that GitHub's runners can publish to ntfy.
    if os.environ.get("SELFTEST") == "1":
        now = datetime.now(EASTERN)
        ok = ntfy("✅ ClassWatch cloud test",
                  "This alert came from GitHub's servers, not your laptop.\n\n"
                  "The 24/7 watcher can reach your phone. No class actually opened.\n\n"
                  f"Sent {now:%b %d, %-I:%M %p ET}", urgent=False)
        if not ok:
            log("SELFTEST FAILED — check the NTFY_TOPIC repository secret")
            return 1
        log("SELFTEST OK — the cloud reached your phone")
        return 0

    wl = load(WATCHLIST, {"term": "202609", "courses": []})
    state = load(STATE, {})
    now = datetime.now(EASTERN)
    force = os.environ.get("FORCE_CHECK") == "1"

    if not wl["courses"]:
        log("watchlist empty — nothing to do")
        return 0

    lo, hi = ACTIVE_HOURS
    if not force and not (lo <= now.hour < hi):
        log(f"outside active hours ({lo}:00–{hi}:00 ET) — skipping")
        return 0

    health = state.get("_health", {"fails": 0, "last_ok": None})
    try:
        rows = parse(fetch(wl["term"], [dept_of(c["match"]) for c in wl["courses"]]))
        if not rows:
            raise RuntimeError("parsed 0 sections — Bentley likely changed their page format")
        found = {c["match"]: [r for r in rows if matches(c["match"], r["code"])]
                 for c in wl["courses"]}
        if all(not v for v in found.values()):
            raise RuntimeError(f"none of the watched classes were found: "
                               f"{[c['match'] for c in wl['courses']]}")
    except Exception as e:
        health["fails"] = health.get("fails", 0) + 1
        log(f"CHECK FAILED ({health['fails']} in a row): {e}")
        if health["fails"] == 3:
            ntfy("⚠️ ClassWatch is broken",
                 f"3 checks in a row failed:\n{e}\n\n"
                 f"Last good check: {health.get('last_ok') or 'never'}\n\n"
                 f"Your classes are NOT being watched right now.")
        state["_health"] = health
        save(STATE, state)
        append_history({"t": now.isoformat(), "ok": False,
                        "error": str(e)[:160], "fails": health["fails"]})
        return 1

    recovered = health.get("fails", 0) >= 3
    if recovered:
        ntfy("✅ ClassWatch recovered", "ClassWatch is working again and watching your classes.")
    state["_health"] = {"fails": 0, "last_ok": now.isoformat()}

    fire = []
    for entry in wl["courses"]:
        for r in found.get(entry["match"], []):
            prev = state.get(r["code"], {})
            was, last = prev.get("open", False), prev.get("last_alert")
            if is_open(r):
                due = True
                if was and last:
                    try:
                        due = now - datetime.fromisoformat(last) >= timedelta(minutes=REALERT_MINUTES)
                    except ValueError:
                        due = True
                elif was:
                    due = False
                if due:
                    fire.append(r)
                    state[r["code"]] = {"open": True, "seats": r["seats"],
                                        "last_alert": now.isoformat()}
                else:
                    state[r["code"]] = {"open": True, "seats": r["seats"], "last_alert": last}
            else:
                state[r["code"]] = {"open": False, "seats": r["seats"], "last_alert": None}

    if fire:
        lines = [f"{r['code']} — {r['name']}\n  {r['seats']} seat(s) | {r['instructor']}\n"
                 f"  {r['meeting']}" for r in fire]
        log("*** OPEN: " + ", ".join(r["code"] for r in fire))
        ntfy(f"🎓 SEAT OPEN — {', '.join(r['code'] for r in fire)}",
             "Register NOW — first come, first served.\n\n" + "\n\n".join(lines)
             + "\n\n" + dashboard.WORKDAY_URL)
        with open(SEAT_CHANGE_FLAG, "w") as f:
            f.write(", ".join(r["code"] for r in fire))
    else:
        log(f"checked {sum(len(v) for v in found.values())} section(s) — none newly open")

    save(STATE, state)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # Report the interval the workflow is actually using, so "next check" on the
    # dashboard doesn't quietly lie when the schedule changes.
    try:
        poll_min = max(1, round(int(os.environ.get("CHECK_INTERVAL_SECONDS", "600")) / 60))
    except ValueError:
        poll_min = 10
    sections = []
    for entry in wl["courses"]:
        for r in sorted(found.get(entry["match"], []), key=lambda x: x["code"]):
            sections.append({**{k: r[k] for k in
                                ("code", "name", "instructor", "meeting", "mode",
                                 "status", "seats")},
                             "open": is_open(r)})
        if not found.get(entry["match"]):
            sections.append({"code": entry["match"], "name": "", "instructor": "",
                             "meeting": "", "mode": "", "status": "not_found",
                             "seats": None, "open": False})
    open_now = [{"code": s["code"], "seats": s["seats"]} for s in sections if s["open"]]
    history = append_history({
        "t": now.isoformat(),
        "ok": True,
        "open": open_now,
        "opened": [r["code"] for r in fire],   # newly opened -> the alert event
        "recovered": recovered,
        "n": len(sections),
    })
    doc = load(STATUS, {})
    doc.update({"checked_at": now.isoformat(),
                "checked_at_display": now.strftime("%-I:%M %p ET"),
                "term": TERMS.get(wl["term"], wl["term"]),
                "poll_minutes": poll_min,
                "sections": sections,
                "history": history})
    save(STATUS, doc)

    # Rendered last so the Log tab reflects this check, not the previous one.
    with open(OUT, "w") as f:
        f.write(dashboard.render_page(
            wl=wl, found=found, checked_at=now,
            term_label=TERMS.get(wl["term"], wl["term"]),
            poll_minutes=poll_min, listing_url=LISTING_URL, live=True,
            status_url=STATUS_URL, history=history))
    log(f"dashboard + status.json written ({len(sections)} sections, "
        f"{len(history)} log entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

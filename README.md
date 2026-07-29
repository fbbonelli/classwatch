# ClassWatch (cloud)

Checks Bentley classes for open seats every 10 minutes and pushes to your phone
the moment one frees up. Runs entirely on GitHub Actions — no laptop involved.

- **Live dashboard:** `https://<your-username>.github.io/<repo>/`
- **Phone alerts:** ntfy, delivered wherever you are
- **Source:** Bentley's public course listing (no login required)

Only the classes in `watchlist.json` are ever checked or displayed.

## Adding a class

Edit `watchlist.json` — on github.com, or locally then push:

```json
{
  "term": "202609",
  "courses": [
    { "match": "CS 305-9", "note": "" },
    { "match": "FI 305",   "note": "any section" }
  ]
}
```

`"CS 305-9"` watches that one section. `"CS 305"` watches every section of it.
Term codes: `202609` Fall 2026, `202601` Spring 2026.

The next scheduled run picks up the change. To check immediately, go to the
**Actions** tab → **ClassWatch** → **Run workflow**.

## How a check works

1. One request to Bentley's listing, filtered to the departments you're watching.
2. Pull `Status:` and `Seats Available:` for each of your sections.
3. Compare against `state.json`, committed in this repo so it survives between
   runs. A class is only "newly open" if it was at 0 seats before and isn't now.
4. On a flip to open, push to ntfy and rewrite `docs/index.html`.

Comparing against the previous run is what makes this usable — you're told when
something *changes*, not nagged every 10 minutes about a class you know about.

## If it breaks

`check.py` treats "fetched the page but found zero sections" as a failure rather
than as "all full" — otherwise a change to Bentley's HTML would leave it silently
reporting good news forever. After 3 consecutive failures it pushes a "ClassWatch
is broken" alert, and tells you again when it recovers.

## Files

| File | Purpose |
|---|---|
| `check.py` | Fetch, compare, alert, render |
| `dashboard.py` | Dashboard renderer (shared with the Mac version) |
| `watchlist.json` | The classes being watched |
| `state.json` | Last-seen status — basis for change detection |
| `docs/index.html` | The dashboard GitHub Pages serves |
| `.github/workflows/check.yml` | The 10-minute schedule |

## Known limits

- GitHub runs scheduled jobs on a best-effort basis and can delay them under
  load, so a "10 minute" check is sometimes 15–20. The copy running on the Mac
  is the fast path; this one is the always-on safety net.
- This repo is public, so the dashboard and your watched course codes are
  publicly readable. The ntfy topic is **not** in the code — it lives in
  repository secrets.

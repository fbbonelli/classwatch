"""Renders the ClassWatch dashboard.

render_inner() -> the <style> + markup (used for both the local file and the
published artifact, so the two always look identical).
render_page()  -> a full standalone HTML document for the local dashboard.
"""

import html
from datetime import datetime, timedelta

CSS = """
:root{
  --paper:#F4F6F9; --surface:#FFFFFF; --sunken:#EAEEF4;
  --line:#D7DDE6; --ink:#0B1622; --muted:#5B6879;
  --gold:#9C7C2E;
  --open:#12704A; --open-field:#E3F5EC; --open-edge:#8FD3B4;
  --full:#8E3149; --full-field:#F6EBEE; --full-edge:#DFBCC5;
  --stale:#8A6D1F; --stale-field:#FBF3DE;
}
@media (prefers-color-scheme:dark){
  :root{
    --paper:#0A1017; --surface:#141C26; --sunken:#0F1721;
    --line:#243040; --ink:#E7EDF5; --muted:#8595A8;
    --gold:#C9A659;
    --open:#3FCB8F; --open-field:#0E2A20; --open-edge:#1F6B4C;
    --full:#E8879C; --full-field:#2A151B; --full-edge:#6B2E3F;
    --stale:#E0BE6A; --stale-field:#2A2312;
  }
}
:root[data-theme="light"]{
  --paper:#F4F6F9; --surface:#FFFFFF; --sunken:#EAEEF4;
  --line:#D7DDE6; --ink:#0B1622; --muted:#5B6879; --gold:#9C7C2E;
  --open:#12704A; --open-field:#E3F5EC; --open-edge:#8FD3B4;
  --full:#8E3149; --full-field:#F6EBEE; --full-edge:#DFBCC5;
  --stale:#8A6D1F; --stale-field:#FBF3DE;
}
:root[data-theme="dark"]{
  --paper:#0A1017; --surface:#141C26; --sunken:#0F1721;
  --line:#243040; --ink:#E7EDF5; --muted:#8595A8; --gold:#C9A659;
  --open:#3FCB8F; --open-field:#0E2A20; --open-edge:#1F6B4C;
  --full:#E8879C; --full-field:#2A151B; --full-edge:#6B2E3F;
  --stale:#E0BE6A; --stale-field:#2A2312;
}

*{box-sizing:border-box;}
.cw{
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
  background:var(--paper); color:var(--ink);
  font-family:var(--sans);
  min-height:100vh; margin:0;
  padding:clamp(20px,4vw,48px) clamp(16px,4vw,40px) 64px;
  -webkit-font-smoothing:antialiased;
}
.cw-wrap{max-width:820px;margin:0 auto;display:flex;flex-direction:column;gap:26px;}

/* masthead */
.cw-top{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px 16px;
  padding-bottom:16px;border-bottom:1px solid var(--line);}
.cw-mark{font-family:var(--mono);font-size:15px;font-weight:700;
  letter-spacing:.22em;text-transform:uppercase;color:var(--gold);margin:0;}
.cw-term{font-family:var(--mono);font-size:13px;color:var(--muted);letter-spacing:.04em;}
.cw-stamp{margin-left:auto;font-family:var(--mono);font-size:12px;
  color:var(--muted);font-variant-numeric:tabular-nums;text-align:right;}

/* verdict */
.cw-verdict{border:1px solid;border-radius:5px;padding:20px 22px;
  display:flex;flex-direction:column;gap:6px;}
.cw-verdict.is-open{background:var(--open-field);border-color:var(--open-edge);}
.cw-verdict.is-quiet{background:var(--sunken);border-color:var(--line);}
.cw-verdict h2{margin:0;font-size:clamp(20px,3.6vw,27px);line-height:1.15;
  letter-spacing:-.02em;text-wrap:balance;}
.cw-verdict.is-open h2{color:var(--open);}
.cw-verdict p{margin:0;font-size:14px;color:var(--muted);line-height:1.5;}
.cw-verdict.is-open p{color:var(--open);opacity:.9;}
.cw-cta{align-self:flex-start;margin-top:8px;display:inline-block;
  background:var(--open);color:#fff;text-decoration:none;
  font-size:13px;font-weight:650;letter-spacing:.02em;
  padding:9px 16px;border-radius:4px;}
.cw-cta:hover{filter:brightness(1.08);}
.cw-cta:focus-visible{outline:2px solid var(--ink);outline-offset:2px;}

/* section label */
.cw-lab{font-family:var(--mono);font-size:11px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--muted);margin:0 0 -8px;}

/* cards */
.cw-list{display:flex;flex-direction:column;gap:12px;list-style:none;margin:0;padding:0;}
.cw-card{background:var(--surface);border:1px solid var(--line);border-radius:5px;
  padding:18px 20px;display:grid;grid-template-columns:1fr auto;gap:4px 20px;align-items:start;}
.cw-card.open{background:var(--open-field);border-color:var(--open-edge);}
.cw-code{grid-column:1;font-family:var(--mono);font-size:19px;font-weight:700;
  letter-spacing:-.01em;margin:0;}
.cw-name{grid-column:1;margin:0;font-size:15px;color:var(--ink);line-height:1.35;}
.cw-meta{grid-column:1;margin:6px 0 0;font-family:var(--mono);font-size:12.5px;
  color:var(--muted);line-height:1.7;}
.cw-note{grid-column:1;margin:8px 0 0;font-size:12.5px;color:var(--muted);
  font-style:italic;line-height:1.45;}
.cw-right{grid-column:2;grid-row:1 / span 2;display:flex;flex-direction:column;
  align-items:flex-end;gap:8px;}
.cw-chip{font-family:var(--mono);font-size:11px;font-weight:700;letter-spacing:.13em;
  text-transform:uppercase;padding:5px 10px;border-radius:3px;white-space:nowrap;
  border:1px solid;}
.cw-chip.open{background:var(--open);color:#fff;border-color:var(--open);}
.cw-chip.full{background:var(--full-field);color:var(--full);border-color:var(--full-edge);}
.cw-chip.gone{background:var(--stale-field);color:var(--stale);border-color:var(--stale);}
.cw-seats{font-family:var(--mono);font-variant-numeric:tabular-nums;text-align:right;
  line-height:1;}
.cw-seats b{display:block;font-size:30px;font-weight:700;letter-spacing:-.03em;}
.cw-seats span{display:block;margin-top:3px;font-size:10px;letter-spacing:.13em;
  text-transform:uppercase;color:var(--muted);}
.cw-card.open .cw-seats b{color:var(--open);}
.cw-card.full .cw-seats b{color:var(--muted);}

.cw-empty{background:var(--sunken);border:1px dashed var(--line);border-radius:5px;
  padding:26px;text-align:center;color:var(--muted);font-size:14px;}

/* footer */
.cw-foot{border-top:1px solid var(--line);padding-top:18px;
  font-size:12.5px;color:var(--muted);line-height:1.65;
  display:flex;flex-direction:column;gap:8px;}
.cw-foot a{color:var(--gold);}
.cw-foot code{font-family:var(--mono);font-size:11.5px;background:var(--sunken);
  padding:1px 5px;border-radius:3px;border:1px solid var(--line);}
.cw-snap{background:var(--stale-field);border:1px solid var(--stale);color:var(--stale);
  border-radius:4px;padding:11px 14px;font-size:12.5px;line-height:1.5;}

@media (max-width:520px){
  .cw-card{grid-template-columns:1fr;}
  .cw-right{grid-column:1;grid-row:auto;flex-direction:row;align-items:center;
    justify-content:space-between;width:100%;margin-top:12px;}
  .cw-seats{text-align:left;}
  .cw-stamp{margin-left:0;text-align:left;width:100%;}
}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;}}
"""

E = lambda s: html.escape(str(s or ""), quote=True)


def _card(entry, row):
    """One watched section. `row` is None when the code matched nothing."""
    if row is None:
        return (
            f'<li class="cw-card full">'
            f'<p class="cw-code">{E(entry["match"])}</p>'
            f'<p class="cw-name">Not found in this term\'s listing</p>'
            f'<p class="cw-meta">Check the course code, or the class may not be offered.</p>'
            f'<div class="cw-right"><span class="cw-chip gone">No match</span></div>'
            f'</li>'
        )
    is_open = row["status"].lower() == "open" and (row["seats"] or 0) > 0
    cls = "open" if is_open else "full"
    chip = "Open" if is_open else "Full"
    bits = []
    if row.get("instructor"):
        bits.append(E(row["instructor"]))
    if row.get("meeting"):
        bits.append(E(row["meeting"]))
    if row.get("mode"):
        bits.append(E(row["mode"]))
    note = (f'<p class="cw-note">{E(entry.get("note"))}</p>'
            if entry.get("note") else "")
    return (
        f'<li class="cw-card {cls}">'
        f'<p class="cw-code">{E(row["code"])}</p>'
        f'<p class="cw-name">{E(row["name"])}</p>'
        f'<p class="cw-meta">{"<br>".join(bits)}</p>'
        f'{note}'
        f'<div class="cw-right">'
        f'<span class="cw-chip {cls}">{chip}</span>'
        f'<p class="cw-seats"><b>{row["seats"] if row["seats"] is not None else "?"}</b>'
        f'<span>seat{"" if row["seats"] == 1 else "s"}</span></p>'
        f'</div></li>'
    )


def render_inner(wl, found, checked_at, term_label, poll_minutes=10,
                 snapshot_note=False, listing_url="", live=True):
    """`found` maps watchlist match -> list of section dicts."""
    cards, open_rows = [], []
    for entry in wl["courses"]:
        rows = found.get(entry["match"]) or []
        if not rows:
            cards.append(_card(entry, None))
            continue
        for r in sorted(rows, key=lambda x: x["code"]):
            cards.append(_card(entry, r))
            if r["status"].lower() == "open" and (r["seats"] or 0) > 0:
                open_rows.append(r)

    n = len(wl["courses"])
    if open_rows:
        codes = ", ".join(r["code"] for r in open_rows)
        total = sum(r["seats"] or 0 for r in open_rows)
        verdict = (
            f'<section class="cw-verdict is-open">'
            f'<h2>{E(codes)} {"has" if len(open_rows) == 1 else "have"} '
            f'{total} open seat{"" if total == 1 else "s"}</h2>'
            f'<p>Register now — seats are first come, first served.</p>'
            f'<a class="cw-cta" href="https://www.bentley.edu/mybentley">Open Workday</a>'
            f'</section>'
        )
    elif n == 0:
        verdict = ('<section class="cw-verdict is-quiet"><h2>Nothing on the watchlist yet</h2>'
                   '<p>Tell Claude which class to watch and it will show up here.</p></section>')
    else:
        verdict = (
            f'<section class="cw-verdict is-quiet">'
            f'<h2>Still full</h2>'
            f'<p>{"Your class is" if n == 1 else f"All {n} watched classes are"} at zero seats. '
            f'You\'ll get a text the moment that changes.</p></section>'
        )

    body = ('<ul class="cw-list">' + "".join(cards) + "</ul>") if cards else \
           '<p class="cw-empty">No classes are being watched right now.</p>'

    if live:
        nxt = (checked_at + timedelta(minutes=poll_minutes)).strftime("%-I:%M %p")
        stamp = (f'Checked {checked_at.strftime("%-I:%M %p")} ET'
                 f'<br>Next check ~{nxt} ET')
        foot_live = (f'<p>Checks every {poll_minutes} minutes, 7am–11pm ET, '
                     f'and texts you the instant a seat opens. '
                     f'This page rewrites itself after every check.</p>')
        snap = ""
    else:
        stamp = f'Snapshot {checked_at.strftime("%b %-d, %-I:%M %p")} ET'
        foot_live = ('<p>The live checker runs on your Mac every 10 minutes and texts you '
                     'the instant a seat opens. That text is the source of truth.</p>')
        snap = ('<p class="cw-snap"><b>This page is a snapshot, not live.</b> '
                'It shows what Bentley reported at the time above and will not update on its own. '
                'Trust the text message, and ask Claude to refresh this page any time.</p>')

    src = (f'<p>Source: <a href="{E(listing_url)}">Bentley’s public course listing</a> '
           f'— real-time seat counts, no login required.</p>') if listing_url else ""

    return (
        f"<style>{CSS}</style>"
        f'<div class="cw"><div class="cw-wrap">'
        f'<header class="cw-top">'
        f'<h1 class="cw-mark">ClassWatch</h1>'
        f'<span class="cw-term">{E(term_label)}</span>'
        f'<span class="cw-stamp">{stamp}</span>'
        f'</header>'
        f'{snap}'
        f'{verdict}'
        f'<p class="cw-lab">Watching {n} class{"" if n == 1 else "es"}</p>'
        f'{body}'
        f'<footer class="cw-foot">{foot_live}{src}</footer>'
        f'</div></div>'
    )


def render_page(**kw):
    """Full standalone document for the local dashboard file."""
    refresh = '<meta http-equiv="refresh" content="60">' if kw.get("live", True) else ""
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"{refresh}<title>ClassWatch</title></head>"
        f"<body style=\"margin:0\">{render_inner(**kw)}</body></html>"
    )

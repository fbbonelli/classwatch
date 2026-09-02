"""Renders the ClassWatch dashboard.

render_inner() -> the <style> + markup (used for both the local file and the
published artifact, so the two always look identical).
render_page()  -> a full standalone HTML document for the local dashboard.
"""

import html, json
from datetime import datetime, timedelta

# Where you actually register. bentley.edu/mybentley is only the portal landing
# page — it costs an extra hop and a hunt for the Workday tile at the exact
# moment speed is the whole point. Defined once and reused by the server-side
# verdict, the client-side verdict and check.py's push alert.
WORKDAY_URL = "https://wd503.myworkday.com/bentley/login.htmld"

# A check is "stale" past this many minutes. The watcher runs every 10, so this
# is ~4 missed cycles — long enough not to trip on GitHub scheduling jitter.
STALE_AFTER_MINUTES = 45
# Checks now run round the clock, so staleness is alarming at any hour. Kept as a
# window (rather than deleted) so re-introducing quiet hours stays a one-line change.
ACTIVE_HOURS = (0, 24)

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

/* theme toggle — the [data-theme] overrides above existed but nothing ever set them */
.cw-theme{font:inherit;font-family:var(--mono);font-size:11px;letter-spacing:.12em;
  text-transform:uppercase;cursor:pointer;padding:6px 10px;border-radius:3px;
  background:none;color:var(--muted);border:1px solid var(--line);line-height:1;}
.cw-theme:hover{color:var(--ink);border-color:var(--muted);}
.cw-theme:focus-visible{outline:2px solid var(--gold);outline-offset:2px;}

/* stale-watcher warning — a dead runner used to look identical to a healthy one */
.cw-stale{background:var(--stale-field);border:1px solid var(--stale);color:var(--stale);
  border-radius:5px;padding:14px 16px;font-size:13.5px;line-height:1.5;
  display:flex;flex-direction:column;gap:4px;}
.cw-stale b{font-family:var(--mono);font-size:12px;letter-spacing:.12em;
  text-transform:uppercase;}
.cw-stale[hidden]{display:none;}

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
  letter-spacing:-.01em;margin:0;display:flex;flex-wrap:wrap;align-items:center;gap:9px;}

/* delivery mode. Deliberately outside the green/crimson status axis and off the
   gold brand mark — it's an attribute of the class, not a state to react to.
   Fill vs outline carries the scan; the word carries the meaning. */
.cw-mode{font-family:var(--mono);font-size:10px;font-weight:700;letter-spacing:.13em;
  text-transform:uppercase;padding:4px 8px;border-radius:3px;white-space:nowrap;
  border:1px solid var(--line);color:var(--muted);background:none;}
.cw-mode.online{background:var(--sunken);color:var(--ink);border-color:var(--muted);}
.cw-mode.hybrid{border-style:dashed;color:var(--ink);}
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

/* check-now control */
.cw-bar{display:flex;flex-wrap:wrap;align-items:center;gap:12px;}
.cw-btn{font:inherit;font-size:13.5px;font-weight:600;letter-spacing:.01em;
  padding:10px 18px;border-radius:4px;cursor:pointer;
  background:var(--ink);color:var(--paper);border:1px solid var(--ink);
  display:inline-flex;align-items:center;gap:8px;}
.cw-btn:hover:not(:disabled){opacity:.86;}
.cw-btn:disabled{opacity:.55;cursor:progress;}
.cw-btn:focus-visible{outline:2px solid var(--gold);outline-offset:2px;}
.cw-dot{width:8px;height:8px;border-radius:50%;background:currentColor;flex:none;}
.cw-btn.busy .cw-dot{animation:cwpulse 1s ease-in-out infinite;}
@keyframes cwpulse{0%,100%{opacity:1}50%{opacity:.25}}
.cw-age{font-family:var(--mono);font-size:12px;color:var(--muted);
  font-variant-numeric:tabular-nums;}
.cw-age.err{color:var(--full);}
.cw-age.ok{color:var(--open);}

/* tabs */
.cw-tabs{display:flex;gap:2px;border-bottom:1px solid var(--line);margin-bottom:-8px;}
.cw-tab{font:inherit;font-family:var(--mono);font-size:12px;letter-spacing:.12em;
  text-transform:uppercase;padding:10px 16px;cursor:pointer;
  background:none;border:none;border-bottom:2px solid transparent;
  color:var(--muted);}
.cw-tab:hover{color:var(--ink);}
.cw-tab[aria-selected="true"]{color:var(--gold);border-bottom-color:var(--gold);}
.cw-tab:focus-visible{outline:2px solid var(--gold);outline-offset:-2px;}
.cw-panel[hidden]{display:none;}
.cw-panel{display:flex;flex-direction:column;gap:26px;}

/* log */
.cw-day{display:flex;flex-direction:column;gap:0;}
.cw-dayhead{font-family:var(--mono);font-size:11px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--muted);margin:0 0 8px;
  padding-bottom:6px;border-bottom:1px solid var(--line);}
.cw-row{display:flex;align-items:baseline;gap:14px;padding:5px 2px;
  font-family:var(--mono);font-size:12.5px;line-height:1.5;}
.cw-row time{color:var(--muted);flex:none;width:74px;
  font-variant-numeric:tabular-nums;text-align:right;}
.cw-row .cw-what{color:var(--muted);}
/* events break out of the quiet rhythm so they cannot be scrolled past */
.cw-ev{border-radius:5px;padding:12px 14px;margin:10px 0;
  display:flex;flex-direction:column;gap:3px;border:1px solid;}
.cw-ev time{font-family:var(--mono);font-size:11.5px;opacity:.8;}
.cw-ev b{font-family:var(--mono);font-size:12px;letter-spacing:.12em;
  text-transform:uppercase;}
.cw-ev span{font-size:13.5px;}
.cw-ev.open{background:var(--open-field);border-color:var(--open-edge);color:var(--open);}
.cw-ev.fail{background:var(--full-field);border-color:var(--full-edge);color:var(--full);}
.cw-ev.rec{background:var(--stale-field);border-color:var(--stale);color:var(--stale);}
.cw-logfoot{font-size:12.5px;color:var(--muted);line-height:1.6;}

/* events-only filter */
.cw-logbar{display:flex;flex-wrap:wrap;align-items:center;gap:12px;}
.cw-filter{font:inherit;font-family:var(--mono);font-size:11px;letter-spacing:.12em;
  text-transform:uppercase;cursor:pointer;padding:7px 12px;border-radius:3px;
  background:none;color:var(--muted);border:1px solid var(--line);line-height:1;}
.cw-filter:hover{color:var(--ink);border-color:var(--muted);}
.cw-filter[aria-pressed="true"]{background:var(--ink);color:var(--paper);border-color:var(--ink);}
.cw-filter:focus-visible{outline:2px solid var(--gold);outline-offset:2px;}
/* hide routine rows, then hide any day that has nothing left in it */
.cw-events-only .cw-row{display:none;}
.cw-events-only .cw-day:not(:has(.cw-ev)){display:none;}
.cw-nothing{color:var(--muted);font-size:13.5px;}

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


def mode_chip(mode):
    """Online / In-Person / Hybrid badge. Bentley writes these three exactly."""
    if not mode:
        return ""
    key = mode.strip().lower()
    cls = "online" if "online" in key else "hybrid" if "hybrid" in key else "person"
    return f'<span class="cw-mode {cls}">{E(mode.strip())}</span>'


def _card(entry, row):
    """One watched section. `row` is None when the code matched nothing."""
    if row is None:
        return (
            f'<li class="cw-card full" data-code="{E(entry["match"])}">'
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
    note = (f'<p class="cw-note">{E(entry.get("note"))}</p>'
            if entry.get("note") else "")
    return (
        f'<li class="cw-card {cls}" data-code="{E(row["code"])}">'
        f'<p class="cw-code">{E(row["code"])}{mode_chip(row.get("mode"))}</p>'
        f'<p class="cw-name">{E(row["name"])}</p>'
        f'<p class="cw-meta">{"<br>".join(bits)}</p>'
        f'{note}'
        f'<div class="cw-right">'
        f'<span class="cw-chip {cls}">{chip}</span>'
        f'<p class="cw-seats"><b>{row["seats"] if row["seats"] is not None else "?"}</b>'
        f'<span>seat{"" if row["seats"] == 1 else "s"}</span></p>'
        f'</div></li>'
    )


def render_log(history):
    """Reverse-chronological log, grouped by day.

    Routine checks stay visually quiet; openings, failures and recoveries are
    pulled out as blocks so they can't be lost in a wall of 'both full'.
    """
    if not history:
        return ('<p class="cw-empty">No checks logged yet. The first entries appear '
                'after the next check runs.</p>')

    rows, days = [], {}
    for h in history:
        try:
            t = datetime.fromisoformat(h["t"])
        except (ValueError, KeyError, TypeError):
            continue
        days.setdefault(t.strftime("%Y-%m-%d"), []).append((t, h))

    out = []
    for day in sorted(days, reverse=True):
        entries = sorted(days[day], key=lambda x: x[0], reverse=True)
        label = entries[0][0].strftime("%A, %B %-d")
        parts = [f'<p class="cw-dayhead">{E(label)}</p>']
        for t, h in entries:
            clock = t.strftime("%-I:%M %p")
            if not h.get("ok", True):
                parts.append(
                    f'<div class="cw-ev fail"><b>Check failed</b>'
                    f'<span>{E(h.get("error", "unknown error"))}</span>'
                    f'<time>{clock} ET</time></div>')
                continue
            if h.get("opened"):
                seats = {o["code"]: o.get("seats") for o in h.get("open", [])}
                detail = ", ".join(
                    f'{c} — {seats.get(c, "?")} seat'
                    f'{"" if seats.get(c) == 1 else "s"}' for c in h["opened"])
                parts.append(
                    f'<div class="cw-ev open"><b>Seat open</b>'
                    f'<span>{E(detail)}</span><time>{clock} ET</time></div>')
                continue
            if h.get("recovered"):
                parts.append(
                    f'<div class="cw-ev rec"><b>Recovered</b>'
                    f'<span>Checks are working again</span>'
                    f'<time>{clock} ET</time></div>')
                continue
            openv = h.get("open") or []
            if openv:
                what = ", ".join(f'{o["code"]} open ({o.get("seats", "?")})' for o in openv)
            else:
                n = h.get("n", 0)
                what = "all full" if n != 1 else "full"
            parts.append(f'<div class="cw-row"><time>{clock}</time>'
                         f'<span class="cw-what">{E(what)}</span></div>')
        out.append('<section class="cw-day">' + "".join(parts) + "</section>")

    total = len(history)
    out.append(f'<p class="cw-logfoot">{total} check{"" if total == 1 else "s"} '
               f'logged, last 7 days. Older entries are dropped automatically.</p>')
    return "".join(out)


TABS_JS = """
(function(){
  var tabs=[].slice.call(document.querySelectorAll('.cw-tab'));
  if(!tabs.length) return;
  function show(name){
    tabs.forEach(function(t){
      var on = t.dataset.tab===name;
      t.setAttribute('aria-selected', on?'true':'false');
      t.tabIndex = on?0:-1;
      var p=document.getElementById('panel-'+t.dataset.tab);
      if(p) p.hidden = !on;
    });
    try{ history.replaceState(null,'', on_hash(name)); }catch(e){}
  }
  function on_hash(name){ return name==='status' ? location.pathname+location.search : '#log'; }
  tabs.forEach(function(t){
    t.addEventListener('click', function(){ show(t.dataset.tab); });
    t.addEventListener('keydown', function(e){
      var i=tabs.indexOf(t), j = e.key==='ArrowRight' ? i+1 : e.key==='ArrowLeft' ? i-1 : -1;
      if(j>=0 && j<tabs.length){ e.preventDefault(); tabs[j].focus(); show(tabs[j].dataset.tab); }
    });
  });
  if(location.hash==='#log') show('log');
})();
"""


CHECK_JS = """
(function(){
  var URL_=%(url)s, WORKDAY_=%(workday)s,
      STALE_=%(stale)d, ACTIVE_=%(active)s, POLL_MS_=%(poll_ms)d,
      pollMin=%(poll_min)d,
      btn=document.getElementById('cwCheck'),
      age=document.getElementById('cwAge'), stamp=document.getElementById('cwStamp');
  if(!btn) return;

  function minsAgo(iso){
    var d=(Date.now()-new Date(iso).getTime())/60000;
    if(d<1) return 'just now';
    if(d<2) return '1 min ago';
    return Math.round(d)+' min ago';
  }

  // Everything Bentley reports is Eastern. Pin every client-side render to it —
  // reading these in the browser's own zone silently relabelled each row (a
  // 9:30 PM ET check displayed as "10:30 PM ET" from UTC-03) and grouped the
  // evening's checks under the following day.
  var ET={timeZone:'America/New_York'};
  function etClock(d){ return d.toLocaleTimeString('en-US',
    {hour:'numeric',minute:'2-digit',timeZone:'America/New_York'}); }
  function etDayKey(d){ return d.toLocaleDateString('en-CA',ET); }   // YYYY-MM-DD
  function etDayLabel(d){ return d.toLocaleDateString('en-US',
    {weekday:'long',month:'long',day:'numeric',timeZone:'America/New_York'}); }
  function etHour(d){ return parseInt(d.toLocaleString('en-US',
    {hour:'2-digit',hour12:false,timeZone:'America/New_York'}),10); }

  // A stopped watcher used to be invisible: the page just kept showing an old
  // timestamp. Overnight the pause is deliberate, so only warn inside active hours.
  function setStale(iso){
    var box=document.getElementById('cwStale'); if(!box) return;
    var mins=(Date.now()-new Date(iso).getTime())/60000, h=etHour(new Date());
    var inHours = h>=ACTIVE_[0] && h<ACTIVE_[1];
    if(mins>STALE_ && inHours){
      box.hidden=false;
      box.innerHTML='<b>Watcher may be down</b><span>Last successful check was '+
        esc(minsAgo(iso))+'. Checks should run every '+
        pollMin+' minutes, so seat openings may be going unnoticed. '+
        'Check the <a href="https://github.com/fbbonelli/classwatch/actions">Actions run history</a>.</span>';
    } else { box.hidden=true; }
  }
  // The server-rendered HTML is only as fresh as the last Pages build, but
  // status.json is fresh every check. Without this the page could not show a
  // class it had never rendered — adding one to the watchlist left the stale
  // list sitting there until Pages rebuilt, which just looks like the edit
  // failed. So the page builds missing cards itself and drops unwatched ones.
  function modeChip(mode){
    if(!mode) return '';
    var k=String(mode).toLowerCase();
    var c = k.indexOf('online')>=0 ? 'online' : (k.indexOf('hybrid')>=0 ? 'hybrid' : 'person');
    return '<span class="cw-mode '+c+'">'+esc(mode)+'</span>';
  }
  function buildCard(s){
    var li=document.createElement('li');
    li.setAttribute('data-code', s.code);
    if(s.status==='not_found'){
      li.className='cw-card full';
      li.innerHTML='<p class="cw-code">'+esc(s.code)+'</p>'+
        '<p class="cw-name">Not found in this term\\'s listing</p>'+
        '<p class="cw-meta">Check the course code, or the class may not be offered.</p>'+
        '<div class="cw-right"><span class="cw-chip gone">No match</span></div>';
      return li;
    }
    var open=!!s.open, cls=open?'open':'full', meta=[];
    if(s.instructor) meta.push(esc(s.instructor));
    if(s.meeting) meta.push(esc(s.meeting));
    li.className='cw-card '+cls;
    li.innerHTML='<p class="cw-code">'+esc(s.code)+modeChip(s.mode)+'</p>'+
      '<p class="cw-name">'+esc(s.name)+'</p>'+
      '<p class="cw-meta">'+meta.join('<br>')+'</p>'+
      '<div class="cw-right"><span class="cw-chip '+cls+'">'+(open?'Open':'Full')+'</span>'+
      '<p class="cw-seats"><b>'+((s.seats===null||s.seats===undefined)?'?':s.seats)+'</b>'+
      '<span>seat'+(s.seats===1?'':'s')+'</span></p></div>';
    return li;
  }
  // Number of cards added, or -1 when there is no list element (an empty
  // watchlist renders a placeholder) so the caller can fall back to the hint.
  function syncCards(secs){
    var list=document.querySelector('.cw-list');
    if(!list) return -1;
    var want={}, added=0;
    secs.forEach(function(s){
      want[s.code]=1;
      if(!list.querySelector('.cw-card[data-code="'+CSS.escape(s.code)+'"]')){
        list.appendChild(buildCard(s)); added++;
      }
    });
    Array.prototype.slice.call(list.querySelectorAll('.cw-card')).forEach(function(c){
      if(!want[c.getAttribute('data-code')]) c.parentNode.removeChild(c);
    });
    // Re-append in feed order so the page matches the watchlist's ordering.
    secs.forEach(function(s){
      var c=list.querySelector('.cw-card[data-code="'+CSS.escape(s.code)+'"]');
      if(c) list.appendChild(c);
    });
    return added;
  }
  function setCard(s){
    var card=document.querySelector('.cw-card[data-code="'+CSS.escape(s.code)+'"]');
    if(!card) return false;
    var open=!!s.open, chip=card.querySelector('.cw-chip'),
        num=card.querySelector('.cw-seats b'), unit=card.querySelector('.cw-seats span');
    card.classList.toggle('open',open); card.classList.toggle('full',!open);
    if(chip){ chip.classList.toggle('open',open); chip.classList.toggle('full',!open);
              chip.textContent = s.status==='not_found' ? 'No match' : (open?'Open':'Full'); }
    if(num) num.textContent = (s.seats===null||s.seats===undefined)?'?':s.seats;
    if(unit) unit.textContent = s.seats===1?'seat':'seats';
    return true;
  }
  function setVerdict(secs){
    var v=document.getElementById('cwVerdict'); if(!v) return;
    var open=secs.filter(function(s){return s.open;});
    if(open.length){
      var total=open.reduce(function(a,s){return a+(s.seats||0);},0);
      v.className='cw-verdict is-open';
      v.innerHTML='<h2>'+open.map(function(s){return esc(s.code);}).join(', ')+
        (open.length===1?' has ':' have ')+total+' open seat'+(total===1?'':'s')+'</h2>'+
        '<p>Register now — seats are first come, first served.</p>'+
        '<a class="cw-cta" target="_blank" rel="noopener" href="'+WORKDAY_+'">Register in Workday</a>';
    } else {
      v.className='cw-verdict is-quiet';
      v.innerHTML='<h2>Still full</h2><p>'+(secs.length===1?'Your class is':'All '+secs.length+' watched classes are')+
        ' at zero seats. You\\'ll get a push the moment that changes.</p>';
    }
  }

  // Mirrors render_log() in dashboard.py — without this, tapping Check now
  // while the Log tab is open would appear to do nothing.
  function esc(s){ var d=document.createElement('div'); d.textContent=s==null?'':s; return d.innerHTML; }
  function redrawLog(hist){
    var panel=document.getElementById('cwLogBody'); if(!panel||!hist) return;
    if(!hist.length){ panel.innerHTML='<p class="cw-empty">No checks logged yet.</p>'; return; }
    var days={};
    hist.forEach(function(h){
      var d=new Date(h.t); if(isNaN(d)) return;
      var k=etDayKey(d);
      (days[k]=days[k]||[]).push([d,h]);
    });
    var html=Object.keys(days).sort().reverse().map(function(k){
      var rows=days[k].sort(function(a,b){return b[0]-a[0];});
      var head=etDayLabel(rows[0][0]);
      return '<section class="cw-day"><p class="cw-dayhead">'+esc(head)+'</p>'+
        rows.map(function(p){
          var d=p[0], h=p[1], c=etClock(d);
          if(h.ok===false) return '<div class="cw-ev fail"><b>Check failed</b><span>'+
            esc(h.error||'unknown error')+'</span><time>'+c+' ET</time></div>';
          if(h.opened && h.opened.length){
            var seats={}; (h.open||[]).forEach(function(o){seats[o.code]=o.seats;});
            var det=h.opened.map(function(x){
              var s=seats[x]; return x+' — '+(s==null?'?':s)+' seat'+(s===1?'':'s'); }).join(', ');
            return '<div class="cw-ev open"><b>Seat open</b><span>'+esc(det)+
              '</span><time>'+c+' ET</time></div>';
          }
          if(h.recovered) return '<div class="cw-ev rec"><b>Recovered</b>'+
            '<span>Checks are working again</span><time>'+c+' ET</time></div>';
          var op=h.open||[];
          var what = op.length ? op.map(function(o){return o.code+' open ('+o.seats+')';}).join(', ')
                               : (h.n===1?'full':'all full');
          return '<div class="cw-row"><time>'+c+'</time><span class="cw-what">'+
            esc(what)+'</span></div>';
        }).join('')+'</section>';
    }).join('');
    panel.innerHTML = html + '<p class="cw-logfoot">'+hist.length+' check'+
      (hist.length===1?'':'s')+' logged, last 7 days. Older entries are dropped automatically.</p>';
    // the events-only filter hides rows that were just replaced
    if(window.cwApplyFilter) window.cwApplyFilter();
  }

  // Shared by the button and the background poller.
  function apply(d, quiet){
    var secs=d.sections||[], missed=0;
    var added=syncCards(secs);
    secs.forEach(function(s){ if(!setCard(s)) missed++; });
    setVerdict(secs);
    redrawLog(d.history);
    setStale(d.checked_at);
    if(d.poll_minutes) pollMin=d.poll_minutes;
    if(stamp) stamp.innerHTML='Checked '+esc(d.checked_at_display)+
      '<br>Every '+esc(String(d.poll_minutes))+' min';
    age.className='cw-age'+(quiet?'':' ok');
    age.textContent = missed
      ? 'Watchlist changed — reload the page'
      : (added>0 ? 'Watchlist updated \\u00b7 data from '+minsAgo(d.checked_at)
                 : (quiet?'Data from ':'Updated \\u00b7 data from ')+minsAgo(d.checked_at));
  }

  function pull(){
    return fetch(URL_+'?t='+Date.now(), {cache:'no-store'})
      .then(function(r){ if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); });
  }

  btn.addEventListener('click', function(){
    btn.disabled=true; btn.classList.add('busy');
    btn.querySelector('.cw-label').textContent='Checking\\u2026';
    age.className='cw-age'; age.textContent='';
    pull()
      .then(function(d){ apply(d, false); })
      .catch(function(e){
        age.className='cw-age err';
        age.textContent='Could not reach GitHub ('+e.message+')';
      })
      .finally(function(){
        btn.disabled=false; btn.classList.remove('busy');
        btn.querySelector('.cw-label').textContent='Check now';
      });
  });

  // Keep an open tab honest. The old page never updated itself once loaded —
  // a full meta-refresh was ruled out because it throws you out of the Log tab
  // mid-read, so update in place instead. Skipped while the tab is hidden, and
  // fired immediately on return so a backgrounded phone isn't showing old seats.
  var timer=null;
  function tick(){
    if(document.hidden) return;
    pull().then(function(d){ apply(d, true); }).catch(function(){ /* keep the last good render */ });
  }
  function start(){ if(timer===null) timer=setInterval(tick, POLL_MS_); }
  function stop(){ if(timer!==null){ clearInterval(timer); timer=null; } }
  document.addEventListener('visibilitychange', function(){
    if(document.hidden){ stop(); } else { tick(); start(); }
  });
  start();
  // The served HTML can be minutes old (Pages CDN), so correct it right away.
  tick();
})();
"""


LOGFILTER_JS = """
(function(){
  var btn=document.getElementById('cwFilter'), body=document.getElementById('cwLogBody');
  if(!btn||!body) return;
  var on=false;
  window.cwApplyFilter=function(){
    body.classList.toggle('cw-events-only', on);
    btn.setAttribute('aria-pressed', on?'true':'false');
    btn.textContent = on ? 'Showing events' : 'Events only';
    var none=document.getElementById('cwNoEvents');
    if(none) none.hidden = !(on && !body.querySelector('.cw-ev'));
  };
  btn.addEventListener('click', function(){ on=!on; window.cwApplyFilter(); });
})();
"""


# Runs before the body paints so a dark-mode user doesn't get a white flash.
THEME_JS = """
(function(){
  try{ var s=localStorage.getItem('cw-theme');
       if(s) document.documentElement.setAttribute('data-theme', s); }catch(e){}
  function current(){
    return document.documentElement.getAttribute('data-theme') ||
      (matchMedia('(prefers-color-scheme:dark)').matches ? 'dark' : 'light');
  }
  function label(){
    var b=document.getElementById('cwTheme'); if(!b) return;
    var dark=current()==='dark';
    b.textContent = dark ? 'Light' : 'Dark';
    b.setAttribute('aria-label', 'Switch to '+(dark?'light':'dark')+' theme');
  }
  document.addEventListener('DOMContentLoaded', function(){
    var b=document.getElementById('cwTheme'); if(!b) return;
    label();
    b.addEventListener('click', function(){
      var next=current()==='dark'?'light':'dark';
      document.documentElement.setAttribute('data-theme', next);
      try{ localStorage.setItem('cw-theme', next); }catch(e){}
      label();
    });
  });
})();
"""


def render_inner(wl, found, checked_at, term_label, poll_minutes=10,
                 snapshot_note=False, listing_url="", live=True, status_url="",
                 history=None, publish_minutes=None):
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
        verdict_inner = (
            f'<h2>{E(codes)} {"has" if len(open_rows) == 1 else "have"} '
            f'{total} open seat{"" if total == 1 else "s"}</h2>'
            f'<p>Register now — seats are first come, first served.</p>'
            f'<a class="cw-cta" href="{WORKDAY_URL}" target="_blank" '
            f'rel="noopener">Register in Workday</a>'
        )
    elif n == 0:
        verdict_inner = ('<h2>Nothing on the watchlist yet</h2>'
                         '<p>Tell Claude which class to watch and it will show up here.</p>')
    else:
        verdict_inner = (
            f'<h2>Still full</h2>'
            f'<p>{"Your class is" if n == 1 else f"All {n} watched classes are"} at zero seats. '
            f'You\'ll get a push the moment that changes.</p>'
        )

    body = ('<ul class="cw-list">' + "".join(cards) + "</ul>") if cards else \
           '<p class="cw-empty">No classes are being watched right now.</p>'

    if live:
        nxt = (checked_at + timedelta(minutes=poll_minutes)).strftime("%-I:%M %p")
        stamp = (f'Checked {checked_at.strftime("%-I:%M %p")} ET'
                 f'<br>Next check ~{nxt} ET')
        # Don't claim the page updates as often as the checker runs — where the two
        # differ (the cloud publishes on a slower heartbeat than it checks, to stay
        # under the Pages build cap) saying so would be a quiet lie, and this footer
        # is what he'd reason from when the page looks behind.
        pub = publish_minutes or poll_minutes
        base = (f'<b>Checks every {poll_minutes} minutes, around the clock</b>, '
                f'and runs in the cloud \u2014 so it keeps checking with your '
                f'laptop closed. The moment a seat opens you get a push via ntfy '
                f'and it shows up here.')
        if pub > poll_minutes:
            # Spelling this out because the two numbers get confused: seeing "10"
            # anywhere on the page reads as "it is only checking every 10 minutes".
            base += (f' The page itself republishes on a slower {pub}-minute cycle '
                     f'to stay inside GitHub\u2019s publishing limit \u2014 that '
                     f'throttles the timestamp below, not the checking.')
        foot_live = (f'<p>{base} This page also re-reads itself every minute '
                     f'while open.</p>')
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

    if status_url:
        bar = ('<div class="cw-bar">'
               '<button type="button" class="cw-btn" id="cwCheck">'
               '<span class="cw-dot"></span><span class="cw-label">Check now</span></button>'
               '<span class="cw-age" id="cwAge" role="status" aria-live="polite"></span></div>')
        script = "<script>" + (CHECK_JS % {
            "url": json.dumps(status_url),
            "workday": json.dumps(WORKDAY_URL),
            "stale": STALE_AFTER_MINUTES,
            "active": json.dumps(list(ACTIVE_HOURS)),
            "poll_ms": 60000,
            "poll_min": poll_minutes,
        }) + "</script>"
    else:
        bar, script = "", ""

    show_tabs = history is not None
    if show_tabs:
        tabs = ('<div class="cw-tabs" role="tablist" aria-label="Dashboard views">'
                '<button class="cw-tab" role="tab" data-tab="status" '
                'id="tab-status" aria-controls="panel-status" aria-selected="true">Status</button>'
                '<button class="cw-tab" role="tab" data-tab="log" '
                'id="tab-log" aria-controls="panel-log" aria-selected="false" '
                'tabindex="-1">Log</button></div>')
        n_ev = sum(1 for h in history
                   if not h.get("ok", True) or h.get("opened") or h.get("recovered"))
        log_panel = (
            f'<div class="cw-panel" role="tabpanel" id="panel-log" '
            f'aria-labelledby="tab-log" hidden>'
            f'<div class="cw-logbar">'
            f'<button type="button" class="cw-filter" id="cwFilter" '
            f'aria-pressed="false">Events only</button>'
            f'<span class="cw-age">{n_ev} event{"" if n_ev == 1 else "s"} '
            f'in {len(history)} check{"" if len(history) == 1 else "s"}</span></div>'
            f'<p class="cw-nothing" id="cwNoEvents" hidden>No openings, failures or '
            f'recoveries in the last 7 days — every check found the classes full.</p>'
            f'<div id="cwLogBody">{render_log(history)}</div>'
            f'</div>')
        script += "<script>" + TABS_JS + "</script>"
        script += "<script>" + LOGFILTER_JS + "</script>"
    else:
        tabs, log_panel = "", ""

    status_panel = (
        f'<section class="cw-verdict {"is-open" if open_rows else "is-quiet"}" id="cwVerdict">'
        f'{verdict_inner}</section>'
        f'{"" if show_tabs else bar}'
        f'<p class="cw-lab">Watching {n} class{"" if n == 1 else "es"}</p>'
        f'{body}'
    )
    # With tabs, the button lives outside the panels — otherwise it vanishes on
    # the Log tab, which is exactly where you'd want to pull fresh entries.
    global_bar = bar if show_tabs else ""
    if show_tabs:
        status_panel = (f'<div class="cw-panel" role="tabpanel" id="panel-status" '
                        f'aria-labelledby="tab-status">{status_panel}</div>')

    # Rendered server-side too, so a page loaded from a stale CDN copy admits it
    # before any JavaScript runs.
    stale_min = (datetime.now(checked_at.tzinfo) - checked_at).total_seconds() / 60
    lo, hi = ACTIVE_HOURS
    stale_now = (live and stale_min > STALE_AFTER_MINUTES
                 and lo <= datetime.now(checked_at.tzinfo).hour < hi)
    stale_box = (
        f'<div class="cw-stale" id="cwStale"{"" if stale_now else " hidden"}>'
        f'<b>Watcher may be down</b>'
        f'<span>Last successful check was {round(stale_min)} min ago. Checks should run '
        f'every {poll_minutes} minutes, so seat openings may be going unnoticed. '
        f'Check the <a href="https://github.com/fbbonelli/classwatch/actions">Actions '
        f'run history</a>.</span></div>'
    ) if live else ""

    theme_btn = ('<button type="button" class="cw-theme" id="cwTheme" '
                 'aria-label="Switch theme">Dark</button>')

    return (
        f"<style>{CSS}</style>"
        f"<script>{THEME_JS}</script>"
        f'<div class="cw"><div class="cw-wrap">'
        f'<header class="cw-top">'
        f'<h1 class="cw-mark">ClassWatch</h1>'
        f'<span class="cw-term">{E(term_label)}</span>'
        f'<span class="cw-stamp" id="cwStamp">{stamp}</span>'
        f'{theme_btn}'
        f'</header>'
        f'{snap}'
        f'{stale_box}'
        f'{tabs}'
        f'{global_bar}'
        f'{status_panel}'
        f'{log_panel}'
        f'<footer class="cw-foot">{foot_live}{src}</footer>'
        f'</div></div>{script}'
    )


def render_page(**kw):
    """Full standalone document for the local dashboard file."""
    # Auto-refresh only when there's no Check now button. With tabs on the page a
    # 60-second reload would yank you out of the Log tab mid-read; where the
    # button exists it's the better update path.
    auto = kw.get("live", True) and not kw.get("status_url")
    refresh = '<meta http-equiv="refresh" content="60">' if auto else ""
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"{refresh}<title>ClassWatch</title></head>"
        f"<body style=\"margin:0\">{render_inner(**kw)}</body></html>"
    )

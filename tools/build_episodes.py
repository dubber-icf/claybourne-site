#!/usr/bin/env python3
"""Regenerate the episode list in episodes.html from the public podcast feed.

The series is complete, so this normally never needs running again. It exists so
the 96 rows are generated from the feed rather than typed, and can be rebuilt if
an audio URL ever changes.

    python3 tools/build_episodes.py            # fetch the live feed
    python3 tools/build_episodes.py feed.xml   # use a saved copy

It replaces everything between the EPISODES:START and EPISODES:END markers.
"""
import html
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

FEED = "https://feeds.acast.com/public/shows/claybourne"
NS = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}
PAGE = Path(__file__).resolve().parent.parent / "episodes.html"
START, END = "<!-- EPISODES:START -->", "<!-- EPISODES:END -->"
PER_WEEK = 4
EXPECTED = 96


def seconds(text):
    parts = [int(p) for p in text.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def clock(sec):
    return f"{sec // 60}:{sec % 60:02d}"


def load(source):
    if source:
        raw = Path(source).read_bytes()
    else:
        req = urllib.request.Request(FEED, headers={"User-Agent": "claybourne-site-build"})
        raw = urllib.request.urlopen(req, timeout=30).read()
    episodes = []
    for item in ET.fromstring(raw).find("channel").findall("item"):
        number = item.findtext("itunes:episode", namespaces=NS)
        if not number:  # the trailer has no episode number
            continue
        title = item.findtext("title")
        title = re.sub(r"^Episode \d+:\s*", "", title).strip()
        synopsis = re.sub(r"<hr>.*", "", item.findtext("description"), flags=re.S)
        synopsis = html.unescape(re.sub(r"<[^>]+>", "", synopsis)).strip()
        episodes.append(
            {
                "n": int(number),
                "title": title,
                "dur": seconds(item.findtext("itunes:duration", namespaces=NS)),
                "src": item.find("enclosure").get("url"),
                "synopsis": synopsis,
            }
        )
    episodes.sort(key=lambda e: e["n"])
    numbers = [e["n"] for e in episodes]
    if numbers != list(range(1, EXPECTED + 1)):
        sys.exit(f"feed does not hold episodes 1 to {EXPECTED} exactly: {numbers}")
    return episodes


def render(episodes):
    out = []
    for w in range(0, len(episodes), PER_WEEK):
        week = episodes[w : w + PER_WEEK]
        k = w // PER_WEEK + 1
        minutes = round(sum(e["dur"] for e in week) / 60)
        out.append(f'<section class="week" id="week-{k}" aria-labelledby="week-{k}-h">')
        out.append('  <header class="week-head">')
        out.append(f'    <h2 id="week-{k}-h">Week {k}</h2>')
        out.append(
            f'    <p class="week-meta">Episodes {week[0]["n"]} to {week[-1]["n"]} &middot; {minutes} min</p>'
        )
        out.append("  </header>")
        out.append(f'  <ol class="ep-list" start="{week[0]["n"]}">')
        for e in week:
            t = html.escape(e["title"], quote=True)
            out.append(
                f'    <li class="ep" id="episode-{e["n"]}" data-ep="{e["n"]}" '
                f'data-title="{t}" data-dur="{e["dur"]}">'
            )
            out.append(
                f'      <a class="ep-play" href="{html.escape(e["src"], quote=True)}" '
                f'aria-label="Play Episode {e["n"]}: {t}">'
            )
            out.append(f'        <span class="ep-num">{e["n"]}</span>')
            out.append(f'        <span class="ep-title">{html.escape(e["title"])}</span>')
            out.append(f'        <span class="ep-dur">{clock(e["dur"])}</span>')
            out.append("      </a>")
            out.append(
                f'      <details class="ep-syn"><summary>Synopsis</summary>'
                f'<p>{html.escape(e["synopsis"])}</p></details>'
            )
            out.append("    </li>")
        out.append("  </ol>")
        out.append("</section>")
    return "\n".join(out)


def main():
    episodes = load(sys.argv[1] if len(sys.argv) > 1 else None)
    page = PAGE.read_text(encoding="utf-8")
    if page.count(START) != 1 or page.count(END) != 1:
        sys.exit("episodes.html must contain each EPISODES marker exactly once")
    head, rest = page.split(START)
    _, tail = rest.split(END)
    PAGE.write_text(f"{head}{START}\n{render(episodes)}\n{END}{tail}", encoding="utf-8")
    total = sum(e["dur"] for e in episodes)
    print(f"wrote {len(episodes)} episodes, {total // 3600}h {total % 3600 // 60}m, to {PAGE.name}")


if __name__ == "__main__":
    main()

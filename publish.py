#!/usr/bin/env python3
"""Publish a daily morning briefing to the GitHub Pages podcast feed.

Usage:
  publish.py --date YYYY-MM-DD --script /path/to/script.txt [--voice en-IN-PrabhatNeural]
             [--no-push] [--force]
  publish.py --feed-only [--no-push]      # just rebuild feed.xml (and push)

Requires: edge-tts (in ./.venv), ffmpeg/ffprobe, git; for pushing, `gh auth login`
(or a git credential with push rights to the repo) on this machine.
"""
import argparse, asyncio, datetime as dt, email.utils, json, os, subprocess, sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent
EP_DIR = ROOT / "episodes"
GH_USER = os.environ.get("PODCAST_GH_USER", "nmsankar")
REPO = os.environ.get("PODCAST_REPO", "morning-briefing-podcast")
BASE_URL = os.environ.get("PODCAST_BASE_URL", f"https://{GH_USER}.github.io/{REPO}").rstrip("/")
TITLE = "Mani's Morning Briefing"
AUTHOR = "Mani Sankar"
DESC = ("A private daily morning news briefing for Mani Sankar: markets, AI and tech, "
        "startups and funding, India and world headlines.")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
DEFAULT_VOICE = "en-IN-PrabhatNeural"


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, text=True, capture_output=True, **kw)


PIPER_VOICE = Path(os.environ.get("PODCAST_PIPER_VOICE",
                   str(ROOT / "voices" / "en_US-lessac-medium.onnx")))


def _edge_tts(text, tmp, voice, rate):
    import edge_tts
    asyncio.run(edge_tts.Communicate(text, voice, rate=rate).save(str(tmp)))
    if not tmp.exists() or tmp.stat().st_size < 1000:
        raise RuntimeError("edge-tts produced no audio")


def _piper_tts(text, tmp_wav):
    """Offline fallback: local Piper neural TTS -> WAV."""
    if not PIPER_VOICE.exists():
        raise RuntimeError(f"Piper voice model missing: {PIPER_VOICE}")
    piper = Path(sys.executable).with_name("piper")
    cmd = [str(piper) if piper.exists() else "piper", "-m", str(PIPER_VOICE),
           "-f", str(tmp_wav), "--sentence-silence", "0.3"]
    subprocess.run(cmd, input=text, text=True, check=True, capture_output=True)
    if not tmp_wav.exists() or tmp_wav.stat().st_size < 1000:
        raise RuntimeError("piper produced no audio")


def tts(text, out_mp3, voice, rate):
    """Synthesize with edge-tts; on any failure fall back to offline Piper. Returns engine name."""
    tmp = out_mp3.with_suffix(".raw.mp3")
    engine = "edge-tts"
    try:
        _edge_tts(text, tmp, voice, rate)
    except Exception as e:
        print(f"edge-tts failed ({type(e).__name__}: {str(e)[:200]}); falling back to Piper",
              file=sys.stderr)
        tmp.unlink(missing_ok=True)
        tmp = out_mp3.with_suffix(".raw.wav")
        _piper_tts(text, tmp)
        engine = f"piper ({PIPER_VOICE.stem})"
    # Re-encode to a standard podcast-friendly MP3 (44.1 kHz mono 64 kbps CBR) with ID3 tags.
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp), "-ac", "1", "-ar", "44100",
         "-b:a", "64k", "-metadata", f"title={episode_title(out_mp3.stem)}",
         "-metadata", f"artist={AUTHOR}", "-metadata", f"album={TITLE}",
         "-id3v2_version", "3", str(out_mp3)])
    tmp.unlink()
    print(f"TTS engine: {engine}")
    return engine


def duration_secs(mp3):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(mp3)]).stdout
    return int(round(float(out.strip())))


def fmt_dur(s):
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def episode_title(date_str):
    d = dt.date.fromisoformat(date_str)
    return f"Morning Briefing – {d.day} {d.strftime('%b %Y')}"


def build_feed():
    eps = sorted(EP_DIR.glob("????-??-??.mp3"), reverse=True)
    items = []
    for mp3 in eps:
        date = mp3.stem
        d = dt.date.fromisoformat(date)
        pub = dt.datetime(d.year, d.month, d.day, 7, 0, tzinfo=IST)
        secs = duration_secs(mp3)
        url = f"{BASE_URL}/episodes/{mp3.name}"
        summary = f"Mani's morning news briefing for {d.strftime('%A, %d %B %Y')}."
        items.append(f"""    <item>
      <title>{escape(episode_title(date))}</title>
      <description>{escape(summary)}</description>
      <itunes:summary>{escape(summary)}</itunes:summary>
      <enclosure url="{escape(url)}" length="{mp3.stat().st_size}" type="audio/mpeg"/>
      <guid isPermaLink="false">mani-morning-briefing-{date}</guid>
      <pubDate>{email.utils.format_datetime(pub)}</pubDate>
      <itunes:duration>{fmt_dur(secs)}</itunes:duration>
      <itunes:episodeType>full</itunes:episodeType>
      <itunes:explicit>false</itunes:explicit>
    </item>""")
    now = email.utils.format_datetime(dt.datetime.now(IST))
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>{escape(TITLE)}</title>
    <link>{BASE_URL}/</link>
    <atom:link href="{BASE_URL}/feed.xml" rel="self" type="application/rss+xml"/>
    <description>{escape(DESC)}</description>
    <language>en-in</language>
    <lastBuildDate>{now}</lastBuildDate>
    <itunes:author>{escape(AUTHOR)}</itunes:author>
    <itunes:owner><itunes:name>{escape(AUTHOR)}</itunes:name></itunes:owner>
    <itunes:summary>{escape(DESC)}</itunes:summary>
    <itunes:image href="{BASE_URL}/cover.jpg"/>
    <image><url>{BASE_URL}/cover.jpg</url><title>{escape(TITLE)}</title><link>{BASE_URL}/</link></image>
    <itunes:category text="News"/>
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>episodic</itunes:type>

{chr(10).join(items)}
  </channel>
</rss>
"""
    (ROOT / "feed.xml").write_text(feed, encoding="utf-8")
    import xml.dom.minidom
    xml.dom.minidom.parseString(feed.encode())  # sanity: must parse
    return eps


def push(msg):
    if not (ROOT / ".git").exists():
        sys.exit("No git repo in %s; run initial setup (see README)." % ROOT)
    run(["git", "-C", str(ROOT), "add", "-A"])
    if subprocess.run(["git", "-C", str(ROOT), "diff", "--cached", "--quiet"]).returncode == 0:
        print("Nothing to commit."); return
    run(["git", "-C", str(ROOT), "commit", "-m", msg])
    r = subprocess.run(["git", "-C", str(ROOT), "push", "origin", "HEAD:main"], text=True,
                       capture_output=True)
    if r.returncode:
        sys.exit("git push failed (is `gh auth login` done / `gh auth setup-git` run?):\n" + r.stderr)
    print("Pushed. Feed:", f"{BASE_URL}/feed.xml")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--script")
    ap.add_argument("--voice", default=os.environ.get("PODCAST_VOICE", DEFAULT_VOICE))
    ap.add_argument("--rate", default="+0%")
    ap.add_argument("--force", action="store_true", help="regenerate MP3 even if it exists")
    ap.add_argument("--feed-only", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args()
    EP_DIR.mkdir(exist_ok=True)
    if not a.feed_only:
        if not (a.date and a.script):
            ap.error("--date and --script are required (or use --feed-only)")
        dt.date.fromisoformat(a.date)
        out = EP_DIR / f"{a.date}.mp3"
        if a.force or not out.exists():
            text = Path(a.script).read_text(encoding="utf-8").strip()
            tts(text, out, a.voice, a.rate)
        s = duration_secs(out)
        print(json.dumps({"date": a.date, "mp3": str(out), "bytes": out.stat().st_size,
                          "duration": fmt_dur(s)}))
    eps = build_feed()
    print(f"feed.xml rebuilt with {len(eps)} episode(s)")
    if not a.no_push:
        push(f"Episode {a.date}" if a.date else "Rebuild feed")


if __name__ == "__main__":
    main()

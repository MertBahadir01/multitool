"""Playlist and video metadata parsing via yt-dlp."""

import yt_dlp


def _quiet_opts():
    return {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "ignoreerrors": True,
    }


def fetch_info(url: str) -> dict:
    """
    Return a normalised info dict for a URL (video or playlist).

    Keys always present:
        is_playlist  bool
        title        str
        entries      list[dict]  — each entry has: index, id, url, title, duration, filesize_approx
    Raises RuntimeError on hard failure.
    """
    opts = _quiet_opts()
    opts["extract_flat"] = "in_playlist"

    with yt_dlp.YoutubeDL(opts) as ydl:
        raw = ydl.extract_info(url, download=False)

    if raw is None:
        raise RuntimeError("Could not fetch info. Check the URL and your connection.")

    is_playlist = raw.get("_type") == "playlist"

    if is_playlist:
        entries = []
        for i, e in enumerate(raw.get("entries") or [], start=1):
            if e is None:
                continue
            entries.append({
                "index": i,
                "id": e.get("id", ""),
                "url": e.get("url") or e.get("webpage_url") or f"https://www.youtube.com/watch?v={e.get('id','')}",
                "title": e.get("title") or f"Video {i}",
                "duration": e.get("duration") or 0,
                "filesize_approx": e.get("filesize_approx") or 0,
            })
        return {
            "is_playlist": True,
            "title": raw.get("title", "Playlist"),
            "playlist_id": raw.get("id", ""),
            "entries": entries,
        }
    else:
        return {
            "is_playlist": False,
            "title": raw.get("title", "Video"),
            "entries": [{
                "index": 1,
                "id": raw.get("id", ""),
                "url": raw.get("webpage_url", url),
                "title": raw.get("title", "Video"),
                "duration": raw.get("duration") or 0,
                "filesize_approx": raw.get("filesize_approx") or 0,
            }],
        }


def fetch_formats(url: str) -> list[dict]:
    """
    Return available video+audio combined formats for a single video URL.
    Each dict: { format_id, height, ext, filesize, label }
    """
    opts = _quiet_opts()
    with yt_dlp.YoutubeDL(opts) as ydl:
        raw = ydl.extract_info(url, download=False)

    if raw is None:
        return []

    seen_heights = set()
    formats = []
    for f in raw.get("formats") or []:
        h = f.get("height")
        if not h:
            continue
        vcodec = f.get("vcodec", "none")
        acodec = f.get("acodec", "none")
        if vcodec == "none" or acodec == "none":
            # prefer combined; if missing, accept video-only (merged later)
            if vcodec == "none":
                continue
        if h in seen_heights:
            continue
        seen_heights.add(h)
        size = f.get("filesize") or f.get("filesize_approx") or 0
        formats.append({
            "format_id": f.get("format_id", ""),
            "height": h,
            "ext": f.get("ext", "mp4"),
            "filesize": size,
            "label": f"{h}p",
        })

    formats.sort(key=lambda x: x["height"], reverse=True)
    return formats


def format_duration(seconds) -> str:
    """Convert integer seconds to H:MM:SS or M:SS."""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "?"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def human_size(size_bytes) -> str:
    """Convert bytes to human-readable string."""
    try:
        size_bytes = int(size_bytes)
    except (TypeError, ValueError):
        return "?"
    if size_bytes <= 0:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

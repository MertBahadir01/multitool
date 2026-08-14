"""Metadata extraction service for the Metadata Reader tool.

Reads file metadata using what's already in the app's dependency set
(Pillow, stdlib zipfile/xml for OOXML docs) plus a few *optional* extras
that degrade gracefully if not installed (mutagen, pypdf) or if ffprobe
isn't on PATH. This tool is stateless — nothing here touches the database.
"""

import os
import re
import json
import mimetypes
import shutil
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp", ".ico"}
OOXML_EXTS = {".docx", ".xlsx", ".pptx", ".dotx", ".xltx", ".potx"}
AUDIO_EXTS = {".mp3", ".flac", ".wav", ".m4a", ".ogg", ".wma", ".aac"}
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".3gp"}
PDF_EXTS = {".pdf"}


def _fmt_ts(ts):
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "-"


def _human_size(n):
    size = float(n)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def _safe_float(value):
    """Convert Pillow's IFDRational (and similar Fraction-like types) to a
    plain float. Never use an f-string format spec directly on these —
    IFDRational.__format__ doesn't support numeric specs like ':.2f' and
    raises 'unsupported format string passed to IFDRational.__format__'."""
    try:
        return float(value)
    except Exception:
        return None


def _dms_to_decimal(dms, ref):
    """Convert an EXIF GPS (degrees, minutes, seconds) tuple to decimal degrees."""
    try:
        deg = _safe_float(dms[0]) or 0.0
        minutes = _safe_float(dms[1]) or 0.0
        seconds = _safe_float(dms[2]) or 0.0
        decimal = deg + minutes / 60.0 + seconds / 3600.0
        if ref in ("S", "W"):
            decimal = -decimal
        return decimal
    except Exception:
        return None


def _maps_link(lat, lon):
    return f"https://www.google.com/maps?q={lat:.6f},{lon:.6f}"


_ISO6709_RE = re.compile(r"^([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)")


def _parse_iso6709(text):
    """Parse the ISO 6709 location strings some phones/cameras embed in
    video containers, e.g. '+40.7128-074.0060+015.000/'."""
    m = _ISO6709_RE.match(text.strip())
    if not m:
        return None
    try:
        return float(m.group(1)), float(m.group(2))
    except Exception:
        return None


def _clean_value(value, max_len=300):
    """Some EXIF tags (MakerNote, UserComment, PrintIM, unknown vendor
    tags...) hold raw binary data. Dumped as text it shows up as a wall of
    replacement-character boxes. Detect that and show a short summary
    instead; also truncate anything unusually long."""
    if isinstance(value, bytes):
        try:
            text = value.decode("utf-8")
        except Exception:
            text = None
        if text is None:
            return f"<binary data, {len(value)} bytes>"
        value = text

    text = str(value)
    if not text:
        return text

    printable = sum(1 for ch in text if ch.isprintable() or ch in "\n\t")
    if printable / len(text) < 0.85:
        return f"<binary/unreadable data, {len(text)} chars>"

    if len(text) > max_len:
        return text[:max_len] + f"... (+{len(text) - max_len} more chars)"
    return text


def basic_file_info(path):
    st = os.stat(path)
    mime, _ = mimetypes.guess_type(path)
    return {
        "File Name": os.path.basename(path),
        "Folder": os.path.dirname(path) or ".",
        "Extension": os.path.splitext(path)[1].lower() or "-",
        "MIME Type": mime or "unknown",
        "Size": f"{st.st_size:,} bytes ({_human_size(st.st_size)})",
        "Created": _fmt_ts(st.st_ctime),
        "Modified": _fmt_ts(st.st_mtime),
        "Accessed": _fmt_ts(st.st_atime),
    }


def image_metadata(path):
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS
    except ImportError:
        return {"note": "Pillow not installed — cannot read image metadata."}

    data = {}
    try:
        with Image.open(path) as img:
            data["Format"] = img.format or "-"
            data["Mode"] = img.mode
            data["Dimensions"] = f"{img.width} x {img.height} px"

            dpi = img.info.get("dpi")
            if dpi:
                dx, dy = _safe_float(dpi[0]), _safe_float(dpi[1])
                data["DPI"] = f"{dx:.0f} x {dy:.0f}" if dx is not None and dy is not None else str(dpi)

            exif = img.getexif()
            if exif:
                gps_info = {}
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id)
                    tag_name = tag if tag is not None else f"Unknown Tag ({tag_id})"
                    if tag_name == "GPSInfo":
                        try:
                            for gps_id, gps_val in value.items():
                                gps_info[GPSTAGS.get(gps_id, gps_id)] = gps_val
                        except Exception:
                            pass
                        continue
                    # _clean_value() handles bytes/text and flags binary or
                    # unreadable data (MakerNote, UserComment, unknown vendor
                    # tags) instead of dumping raw replacement characters.
                    data[str(tag_name)] = _clean_value(value)

                if gps_info:
                    # Decode a human-readable lat/long + map link BEFORE the
                    # raw values below get stringified for the detail view.
                    lat, lat_ref = gps_info.get("GPSLatitude"), gps_info.get("GPSLatitudeRef")
                    lon, lon_ref = gps_info.get("GPSLongitude"), gps_info.get("GPSLongitudeRef")
                    if lat and lon and lat_ref and lon_ref:
                        lat_dec = _dms_to_decimal(lat, lat_ref)
                        lon_dec = _dms_to_decimal(lon, lon_ref)
                        if lat_dec is not None and lon_dec is not None:
                            data["GPS Coordinates"] = f"{lat_dec:.6f}, {lon_dec:.6f}"
                            data["Location (Map Link)"] = _maps_link(lat_dec, lon_dec)

                    alt = gps_info.get("GPSAltitude")
                    if alt is not None:
                        alt_val = _safe_float(alt)
                        data["GPS Altitude"] = f"{alt_val:.1f} m" if alt_val is not None else str(alt)

                    gps_date = gps_info.get("GPSDateStamp")
                    gps_time = gps_info.get("GPSTimeStamp")
                    if gps_date:
                        data["GPS Date/Time (UTC)"] = f"{gps_date} {gps_time or ''}".strip()

                    for k, v in gps_info.items():
                        data[f"GPS {k} (raw)"] = _clean_value(v)
    except Exception as e:
        data["error"] = f"Could not read image metadata: {e}"
    return data


def _ffprobe_path():
    return shutil.which("ffprobe")


def av_metadata(path):
    """Uses ffprobe (bundled with the ffmpeg install the app already relies
    on for mp4_to_mp3 / screen_recorder / youtube_downloader)."""
    ffprobe = _ffprobe_path()
    if not ffprobe:
        return {"note": "ffprobe (part of ffmpeg) not found on PATH — install ffmpeg for duration/codec details."}
    try:
        result = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", path],
            capture_output=True, text=True, timeout=20,
        )
        info = json.loads(result.stdout or "{}")
    except Exception as e:
        return {"error": f"ffprobe failed: {e}"}

    data = {}
    fmt = info.get("format", {})
    dur = fmt.get("duration")
    if dur:
        try:
            secs = float(dur)
            data["Duration"] = f"{int(secs // 60)}m {secs % 60:.1f}s"
        except Exception:
            pass
    if fmt.get("bit_rate"):
        try:
            data["Bitrate"] = f"{int(fmt['bit_rate']) // 1000} kbps"
        except Exception:
            pass
    tags = fmt.get("tags", {}) or {}
    make = model = None
    for k, v in tags.items():
        data[f"Tag: {k.title()}"] = _clean_value(v)
        kl = k.lower()

        # Recording device — phones/cameras often store this as
        # com.apple.quicktime.make / .model, or plain 'make' / 'model'.
        if kl.endswith("make"):
            make = v
        elif kl.endswith("model"):
            model = v

        # Embedded GPS location, e.g. com.apple.quicktime.location.iso6709.
        if "location" in kl and isinstance(v, str):
            coords = _parse_iso6709(v)
            if coords:
                lat, lon = coords
                data["GPS Coordinates"] = f"{lat:.6f}, {lon:.6f}"
                data["Location (Map Link)"] = _maps_link(lat, lon)

    if make or model:
        data["Recording Device"] = " ".join(x for x in (make, model) if x)

    for i, stream in enumerate(info.get("streams", [])):
        prefix = f"Stream {i} ({stream.get('codec_type', '?')})"
        if stream.get("codec_name"):
            data[f"{prefix} Codec"] = stream["codec_name"]
        if stream.get("width") and stream.get("height"):
            data[f"{prefix} Resolution"] = f"{stream['width']}x{stream['height']}"
        if stream.get("avg_frame_rate") and stream["avg_frame_rate"] not in ("0/0", None):
            data[f"{prefix} Frame Rate"] = stream["avg_frame_rate"]
        if stream.get("sample_rate"):
            data[f"{prefix} Sample Rate"] = f"{stream['sample_rate']} Hz"
        if stream.get("channels"):
            data[f"{prefix} Channels"] = str(stream["channels"])

    if not data:
        data["note"] = "No stream/format metadata returned by ffprobe."
    return data


def audio_tags(path):
    """Optional: richer ID3/Vorbis/etc tags via mutagen, if installed."""
    try:
        import mutagen
    except ImportError:
        return {}
    try:
        f = mutagen.File(path, easy=True)
        if not f:
            return {}
        data = {}
        for key, values in f.items():
            data[f"Tag: {key.title()}"] = ", ".join(values) if isinstance(values, list) else str(values)
        return data
    except Exception:
        return {}


def ooxml_metadata(path):
    """docx/xlsx/pptx are ZIP archives with docProps/core.xml + app.xml —
    stdlib zipfile + xml is enough, no extra dependency needed."""
    data = {}
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            for part in ("docProps/core.xml", "docProps/app.xml"):
                if part in names:
                    root = ET.fromstring(z.read(part))
                    for child in root:
                        tag = child.tag.split("}")[-1]
                        if child.text and child.text.strip():
                            data[tag] = child.text.strip()
    except Exception as e:
        data["error"] = f"Could not read document properties: {e}"
    if not data:
        data["note"] = "No embedded document properties found."
    return data


def pdf_metadata(path):
    """Optional: pypdf / PyPDF2, if installed."""
    try:
        try:
            from pypdf import PdfReader
        except ImportError:
            from PyPDF2 import PdfReader
    except ImportError:
        return {"note": "Install 'pypdf' (pip install pypdf) for PDF metadata & page count."}

    data = {}
    try:
        reader = PdfReader(path)
        data["Pages"] = str(len(reader.pages))
        info = reader.metadata or {}
        for k, v in info.items():
            key = k.lstrip("/")
            if v:
                data[key] = str(v)
        if getattr(reader, "is_encrypted", False):
            data["Encrypted"] = "Yes"
    except Exception as e:
        data["error"] = f"Could not read PDF metadata: {e}"
    return data


def read_metadata(path):
    """Returns an ordered dict of sections: {section_name: {key: value}}."""
    sections = {"File Info": basic_file_info(path)}

    ext = os.path.splitext(path)[1].lower()

    if ext in IMAGE_EXTS:
        sections["Image / EXIF"] = image_metadata(path)
    elif ext in OOXML_EXTS:
        sections["Document Properties"] = ooxml_metadata(path)
    elif ext in PDF_EXTS:
        sections["PDF Metadata"] = pdf_metadata(path)
    elif ext in AUDIO_EXTS:
        tags = audio_tags(path)
        if tags:
            sections["Audio Tags"] = tags
        sections["Audio Technical Info"] = av_metadata(path)
    elif ext in VIDEO_EXTS:
        sections["Video / Audio Streams"] = av_metadata(path)
    else:
        sections["Note"] = {"info": "No specialized reader for this file type — showing basic file info only."}

    return sections

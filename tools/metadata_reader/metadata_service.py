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


def _fix_mojibake(text):
    """Root-cause fix for the 'Â©' style corruption.

    Pillow (and the IPTC/EXIF spec itself) treats these text fields as
    Latin-1/ASCII, decoding them byte-for-byte. Many real-world tools write
    UTF-8 into those same fields anyway (e.g. '©' as bytes C2 A9). Decoded
    as Latin-1 that becomes the two characters 'Â' + '©' — a classic
    mojibake pattern, not a display/font issue.

    Fix: re-encode the (wrongly-decoded) text back to raw bytes as Latin-1,
    then decode *those* bytes as UTF-8. If the text was never mis-decoded
    in the first place, that round trip fails (raises) or produces
    replacement characters, so we fall back to the original untouched —
    this only "fixes" text that was actually broken, for any character,
    not just '©'.
    """
    if not isinstance(text, str) or not text:
        return text
    try:
        candidate = text.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text
    if "\ufffd" in candidate:
        return text
    return candidate


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

    # Applied to every string that flows through here — EXIF, IPTC, XMP,
    # ffprobe tags — since the mis-decoding bug isn't specific to one field.
    text = _fix_mojibake(text)

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
    """EXIF-derived fields only (Make/Model/Software/Artist/Copyright/...).
    GPS, IPTC/IIM and XMP are handled by their own functions below and kept
    in separate sections — see gps_metadata(), iptc_metadata(), xmp_metadata().
    """
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
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
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id)
                    tag_name = tag if tag is not None else f"Unknown Tag ({tag_id})"
                    if tag_name == "GPSInfo":
                        continue  # separate [GPS] section — see gps_metadata()
                    # _clean_value() handles bytes/text, flags binary or
                    # unreadable data (MakerNote, UserComment, unknown vendor
                    # tags), and fixes the UTF-8-decoded-as-Latin-1 mojibake
                    # bug (e.g. 'Â©' -> '©') for any field, not just Copyright.
                    data[str(tag_name)] = _clean_value(value)
    except Exception as e:
        data["error"] = f"Could not read image metadata: {e}"
    return data


def gps_metadata(path):
    """[GPS] section — decoded from the EXIF GPSInfo IFD.

    Kept separate from the main EXIF section (rather than prefixing every
    key with 'GPS ') so it lines up with IPTC/XMP as its own namespace,
    per the 'don't merge sources' requirement.

    Root cause note: Image.Exif.items() only returns *top-level* IFD0
    entries. For GPSInfo (tag 0x8825) that's just an integer byte offset,
    not the resolved tag dict, so the old code's `value.items()` silently
    failed inside its own try/except and GPS came back empty. The GPS IFD
    has to be resolved explicitly via exif.get_ifd(GPSInfo).
    """
    try:
        from PIL import Image
        from PIL.ExifTags import GPSTAGS, IFD
    except ImportError:
        return {}

    data = {}
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return {}

            try:
                gps_ifd = exif.get_ifd(IFD.GPSInfo)
            except Exception:
                gps_ifd = {}
            if not gps_ifd:
                return {}

            gps_info = {GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}

            lat, lat_ref = gps_info.get("GPSLatitude"), gps_info.get("GPSLatitudeRef")
            lon, lon_ref = gps_info.get("GPSLongitude"), gps_info.get("GPSLongitudeRef")
            if lat and lon and lat_ref and lon_ref:
                lat_dec = _dms_to_decimal(lat, lat_ref)
                lon_dec = _dms_to_decimal(lon, lon_ref)
                if lat_dec is not None and lon_dec is not None:
                    data["Latitude"] = f"{lat_dec:.6f}"
                    data["Longitude"] = f"{lon_dec:.6f}"
                    data["Map Link"] = _maps_link(lat_dec, lon_dec)

            alt = gps_info.get("GPSAltitude")
            if alt is not None:
                alt_val = _safe_float(alt)
                data["Altitude"] = f"{alt_val:.1f} m" if alt_val is not None else str(alt)

            gps_date = gps_info.get("GPSDateStamp")
            gps_time = gps_info.get("GPSTimeStamp")
            if gps_date:
                data["Date/Time (UTC)"] = f"{gps_date} {gps_time or ''}".strip()

            # Raw IFD values too, in case a caller needs the untouched rationals.
            for k, v in gps_info.items():
                data[f"{k} (raw)"] = _clean_value(v)
    except Exception as e:
        data["error"] = f"Could not read GPS metadata: {e}"
    return data


# ---------------------------------------------------------------------------
# IPTC / IIM
# ---------------------------------------------------------------------------
# Root cause of "IPTC/IIM missing": IPTC data lives in a completely different
# JPEG segment (APP13 "Photoshop 3.0", resource block 0x0404) than EXIF
# (APP1 "Exif\0\0"). The old code only ever called img.getexif(), so this
# segment was never even looked at. Pillow already parses it into
# img.info["photoshop"] when opening the file — we just weren't reading it.

_IPTC_TAGS = {
    (2, 0): "Record Version",
    (2, 3): "Object Type Reference",
    (2, 5): "Object Name",
    (2, 7): "Edit Status",
    (2, 10): "Urgency",
    (2, 15): "Category",
    (2, 20): "Supplemental Category",
    (2, 22): "Fixture Identifier",
    (2, 25): "Keywords",
    (2, 40): "Special Instructions",
    (2, 55): "Date Created",
    (2, 60): "Time Created",
    (2, 62): "Digital Creation Date",
    (2, 63): "Digital Creation Time",
    (2, 65): "Originating Program",
    (2, 70): "Program Version",
    (2, 75): "Object Cycle",
    (2, 80): "By-line",
    (2, 85): "By-line Title",
    (2, 90): "City",
    (2, 92): "Sub-location",
    (2, 95): "Province/State",
    (2, 100): "Country/Primary Location Code",
    (2, 101): "Country/Primary Location Name",
    (2, 103): "Original Transmission Reference",
    (2, 105): "Headline",
    (2, 110): "Credit",
    (2, 115): "Source",
    (2, 116): "Copyright Notice",
    (2, 118): "Contact",
    (2, 120): "Caption/Abstract",
    (2, 122): "Writer/Editor",
}

# Marks the field as the character-set indicator escape sequence. When it
# contains ESC % G, the rest of the IIM record is UTF-8 per the IPTC spec.
_IPTC_CHARSET_TAG = (1, 90)
_IPTC_UTF8_MARKER = b"\x1b%G"


def _decode_iptc_bytes(value, prefer_utf8):
    """IIM text fields are raw bytes with no per-field encoding tag; the
    encoding is set once for the whole record via the (1,90) CodedCharacterSet
    marker. Try that, then fall back safely so nothing crashes on odd bytes."""
    if not isinstance(value, bytes):
        return _clean_value(value)
    encodings = ["utf-8", "cp1252", "latin-1"] if prefer_utf8 else ["cp1252", "utf-8", "latin-1"]
    for enc in encodings:
        try:
            return _clean_value(value.decode(enc))
        except Exception:
            continue
    return _clean_value(value.decode("latin-1", errors="replace"))


def iptc_metadata(path):
    """[IPTC / IIM] section, read via Pillow's IptcImagePlugin."""
    try:
        from PIL import Image, IptcImagePlugin
    except ImportError:
        return {}

    data = {}
    try:
        with Image.open(path) as img:
            info = IptcImagePlugin.getiptcinfo(img)
    except Exception as e:
        return {"error": f"Could not read IPTC/IIM metadata: {e}"}

    if not info:
        return {}

    prefer_utf8 = _IPTC_UTF8_MARKER in (info.get(_IPTC_CHARSET_TAG) or b"")

    try:
        for key, value in info.items():
            if key == _IPTC_CHARSET_TAG:
                continue
            name = _IPTC_TAGS.get(key, f"Tag {key[0]}:{key[1]}")
            if isinstance(value, list):
                # Repeated fields (Keywords, Supplemental Category, ...) —
                # keep as a real list so JSON export preserves the array.
                decoded = [_decode_iptc_bytes(v, prefer_utf8) for v in value]
                data[name] = decoded
            else:
                data[name] = _decode_iptc_bytes(value, prefer_utf8)
    except Exception as e:
        data["error"] = f"Could not decode IPTC/IIM metadata: {e}"

    return data


# ---------------------------------------------------------------------------
# XMP
# ---------------------------------------------------------------------------
# Root cause of "XMP missing": same story as IPTC — XMP lives in its own
# APP1 segment ("http://ns.adobe.com/xap/1.0/\0..."), separate from the
# EXIF APP1 segment. Pillow's JPEG plugin already extracts that raw XML
# packet into img.info["xmp"]; the old code never read it.

_XMP_NS_PREFIXES = {
    "http://purl.org/dc/elements/1.1/": "dc",
    "http://ns.adobe.com/xap/1.0/": "xmp",
    "http://ns.adobe.com/xap/1.0/rights/": "xmpRights",
    "http://ns.adobe.com/xap/1.0/mm/": "xmpMM",
    "http://ns.adobe.com/photoshop/1.0/": "photoshop",
    "http://ns.adobe.com/tiff/1.0/": "tiff",
    "http://ns.adobe.com/exif/1.0/": "exif",
    "http://cipa.jp/exif/1.0/": "exifEX",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf",
    "http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/": "Iptc4xmpCore",
    "http://iptc.org/std/Iptc4xmpExt/2008-02-29/": "Iptc4xmpExt",
    "http://ns.adobe.com/pdf/1.3/": "pdf",
    "http://www.w3.org/1999/xhtml": "xhtml",
}

_RDF_NS = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"


def _xmp_qname(tag):
    """'{uri}local' -> 'prefix:local', using known namespaces where
    possible and falling back to a generic-but-still-readable prefix
    derived from the URI for anything unrecognized (never dropped)."""
    if not tag.startswith("{"):
        return tag
    uri, local = tag[1:].split("}", 1)
    prefix = _XMP_NS_PREFIXES.get(uri)
    if not prefix:
        prefix = uri.rstrip("/").rsplit("/", 1)[-1] or "ns"
    return f"{prefix}:{local}"


def _rdf_list_items(elem):
    """Collect rdf:li text from a Bag/Seq/Alt container (e.g. dc:subject,
    dc:creator) so arrays like Keywords survive as real lists."""
    items = []
    for li in elem.iter(f"{_RDF_NS}li"):
        if li.text and li.text.strip():
            items.append(li.text.strip())
    return items


def _xmp_property_value(child):
    """Read one XMP property element: prefers an rdf:Bag/Seq/Alt list,
    then direct text, then any nested text, then an rdf:resource attribute.
    Returns None only if the property genuinely has nothing to show."""
    list_items = _rdf_list_items(child)
    if list_items:
        return list_items

    if child.text and child.text.strip():
        return child.text.strip()

    nested = [e.text.strip() for e in child.iter() if e is not child and e.text and e.text.strip()]
    if nested:
        return nested

    resource = child.attrib.get(f"{_RDF_NS}resource")
    if resource:
        return resource

    return None


def xmp_metadata(path):
    """[XMP] section. Walks every rdf:Description generically instead of
    hard-coding a fixed field list, so nothing present in the packet is
    silently dropped."""
    try:
        from PIL import Image
    except ImportError:
        return {"note": "Pillow not installed — cannot read XMP metadata."}

    try:
        with Image.open(path) as img:
            xmp_raw = img.info.get("xmp")
    except Exception as e:
        return {"error": f"Could not open file for XMP metadata: {e}"}

    if not xmp_raw:
        return {}

    if isinstance(xmp_raw, bytes):
        xmp_text = xmp_raw.decode("utf-8", errors="replace")
    else:
        xmp_text = str(xmp_raw)

    data = {}
    try:
        root = ET.fromstring(xmp_text)
        for desc in root.iter(f"{_RDF_NS}Description"):
            # Compact form: properties written as plain XML attributes
            # directly on rdf:Description (e.g. xmp:CreateDate="...").
            for attr, value in desc.attrib.items():
                if attr.endswith("about"):
                    continue
                name = _xmp_qname(attr)
                data.setdefault(name, _clean_value(value))

            # Expanded form: properties as child elements.
            for child in list(desc):
                name = _xmp_qname(child.tag)
                value = _xmp_property_value(child)
                if value is None:
                    continue
                if isinstance(value, list):
                    data[name] = [_clean_value(v) for v in value]
                else:
                    data[name] = _clean_value(value)
    except ET.ParseError as e:
        return {"error": f"Could not parse XMP XML: {e}"}
    except Exception as e:
        return {"error": f"Could not read XMP metadata: {e}"}

    if not data:
        data["note"] = "XMP packet present but no readable properties found."
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
        gps = gps_metadata(path)
        if gps:
            sections["GPS"] = gps
        iptc = iptc_metadata(path)
        if iptc:
            sections["IPTC / IIM"] = iptc
        xmp = xmp_metadata(path)
        if xmp:
            sections["XMP"] = xmp
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

"""
Regression tests for the Metadata Reader's EXIF / GPS / IPTC(IIM) / XMP
extraction and the UTF-8-decoded-as-Latin-1 encoding fix.

Fixtures used
-------------

1. tests/fixtures/synthetic_metadata_test.jpg — a small JPEG built
   specifically for this suite, containing real EXIF, IPTC/IIM (APP13
   "Photoshop 3.0"), XMP (APP1) and GPS segments — including a UTF-8 '©'
   written into Copyright / Artist / Caption / dc:rights the way real
   tools do it (which is exactly what triggers the Latin-1 mis-decode
   bug). This fixture is checked into the repo, so these tests always run
   and always exercise the real parsing code in metadata_service.py —
   nothing here asserts against a value that's hard-coded in the parser
   itself, only against what the parser actually extracted.

   Regenerate it with `python tests/fixtures/generate_synthetic_fixture.py`
   if you ever need to (requires the `piexif` package — test-tooling only,
   not a runtime dependency of the app).

2. tests/fixtures/Metadata_test_file_-_includes_data_in_IIM,_XMP,_and_Exif.jpg
   — the public Wikimedia Commons sample file by Carl Seibert used to
   demonstrate EXIF+IPTC+XMP side by side. It's a binary asset that isn't
   fetchable from this environment, so it isn't bundled here. Drop a copy
   into tests/fixtures/ and the TestRealWikimediaSample tests below will
   pick it up automatically; otherwise they're skipped (not failed).
"""

import importlib.util
import json
import os

import pytest


# ---------------------------------------------------------------------------
# Load metadata_service.py directly by path, so this test file doesn't
# require PySide6 / the rest of the MultiTool Studio app to be importable.
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
#_SERVICE_PATH = os.path.join(os.path.dirname(_HERE), "metadata_service.py")
_SERVICE_PATH = os.path.join(_HERE, "metadata_service.py")
_FIXTURES = os.path.join(_HERE, "fixtures")


def _load_service():
    spec = importlib.util.spec_from_file_location("metadata_service", _SERVICE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ms = _load_service()

SYNTHETIC_FIXTURE = os.path.join(_FIXTURES, "synthetic_metadata_test.jpg")
REAL_FIXTURE = os.path.join(
    _FIXTURES, "Metadata_test_file_-_includes_data_in_IIM,_XMP,_and_Exif.jpg"
)


@pytest.fixture(scope="module")
def synthetic_sections():
    assert os.path.isfile(SYNTHETIC_FIXTURE), (
        "tests/fixtures/synthetic_metadata_test.jpg is missing — see the "
        "module docstring for how to regenerate it."
    )
    return ms.read_metadata(SYNTHETIC_FIXTURE)


# ---------------------------------------------------------------------------
# Core requirement: EXIF, GPS, IPTC/IIM and XMP are ALL extracted, as
# separate, non-merged sections — this is the actual bug being fixed.
# ---------------------------------------------------------------------------

def test_all_four_sections_present(synthetic_sections):
    for section in ("Image / EXIF", "GPS", "IPTC / IIM", "XMP"):
        assert section in synthetic_sections, f"missing section: {section}"
        assert synthetic_sections[section], f"section came back empty: {section}"


def test_exif_fields_extracted(synthetic_sections):
    exif = synthetic_sections["Image / EXIF"]
    for key in ("Make", "Model", "Software", "DateTime", "Artist", "Copyright", "ImageDescription"):
        assert key in exif and exif[key], f"EXIF field not extracted: {key}"


def test_gps_extracted_and_decoded(synthetic_sections):
    gps = synthetic_sections["GPS"]
    assert "Latitude" in gps and "Longitude" in gps
    lat = float(gps["Latitude"])
    lon = float(gps["Longitude"])
    # Regression guard for the exif.get_ifd() bug specifically: these must
    # be real decoded decimal degrees, not 0.0 (which is what you get if
    # the GPS IFD silently failed to resolve).
    assert -90 <= lat <= 90 and lat != 0.0
    assert -180 <= lon <= 180 and lon != 0.0
    assert gps.get("Map Link", "").startswith("https://www.google.com/maps?q=")


def test_iptc_fields_extracted(synthetic_sections):
    iptc = synthetic_sections["IPTC / IIM"]
    for key in ("By-line", "Copyright Notice", "Caption/Abstract", "City"):
        assert key in iptc and iptc[key], f"IPTC field not extracted: {key}"


def test_iptc_keywords_preserved_as_list(synthetic_sections):
    iptc = synthetic_sections["IPTC / IIM"]
    assert "Keywords" in iptc
    assert isinstance(iptc["Keywords"], list), "Keywords must stay an array, not be flattened into a string"
    assert set(iptc["Keywords"]) == {"keyword1", "keyword2"}


def test_xmp_fields_extracted(synthetic_sections):
    xmp = synthetic_sections["XMP"]
    for key in ("dc:creator", "dc:description", "dc:rights", "photoshop:Headline", "xmp:CreateDate"):
        assert key in xmp and xmp[key], f"XMP field not extracted: {key}"


def test_xmp_arrays_preserved_as_list(synthetic_sections):
    xmp = synthetic_sections["XMP"]
    assert isinstance(xmp["dc:subject"], list)
    assert set(xmp["dc:subject"]) == {"keyword1", "keyword2"}


def test_sources_are_not_merged(synthetic_sections):
    """The same logical field ('Copyright') exists in EXIF, IPTC and XMP
    in this fixture — they must appear as 3 separate values in 3 separate
    sections, not collapsed into one shared value."""
    exif_section = synthetic_sections["Image / EXIF"]
    iptc_section = synthetic_sections["IPTC / IIM"]
    xmp_section = synthetic_sections["XMP"]

    assert exif_section["Copyright"]
    assert iptc_section["Copyright Notice"]
    assert xmp_section["dc:rights"]
    assert exif_section is not iptc_section
    assert iptc_section is not xmp_section


# ---------------------------------------------------------------------------
# Encoding bug: 'Â©' must never appear once the fix is applied, and a
# correctly-encoded '©' must appear in each source that has one.
# ---------------------------------------------------------------------------

def test_no_mojibake_anywhere(synthetic_sections):
    dumped = json.dumps(synthetic_sections, ensure_ascii=False)
    assert "Â©" not in dumped, "found the UTF-8-decoded-as-Latin-1 mojibake pattern in the output"


def test_copyright_symbol_correct_in_all_three_sources(synthetic_sections):
    assert "©" in synthetic_sections["Image / EXIF"]["Copyright"]
    assert "©" in synthetic_sections["IPTC / IIM"]["Copyright Notice"]
    rights = synthetic_sections["XMP"]["dc:rights"]
    rights_text = rights[0] if isinstance(rights, list) else rights
    assert "©" in rights_text


def test_fix_mojibake_helper_is_conservative():
    """The fix must only touch text that was actually mis-decoded — it
    must never corrupt already-correct ASCII or already-correct Unicode."""
    assert ms._fix_mojibake("Â© Copyright 2017 Carl Seibert") == "© Copyright 2017 Carl Seibert"
    assert ms._fix_mojibake("plain ascii text") == "plain ascii text"
    assert ms._fix_mojibake("already correct © unicode Ω text") == "already correct © unicode Ω text"
    assert ms._fix_mojibake("") == ""
    assert ms._fix_mojibake(None) is None


# ---------------------------------------------------------------------------
# Safety requirements: missing metadata / unknown tags / binary data must
# never crash the reader, and nothing should be silently dropped.
# ---------------------------------------------------------------------------

def test_file_with_no_metadata_does_not_crash(tmp_path):
    from PIL import Image

    plain_path = tmp_path / "plain.jpg"
    Image.new("RGB", (10, 10)).save(plain_path, "JPEG")

    sections = ms.read_metadata(str(plain_path))

    assert "File Info" in sections
    assert "Image / EXIF" in sections
    # No GPS/IPTC/XMP section should be *added* when there's nothing there,
    # but nothing should raise either.
    assert not sections.get("GPS")
    assert not sections.get("IPTC / IIM")
    assert not sections.get("XMP")


def test_unknown_exif_tag_is_labelled_not_dropped(tmp_path):
    """A vendor/private EXIF tag with no entry in PIL.ExifTags.TAGS must
    still show up (labelled 'Unknown Tag (id)'), not vanish."""
    from PIL import Image

    UNKNOWN_TAG_ID = 0xC7D9  # not a standard EXIF tag
    img = Image.new("RGB", (10, 10))
    exif = Image.Exif()
    exif[UNKNOWN_TAG_ID] = "custom-vendor-value"
    path = tmp_path / "unknown_tag.jpg"
    img.save(path, "JPEG", exif=exif)

    exif_section = ms.image_metadata(str(path))
    expected_key = f"Unknown Tag ({UNKNOWN_TAG_ID})"
    assert expected_key in exif_section
    assert exif_section[expected_key] == "custom-vendor-value"


def test_clean_value_handles_binary_without_crashing():
    blob = bytes(range(256)) * 4
    result = ms._clean_value(blob)
    assert isinstance(result, str)
    assert "binary" in result.lower()


def test_dms_to_decimal_handles_bad_input_safely():
    # Must never raise — unparseable components fall back to 0.0 rather
    # than propagating an exception up into the metadata reader.
    result = ms._dms_to_decimal(("not", "a", "number"), "N")
    assert isinstance(result, float)
    # Too few components IS caught internally and returns None, not a crash.
    assert ms._dms_to_decimal((1, 2), "N") is None


def test_iptc_and_xmp_are_safe_on_a_non_image_file(tmp_path):
    """Calling the image-specific readers on a file that isn't a valid
    image must degrade gracefully, never raise."""
    junk_path = tmp_path / "not_really_a_jpeg.jpg"
    junk_path.write_bytes(b"this is not a jpeg file at all")

    assert ms.iptc_metadata(str(junk_path)) is not None
    assert ms.xmp_metadata(str(junk_path)) is not None
    assert ms.gps_metadata(str(junk_path)) is not None
    assert ms.image_metadata(str(junk_path)) is not None


# ---------------------------------------------------------------------------
# Optional: run the same structural assertions against the real Wikimedia
# sample file, if present. No field VALUES are hard-coded here — only that
# each section exists and is non-empty, and that no mojibake survives.
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.path.isfile(REAL_FIXTURE),
    reason=(
        "Real Wikimedia sample not present. Download "
        "'Metadata_test_file_-_includes_data_in_IIM,_XMP,_and_Exif.jpg' from "
        "Wikimedia Commons and place it in tests/fixtures/ to enable this test."
    ),
)
class TestRealWikimediaSample:
    @pytest.fixture(scope="class")
    def sections(self):
        return ms.read_metadata(REAL_FIXTURE)

    def test_exif_present(self, sections):
        assert sections.get("Image / EXIF")

    def test_gps_present(self, sections):
        assert sections.get("GPS")

    def test_iptc_present(self, sections):
        assert sections.get("IPTC / IIM")

    def test_xmp_present(self, sections):
        assert sections.get("XMP")

    def test_no_mojibake(self, sections):
        dumped = json.dumps(sections, ensure_ascii=False)
        assert "Â©" not in dumped

"""Build a synthetic JPEG with EXIF + IPTC/IIM (Photoshop APP13) + XMP (APP1)
segments so we can test the parser end-to-end without needing network access
to fetch the real Wikimedia sample file."""
import struct
from PIL import Image
import piexif  # not guaranteed installed; fallback below if missing

def build_exif_bytes():
    # UTF-8 encoded "©" written into Copyright/Artist, but EXIF ASCII fields
    # get decoded by Pillow as Latin-1 -> reproduces the 'Â©' mojibake bug.
    copyright_utf8 = "© Copyright 2017 Carl Seibert".encode("utf-8")
    artist_utf8 = "Carl Seibert".encode("utf-8")
    zeroth = {
        piexif.ImageIFD.Make: b"TestCam",
        piexif.ImageIFD.Model: b"TestModel X100",
        piexif.ImageIFD.Software: b"MetadataReaderTestSuite",
        piexif.ImageIFD.Artist: artist_utf8,
        piexif.ImageIFD.Copyright: copyright_utf8,
        piexif.ImageIFD.ImageDescription: b"Synthetic test image",
        piexif.ImageIFD.DateTime: b"2017:01:01 12:00:00",
    }
    gps = {
        piexif.GPSIFD.GPSLatitudeRef: b"N",
        piexif.GPSIFD.GPSLatitude: [(40, 1), (42, 1), (46, 1)],
        piexif.GPSIFD.GPSLongitudeRef: b"W",
        piexif.GPSIFD.GPSLongitude: [(74, 1), (0, 1), (21, 1)],
        piexif.GPSIFD.GPSAltitude: (15, 1),
    }
    exif_dict = {"0th": zeroth, "Exif": {}, "GPS": gps, "1st": {}, "thumbnail": None}
    return piexif.dump(exif_dict)


def build_iptc_app13():
    """Build a minimal Photoshop 3.0 APP13 segment containing an IPTC-NAA
    (resource ID 0x0404) record with a couple of IIM fields, UTF-8 encoded
    with the ESC %G charset marker."""
    def iim_field(record, dataset, value_bytes):
        return struct.pack(">BBBH", 0x1C, record, dataset, len(value_bytes)) + value_bytes

    iim = b""
    iim += iim_field(1, 90, b"\x1b%G")  # CodedCharacterSet = UTF-8
    iim += iim_field(2, 80, "Carl Seibert".encode("utf-8"))       # By-line
    iim += iim_field(2, 116, "© Copyright 2017 Carl Seibert".encode("utf-8"))  # Copyright Notice
    iim += iim_field(2, 120, "Test caption with a © sign".encode("utf-8"))     # Caption/Abstract
    iim += iim_field(2, 25, "keyword1".encode("utf-8"))           # Keywords (repeated tag)
    iim += iim_field(2, 25, "keyword2".encode("utf-8"))
    iim += iim_field(2, 90, "Testville".encode("utf-8"))          # City

    # Wrap in an 8BIM Image Resource Block, resource id 0x0404
    name = b"\x00\x00"  # pascal string "" padded to even
    resource = b"8BIM" + struct.pack(">H", 0x0404) + name + struct.pack(">I", len(iim)) + iim
    if len(iim) % 2:
        resource += b"\x00"

    app13_payload = b"Photoshop 3.0\x00" + resource
    segment = struct.pack(">HH", 0xFFED, len(app13_payload) + 2) + app13_payload
    return segment


def build_xmp_app1():
    xmp_xml = """<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/"
    xmp:CreateDate="2017-01-01T12:00:00">
   <dc:creator>
    <rdf:Seq>
     <rdf:li>Carl Seibert</rdf:li>
    </rdf:Seq>
   </dc:creator>
   <dc:description>
    <rdf:Alt>
     <rdf:li xml:lang="x-default">XMP description with a \u00a9 sign</rdf:li>
    </rdf:Alt>
   </dc:description>
   <dc:rights>
    <rdf:Alt>
     <rdf:li xml:lang="x-default">\u00a9 Copyright 2017 Carl Seibert</rdf:li>
    </rdf:Alt>
   </dc:rights>
   <dc:subject>
    <rdf:Bag>
     <rdf:li>keyword1</rdf:li>
     <rdf:li>keyword2</rdf:li>
    </rdf:Bag>
   </dc:subject>
   <photoshop:Headline>Test Headline</photoshop:Headline>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""
    xmp_bytes = xmp_xml.encode("utf-8")
    header = b"http://ns.adobe.com/xap/1.0/\x00"
    payload = header + xmp_bytes
    segment = struct.pack(">HH", 0xFFE1, len(payload) + 2) + payload
    return segment


def main(out_path):
    img = Image.new("RGB", (64, 48), color=(120, 160, 200))
    base_path = out_path + ".base.jpg"
    img.save(base_path, "JPEG")

    with open(base_path, "rb") as f:
        raw = f.read()

    assert raw[0:2] == b"\xff\xd8"
    insert_at = 2

    exif_bytes = build_exif_bytes()
    exif_segment = struct.pack(">HH", 0xFFE1, len(exif_bytes) + 2 + 6) + b"Exif\x00\x00" + exif_bytes

    iptc_segment = build_iptc_app13()
    xmp_segment = build_xmp_app1()

    new_raw = raw[:insert_at] + exif_segment + iptc_segment + xmp_segment + raw[insert_at:]

    with open(out_path, "wb") as f:
        f.write(new_raw)

    print("wrote", out_path, len(new_raw), "bytes")


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "synthetic_metadata_test.jpg")

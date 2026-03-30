"""Parse .dsevents binary files: header and event records."""

import struct

# LabView epoch: 1904-01-01 00:00:00 UTC
LABVIEW_EPOCH_OFFSET = -2082826800

HEADER_SIZE = 20
HEADER_FORMAT = ">iqQ"  # version (int32), timestamp_sec (int64), timestamp_frac (uint64)

RECORD_HEADER_SIZE = 20
RECORD_HEADER_FORMAT = ">qQi"  # timestamp_sec (int64), timestamp_frac (uint64), text_length (int32)


def labview_to_unix(seconds, fractional):
    """Convert LabView timestamp to Unix timestamp."""
    return LABVIEW_EPOCH_OFFSET + seconds + fractional / (2**64)


def parse_header(data):
    """Parse the 20-byte file header. Returns dict with version and timestamp."""
    if len(data) < HEADER_SIZE:
        raise ValueError(f"File too short for header: {len(data)} bytes")
    version, ts_sec, ts_frac = struct.unpack_from(HEADER_FORMAT, data, 0)
    return {
        "version": version,
        "timestamp": labview_to_unix(ts_sec, ts_frac),
        "timestamp_sec": ts_sec,
        "timestamp_frac": ts_frac,
    }


def parse_dsevents_file(data):
    """Parse a complete .dsevents file. Returns dict with header and events list."""
    header = parse_header(data)
    events = []
    offset = HEADER_SIZE

    while offset + RECORD_HEADER_SIZE <= len(data):
        ts_sec, ts_frac, text_len = struct.unpack_from(RECORD_HEADER_FORMAT, data, offset)
        offset += RECORD_HEADER_SIZE

        if text_len < 0 or offset + text_len > len(data):
            break  # corrupt record, stop parsing

        text_bytes = data[offset : offset + text_len]
        offset += text_len

        text = text_bytes.decode("utf-8", errors="replace")

        events.append({
            "timestamp": labview_to_unix(ts_sec, ts_frac),
            "timestamp_sec": ts_sec,
            "timestamp_frac": ts_frac,
            "text": text,
        })

    return {"header": header, "events": events}


def parse_dsevents_path(filepath):
    """Parse a .dsevents file from a file path."""
    with open(filepath, "rb") as f:
        data = f.read()
    return parse_dsevents_file(data)

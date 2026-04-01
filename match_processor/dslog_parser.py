"""Parse .dslog binary files: header and variable-length records."""

import struct

LABVIEW_EPOCH_OFFSET = -2082826800

HEADER_SIZE = 20
HEADER_FORMAT = ">iqQ"  # version (int32), timestamp_sec (int64), timestamp_frac (uint64)

# 10-byte fixed section per record
FIXED_SIZE = 10
FIXED_FORMAT = ">BbHBBBBH"  # trip, pkt_loss, voltage, cpu, status, can, wifi_sig, wifi_bw

PD_HEADER_SIZE = 4
PD_SIZES = {0x21: 33, 0x19: 25}  # REV PDH, CTRE PDP

EXPECTED_VERSION = 4


def labview_to_unix(seconds, fractional):
    """Convert LabVIEW timestamp to Unix timestamp."""
    return LABVIEW_EPOCH_OFFSET + seconds + fractional / (2**64)


def parse_dslog_header(data):
    """Parse the 20-byte dslog header.

    Returns dict with version, timestamp, timestamp_sec, timestamp_frac.
    Returns None if data is truncated or version is unsupported (with a warning printed).
    """
    if len(data) < HEADER_SIZE:
        print(f"  Warning: dslog file too short for header ({len(data)} bytes), skipping.")
        return None

    version, ts_sec, ts_frac = struct.unpack_from(HEADER_FORMAT, data, 0)

    if version != EXPECTED_VERSION:
        print(f"  Warning: dslog version {version} (expected {EXPECTED_VERSION}), skipping.")
        return None

    return {
        "version": version,
        "timestamp": labview_to_unix(ts_sec, ts_frac),
        "timestamp_sec": ts_sec,
        "timestamp_frac": ts_frac,
    }

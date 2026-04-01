import os
import struct
import tempfile
import shutil

import pytest


# LabView epoch offset: seconds between 1904-01-01 and 1970-01-01
LABVIEW_EPOCH_OFFSET = -2082826800


def make_dsevents_header(unix_timestamp=0.0, version=4):
    """Build a 20-byte .dsevents file header."""
    lv_seconds = int(unix_timestamp - LABVIEW_EPOCH_OFFSET)
    lv_fractional = 0
    return struct.pack(">iqQ", version, lv_seconds, lv_fractional)


def make_event_record(text, unix_timestamp=0.0):
    """Build a single event record (16-byte timestamp + 4-byte length + text)."""
    lv_seconds = int(unix_timestamp - LABVIEW_EPOCH_OFFSET)
    lv_fractional = 0
    text_bytes = text.encode("utf-8")
    return struct.pack(">qQi", lv_seconds, lv_fractional, len(text_bytes)) + text_bytes


def make_dsevents_file(events, unix_timestamp=0.0, version=4):
    """Build a complete .dsevents file as bytes."""
    header = make_dsevents_header(unix_timestamp, version)
    records = b"".join(make_event_record(text, unix_timestamp) for text in events)
    return header + records


# ── dslog fixture helpers ──

DSLOG_HEADER_FORMAT = ">iqQ"  # version (int32), ts_sec (int64), ts_frac (uint64)
DSLOG_HEADER_SIZE = 20

# 10-byte fixed section: trip(u8), pkt_loss(i8), voltage(u16 BE), cpu(u8), status(u8), can(u8), wifi_sig(u8), wifi_bw(u16 BE)
DSLOG_FIXED_FORMAT = ">BbHBBBBH"
DSLOG_FIXED_SIZE = 10

# PD header: 3 opaque bytes + 1 type byte
DSLOG_PD_HEADER_SIZE = 4

# PD additional data sizes by type
PD_SIZES = {0x21: 33, 0x19: 25}  # REV PDH, CTRE PDP


def make_dslog_header(unix_timestamp=0.0, version=4):
    """Build a 20-byte .dslog file header."""
    lv_seconds = int(unix_timestamp - LABVIEW_EPOCH_OFFSET)
    lv_fractional = 0
    return struct.pack(DSLOG_HEADER_FORMAT, version, lv_seconds, lv_fractional)


def make_dslog_record(status=0xFF, voltage_raw=3072, trip=0, pkt_loss=0,
                      cpu=0, can=0, wifi_sig=0, wifi_bw=0, pd_type=0x21):
    """Build a single dslog record.

    Args:
        status: status mask byte (inverted logic: 0=active). Default 0xFF = all inactive (Disconnected).
        voltage_raw: uint16 value, divide by 256 for volts. Default 3072 = 12.0V.
        trip: raw trip time byte (× 0.5 = ms).
        pkt_loss: raw packet loss byte (int8, × 4 × 0.01).
        cpu: raw CPU byte (× 0.5 × 0.01 = fraction).
        can: raw CAN byte (× 0.5 × 0.01 = fraction).
        pd_type: PD device type (0x21=REV, 0x19=CTRE, other=none).
    """
    fixed = struct.pack(DSLOG_FIXED_FORMAT,
                        trip, pkt_loss, voltage_raw, cpu, status, can, wifi_sig, wifi_bw)
    pd_header = struct.pack("4B", 0, 0, 0, pd_type)
    pd_extra_size = PD_SIZES.get(pd_type, 0)
    pd_data = b"\x00" * pd_extra_size
    return fixed + pd_header + pd_data


def make_dslog_file(records_args, unix_timestamp=0.0, version=4):
    """Build a complete .dslog file as bytes.

    Args:
        records_args: list of dicts, each passed as kwargs to make_dslog_record.
    """
    header = make_dslog_header(unix_timestamp, version)
    records = b"".join(make_dslog_record(**kwargs) for kwargs in records_args)
    return header + records


@pytest.fixture
def tmp_dirs(tmp_path):
    """Create source and destination directories for testing."""
    src = tmp_path / "source"
    dst = tmp_path / "dest"
    src.mkdir()
    dst.mkdir()
    return src, dst


@pytest.fixture
def sample_match_dsevents():
    """Return bytes for a .dsevents file representing a real FRC match."""
    return make_dsevents_file([
        "Info Joystick 0: (Controller (Xbox One For Windows))6 axes, 16 buttons, 1 POVs. "
        "Info Joystick 1: (Controller (Gamepad F310))6 axes, 10 buttons, 1 POVs. ",
        "FMS Connected:   Qualification - 52:1, Field Time: 26/3/29 13:35:4\n"
        " -- FRC Driver Station - Version 26.0",
        "Code Start Notification. ",
        "<TagVersion>1 <time> 00.000 <count> 1 <flags> 2 <Code> 44000 "
        "<details> Driver Station not keeping up with protocol rates "
        "<location> Driver Station <stack> ",
        "Warning <Code> 44007 <secondsSinceReboot> 116.460\r<Description>FRC: Time since robot boot.",
    ])


@pytest.fixture
def sample_nonmatch_dsevents():
    """Return bytes for a .dsevents file that is NOT a real match (None type)."""
    return make_dsevents_file([
        "FMS Connected:   None - 0:0, Field Time: -100/0/0 0:0:0\n"
        " -- FRC Driver Station - Version 26.0",
    ])

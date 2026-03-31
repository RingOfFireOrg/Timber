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

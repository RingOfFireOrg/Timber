# FRC Match Log Processor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI tool that identifies FRC match log files, extracts match metadata, writes human-readable event summaries, and copies organized files to a destination folder.

**Architecture:** Single-script tool (`process_matches.py`) with internal modules for binary parsing, event filtering, and file operations. Tests live in `tests/` using pytest. No external dependencies beyond stdlib for the script itself.

**Tech Stack:** Python 3.14 (via `uv`), pytest for testing, `uv` for project management.

**Spec:** `docs/superpowers/specs/2026-03-30-match-log-processor-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `process_matches.py` | CLI entry point: argparse, scan, confirm, orchestrate |
| `dsevents_parser.py` | Parse `.dsevents` binary format: header, event records, text extraction |
| `match_identifier.py` | Extract FMS match info, build match IDs, group files by match |
| `event_formatter.py` | Filter events, format for display, repeat collapsing |
| `match_writer.py` | Write `match_events.txt`, copy file pairs to destination |
| `tests/test_dsevents_parser.py` | Tests for binary parsing |
| `tests/test_match_identifier.py` | Tests for match identification and grouping |
| `tests/test_event_formatter.py` | Tests for event filtering and repeat collapsing |
| `tests/test_match_writer.py` | Tests for file writing and copying |
| `tests/test_integration.py` | End-to-end tests using real `.dsevents` files from the repo |
| `tests/conftest.py` | Shared fixtures (sample binary data, temp directories) |

---

## Task 0: Project Setup

**Files:**
- Create: `pyproject.toml`
- Create: `tests/conftest.py`

- [ ] **Step 1: Initialize Python project with uv**

```bash
cd /workspace
uv init --no-readme --python 3.14
```

- [ ] **Step 2: Add pytest as dev dependency**

```bash
uv add --dev pytest
```

- [ ] **Step 3: Create tests directory and conftest.py**

```bash
mkdir -p tests
```

Create `tests/conftest.py`:

```python
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
    return struct.pack(">iQQ", version, lv_seconds, lv_fractional)


def make_event_record(text, unix_timestamp=0.0):
    """Build a single event record (16-byte timestamp + 4-byte length + text)."""
    lv_seconds = int(unix_timestamp - LABVIEW_EPOCH_OFFSET)
    lv_fractional = 0
    text_bytes = text.encode("utf-8")
    return struct.pack(">QQi", lv_seconds, lv_fractional, len(text_bytes)) + text_bytes


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
        "\x00#Info 26.0Info FMS Event Name: NCPEM",
        "nInfo Joystick 0: (Controller (Xbox One For Windows))6 axes, 16 buttons, 1 POVs. "
        "Info Joystick 1: (Controller (Gamepad F310))6 axes, 10 buttons, 1 POVs. ",
        "hFMS Connected:   Qualification - 52:1, Field Time: 26/3/29 13:35:4\n"
        " -- FRC Driver Station - Version 26.0",
        "Code Start Notification. ",
        "<TagVersion>1 <time> 00.000 <count> 1 <flags> 2 <Code> 44000 "
        "<details> Driver Station not keeping up with protocol rates "
        "<location> Driver Station <stack> ",
    ])


@pytest.fixture
def sample_nonmatch_dsevents():
    """Return bytes for a .dsevents file that is NOT a real match (None type)."""
    return make_dsevents_file([
        "\x00#Info 26.0Info FMS Event Name: NCPEM",
        "hFMS Connected:   None - 0:0, Field Time: -100/0/0 0:0:0\n"
        " -- FRC Driver Station - Version 26.0",
    ])
```

- [ ] **Step 4: Verify pytest runs (no tests yet)**

Run: `uv run pytest tests/ -v`
Expected: "no tests ran" with exit code 5 (no tests collected)

- [ ] **Step 5: Commit**

```
feat: initialize Python project with uv and pytest
```

Files: `pyproject.toml`, `uv.lock`, `tests/conftest.py`

---

## Task 1: Binary Parser — `.dsevents` Header and Event Records

**Files:**
- Create: `dsevents_parser.py`
- Create: `tests/test_dsevents_parser.py`

- [ ] **Step 1: Write failing tests for header parsing**

Create `tests/test_dsevents_parser.py`:

```python
import struct

from conftest import make_dsevents_header, make_dsevents_file, make_event_record, LABVIEW_EPOCH_OFFSET


def test_parse_header_version():
    from dsevents_parser import parse_header
    data = make_dsevents_header(unix_timestamp=1000000.0, version=4)
    header = parse_header(data)
    assert header["version"] == 4


def test_parse_header_timestamp():
    from dsevents_parser import parse_header
    data = make_dsevents_header(unix_timestamp=1000000.0, version=4)
    header = parse_header(data)
    assert abs(header["timestamp"] - 1000000.0) < 1.0


def test_parse_events_single_record():
    from dsevents_parser import parse_dsevents_file
    file_bytes = make_dsevents_file(["Hello world"])
    result = parse_dsevents_file(file_bytes)
    assert len(result["events"]) == 1
    assert result["events"][0]["text"] == "Hello world"


def test_parse_events_multiple_records():
    from dsevents_parser import parse_dsevents_file
    file_bytes = make_dsevents_file(["Event one", "Event two", "Event three"])
    result = parse_dsevents_file(file_bytes)
    assert len(result["events"]) == 3
    assert result["events"][1]["text"] == "Event two"


def test_parse_events_empty_file():
    from dsevents_parser import parse_dsevents_file
    file_bytes = make_dsevents_header()  # header only, no events
    result = parse_dsevents_file(file_bytes)
    assert len(result["events"]) == 0


def test_parse_real_file():
    """Test parsing against a real .dsevents file from the repo."""
    from dsevents_parser import parse_dsevents_file
    with open("2026/UNCPembroke/2026_03_29 09_34_29 Sun.dsevents", "rb") as f:
        data = f.read()
    result = parse_dsevents_file(data)
    assert result["header"]["version"] == 4
    assert len(result["events"]) > 0
    # At least one event should contain FMS Connected
    texts = [e["text"] for e in result["events"]]
    assert any("FMS Connected" in t for t in texts)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_dsevents_parser.py -v`
Expected: FAIL — `dsevents_parser` module not found

- [ ] **Step 3: Implement the parser**

Create `dsevents_parser.py`:

```python
"""Parse FRC Driver Station .dsevents binary files."""

import struct

# Seconds between LabView epoch (1904-01-01) and Unix epoch (1970-01-01)
LABVIEW_EPOCH_OFFSET = -2082826800

HEADER_SIZE = 20
HEADER_FORMAT = ">iqQ"  # version (int32), timestamp_sec (int64), timestamp_frac (uint64)

RECORD_HEADER_SIZE = 20
RECORD_HEADER_FORMAT = ">qQi"  # timestamp_sec (int64), timestamp_frac (uint64), text_length


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

        # Strip leading non-printable bytes (length/type prefix in some records)
        text = text_bytes.decode("utf-8", errors="replace")
        # Remove leading control characters
        text = text.lstrip("\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0b\x0c\x0e\x0f"
                           "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f")
        # Some records have a leading length byte followed by content — skip any
        # remaining non-ASCII prefix characters
        while text and ord(text[0]) < 32:
            text = text[1:]

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_dsevents_parser.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```
feat: add .dsevents binary parser with header and event record extraction
```

Files: `dsevents_parser.py`, `tests/test_dsevents_parser.py`

---

## Task 2: Match Identifier — FMS Parsing, Match IDs, Grouping

**Files:**
- Create: `match_identifier.py`
- Create: `tests/test_match_identifier.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_match_identifier.py`:

```python
import os
import struct

from conftest import make_dsevents_file, make_dsevents_header


def test_extract_fms_info_qualification():
    from match_identifier import extract_fms_info
    events = [
        {"text": '#Info 26.0Info FMS Event Name: NCPEM'},
        {"text": 'FMS Connected:   Qualification - 52:1, Field Time: 26/3/29 13:35:4\n -- FRC Driver Station - Version 26.0'},
    ]
    info = extract_fms_info(events)
    assert info["match_type"] == "Qualification"
    assert info["match_number"] == 52
    assert info["replay"] == 1
    assert info["field_time"] == "26/3/29 13:35:4"
    assert info["ds_version"] == "FRC Driver Station - Version 26.0"
    assert info["event_name"] == "NCPEM"


def test_extract_fms_info_elimination():
    from match_identifier import extract_fms_info
    events = [
        {"text": 'FMS Connected:   Elimination - 6:1, Field Time: 26/3/29 18:11:7\n -- FRC Driver Station - Version 26.0'},
    ]
    info = extract_fms_info(events)
    assert info["match_type"] == "Elimination"
    assert info["match_number"] == 6
    assert info["replay"] == 1


def test_extract_fms_info_none_match():
    from match_identifier import extract_fms_info
    events = [
        {"text": 'FMS Connected:   None - 0:0, Field Time: -100/0/0 0:0:0\n -- FRC Driver Station - Version 26.0'},
    ]
    info = extract_fms_info(events)
    assert info["match_type"] == "None"


def test_extract_fms_info_no_fms():
    from match_identifier import extract_fms_info
    events = [{"text": "Some random event"}]
    info = extract_fms_info(events)
    assert info is None


def test_build_match_id_qualification():
    from match_identifier import build_match_id
    assert build_match_id("Qualification", 52, 1) == "Q52"


def test_build_match_id_qualification_replay():
    from match_identifier import build_match_id
    assert build_match_id("Qualification", 52, 2) == "Q52_R2"


def test_build_match_id_elimination():
    from match_identifier import build_match_id
    assert build_match_id("Elimination", 6, 1) == "E6_R1"


def test_build_match_key():
    from match_identifier import build_match_key
    assert build_match_key("Qualification", 52, 1) == "Qualification - 52:1"


def test_is_real_match():
    from match_identifier import is_real_match
    assert is_real_match({"match_type": "Qualification"}) is True
    assert is_real_match({"match_type": "Elimination"}) is True
    assert is_real_match({"match_type": "Practice"}) is True
    assert is_real_match({"match_type": "None"}) is False
    assert is_real_match(None) is False


def test_group_files_by_match_single():
    from match_identifier import group_files_by_match
    files = [
        {"path": "/src/a.dsevents", "fms_info": {"match_type": "Qualification", "match_number": 52, "replay": 1}, "header_timestamp": 1000.0},
    ]
    groups = group_files_by_match(files)
    assert "Qualification - 52:1" in groups
    assert len(groups["Qualification - 52:1"]) == 1


def test_group_files_by_match_restart():
    from match_identifier import group_files_by_match
    files = [
        {"path": "/src/b.dsevents", "fms_info": {"match_type": "Qualification", "match_number": 52, "replay": 1}, "header_timestamp": 2000.0},
        {"path": "/src/a.dsevents", "fms_info": {"match_type": "Qualification", "match_number": 52, "replay": 1}, "header_timestamp": 1000.0},
    ]
    groups = group_files_by_match(files)
    group = groups["Qualification - 52:1"]
    assert len(group) == 2
    # Should be sorted by timestamp
    assert group[0]["path"] == "/src/a.dsevents"
    assert group[1]["path"] == "/src/b.dsevents"


def test_extract_joystick_info():
    from match_identifier import extract_joystick_info
    events = [
        {"text": "Info Joystick 0: (Controller (Xbox One For Windows))6 axes, 16 buttons, 1 POVs. "
                 "Info Joystick 1: (Controller (Gamepad F310))6 axes, 10 buttons, 1 POVs. "
                 "Info Joystick 0: (Controller (Xbox One For Windows))6 axes, 16 buttons, 1 POVs. "},
    ]
    joysticks = extract_joystick_info(events)
    assert len(joysticks) == 2
    assert joysticks[0]["name"] == "Controller (Xbox One For Windows)"
    assert joysticks[0]["axes"] == 6
    assert joysticks[1]["name"] == "Controller (Gamepad F310)"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_match_identifier.py -v`
Expected: FAIL — `match_identifier` module not found

- [ ] **Step 3: Implement match identifier**

Create `match_identifier.py`:

```python
"""Extract FMS match info from parsed .dsevents data and group files by match."""

import re

FMS_PATTERN = re.compile(
    r"FMS Connected:\s+(\w+)\s*-\s*(\d+):(\d+),\s*Field Time:\s*(.+)\n\s*--\s*(.+)"
)

EVENT_NAME_PATTERN = re.compile(r"Info FMS Event Name:\s*(\w+)")

JOYSTICK_PATTERN = re.compile(
    r"Info Joystick (\d+): \(([^)]+)\)(\d+) axes, (\d+) buttons, (\d+) POVs\."
)


def extract_fms_info(events):
    """Extract FMS match info from a list of event dicts.

    Scans event text for the FMS Connected line and Info records.
    Returns a dict with match_type, match_number, replay, field_time,
    ds_version, event_name — or None if no FMS data found.
    """
    fms_match = None
    event_name = None

    for event in events:
        text = event["text"]

        if fms_match is None:
            m = FMS_PATTERN.search(text)
            if m:
                fms_match = m

        if event_name is None:
            m = EVENT_NAME_PATTERN.search(text)
            if m:
                event_name = m.group(1)

        if fms_match and event_name:
            break

    if fms_match is None:
        return None

    return {
        "match_type": fms_match.group(1),
        "match_number": int(fms_match.group(2)),
        "replay": int(fms_match.group(3)),
        "field_time": fms_match.group(4).strip(),
        "ds_version": fms_match.group(5).strip(),
        "event_name": event_name,
    }


def extract_joystick_info(events):
    """Extract joystick configuration from event records.

    Returns a list of dicts with number, name, axes, buttons, povs.
    Deduplicates by joystick number (keeps first occurrence).
    """
    seen = set()
    joysticks = []

    for event in events:
        for m in JOYSTICK_PATTERN.finditer(event["text"]):
            num = int(m.group(1))
            if num not in seen:
                seen.add(num)
                joysticks.append({
                    "number": num,
                    "name": m.group(2),
                    "axes": int(m.group(3)),
                    "buttons": int(m.group(4)),
                    "povs": int(m.group(5)),
                })

    joysticks.sort(key=lambda j: j["number"])
    return joysticks


def build_match_key(match_type, match_number, replay):
    """Build the grouping key from match info (e.g., 'Qualification - 52:1')."""
    return f"{match_type} - {match_number}:{replay}"


def build_match_id(match_type, match_number, replay):
    """Build the file prefix match ID (e.g., 'Q52', 'E6_R1')."""
    if match_type == "Qualification":
        base = f"Q{match_number}"
        if replay > 1:
            base += f"_R{replay}"
        return base
    elif match_type == "Elimination":
        return f"E{match_number}_R{replay}"
    else:
        return f"{match_type}{match_number}"


def is_real_match(fms_info):
    """Return True if the FMS info represents a real match (not None or absent)."""
    if fms_info is None:
        return False
    return fms_info["match_type"] != "None"


def group_files_by_match(file_infos):
    """Group file info dicts by match key. Sort each group by header timestamp.

    Args:
        file_infos: list of dicts with keys: path, fms_info, header_timestamp

    Returns:
        dict mapping match_key -> list of file_info dicts, sorted by timestamp
    """
    groups = {}
    for fi in file_infos:
        key = build_match_key(
            fi["fms_info"]["match_type"],
            fi["fms_info"]["match_number"],
            fi["fms_info"]["replay"],
        )
        groups.setdefault(key, []).append(fi)

    for key in groups:
        groups[key].sort(key=lambda fi: fi["header_timestamp"])

    return groups
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_match_identifier.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```
feat: add match identifier with FMS parsing, match ID construction, and grouping
```

Files: `match_identifier.py`, `tests/test_match_identifier.py`

---

## Task 3: Event Formatter — Filtering, Tagged Event Parsing, Repeat Collapsing

**Files:**
- Create: `event_formatter.py`
- Create: `tests/test_event_formatter.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_event_formatter.py`:

```python
def test_parse_tagged_event_message():
    from event_formatter import parse_tagged_events
    text = "<TagVersion>1 <time> 00.169 <message> CS: USB Camera 0: Attempting to connect to USB camera on /dev/video0 "
    events = parse_tagged_events(text)
    assert len(events) == 1
    assert events[0]["time"] == "00.169"
    assert "USB Camera 0" in events[0]["display"]


def test_parse_tagged_event_coded():
    from event_formatter import parse_tagged_events
    text = ("<TagVersion>1 <time> 00.000 <count> 1 <flags> 2 <Code> 44000 "
            "<details> Driver Station not keeping up with protocol rates "
            "<location> Driver Station <stack> ")
    events = parse_tagged_events(text)
    assert len(events) == 1
    assert events[0]["flags"] == 2
    assert events[0]["code"] == 44000
    assert "ERROR (44000)" in events[0]["display"]


def test_parse_tagged_event_multiple_in_one_record():
    from event_formatter import parse_tagged_events
    text = ("<TagVersion>1 <time> 00.100 <message> First message "
            "<TagVersion>1 <time> 00.200 <message> Second message ")
    events = parse_tagged_events(text)
    assert len(events) == 2
    assert "First message" in events[0]["display"]
    assert "Second message" in events[1]["display"]


def test_format_plain_event_fms_connected():
    from event_formatter import format_plain_event
    text = "FMS Connected:   Qualification - 52:1, Field Time: 26/3/29 13:35:4\n -- FRC Driver Station - Version 26.0"
    result = format_plain_event(text)
    assert result is not None
    assert result["display"] == "FMS Connected"


def test_format_plain_event_code_start():
    from event_formatter import format_plain_event
    text = "Code Start Notification. "
    result = format_plain_event(text)
    assert result is not None
    assert result["display"] == "Code Start Notification"


def test_should_exclude_periodic_trace():
    from event_formatter import should_exclude
    assert should_exclude("disabledPeriodic(): 0.000075s") is True
    assert should_exclude("robotPeriodic(): 0.017270s") is True
    assert should_exclude("Shuffleboard.update(): 0.006733s") is True
    assert should_exclude("LiveWindow.updateValues(): 0.000000s") is True
    assert should_exclude("SmartDashboard.updateValues(): 0.000816s") is True


def test_should_not_exclude_real_events():
    from event_formatter import should_exclude
    assert should_exclude("FMS Connected") is False
    assert should_exclude("WARNING (44000): Driver Station not keeping up") is False


def test_collapse_repeats_no_repeats():
    from event_formatter import collapse_repeats
    events = [
        {"time": "00.000", "display": "Event A"},
        {"time": "01.000", "display": "Event B"},
    ]
    result = collapse_repeats(events)
    assert len(result) == 2


def test_collapse_repeats_two_consecutive():
    from event_formatter import collapse_repeats
    events = [
        {"time": "00.000", "display": "Same event"},
        {"time": "01.000", "display": "Same event"},
    ]
    result = collapse_repeats(events)
    assert len(result) == 2
    assert "(repeated 1x)" not in result[0]["display"]
    assert "(repeated 1x)" in result[1]["display"]


def test_collapse_repeats_six_consecutive():
    from event_formatter import collapse_repeats
    events = [{"time": f"0{i}.000", "display": "Repeated msg"} for i in range(6)]
    result = collapse_repeats(events)
    assert len(result) == 2  # first + last
    assert "(repeated 5x)" in result[1]["display"]


def test_collapse_repeats_mixed():
    from event_formatter import collapse_repeats
    events = [
        {"time": "00.000", "display": "A"},
        {"time": "01.000", "display": "B"},
        {"time": "02.000", "display": "B"},
        {"time": "03.000", "display": "B"},
        {"time": "04.000", "display": "C"},
    ]
    result = collapse_repeats(events)
    assert len(result) == 4  # A, B (first), B (repeated 2x), C
    assert result[0]["display"] == "A"
    assert "(repeated" not in result[1]["display"]
    assert "(repeated 2x)" in result[2]["display"]
    assert result[3]["display"] == "C"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_event_formatter.py -v`
Expected: FAIL — `event_formatter` module not found

- [ ] **Step 3: Implement event formatter**

Create `event_formatter.py`:

```python
"""Filter, format, and collapse .dsevents event records for display."""

import re

# Pattern to split multiple <TagVersion> entries in one text payload
TAG_SPLIT_PATTERN = re.compile(r"(?=<TagVersion>)")

# Parse a tagged message event
TAG_MESSAGE_PATTERN = re.compile(
    r"<TagVersion>\d+\s+<time>\s*([-\d.]+)\s+<message>\s*(.*)"
)

# Parse a tagged coded event
TAG_CODED_PATTERN = re.compile(
    r"<TagVersion>\d+\s+<time>\s*([-\d.]+)\s+"
    r"<count>\s*(\d+)\s+<flags>\s*(\d+)\s+<Code>\s*(\d+)\s+"
    r"<details>\s*(.*?)\s*<location>\s*(.*?)\s*<stack>\s*(.*)"
)

# Patterns for events to exclude
EXCLUDE_PATTERNS = [
    re.compile(r"disabledPeriodic\(\):"),
    re.compile(r"robotPeriodic\(\):"),
    re.compile(r"Shuffleboard\.update\(\):"),
    re.compile(r"LiveWindow\.updateValues\(\):"),
    re.compile(r"SmartDashboard\.updateValues\(\):"),
    re.compile(r"autonomousPeriodic\(\):"),
    re.compile(r"teleopPeriodic\(\):"),
]

# Plain text events we want to include
PLAIN_EVENTS = {
    "FMS Connected": re.compile(r"^FMS Connected:"),
    "FMS Disconnected": re.compile(r"^FMS Disconnected"),
    "Code Start Notification": re.compile(r"^Code Start Notification"),
}


def should_exclude(display_text):
    """Return True if the event display text matches an exclude pattern."""
    for pattern in EXCLUDE_PATTERNS:
        if pattern.search(display_text):
            return True
    return False


def should_include_tagged(flags, code, details, message):
    """Return True if a tagged event should be included in output."""
    # Warnings (flags=1) and errors (flags=2)
    if flags >= 1:
        return True
    # Non-zero code
    if code != 0:
        return True
    # Phoenix Signal Logger
    if details and details.strip().startswith("[phoenix] Signal Logger"):
        return True
    # PhotonVision
    text = (details or "") + (message or "")
    if "PhotonVision" in text or "org.photonvision" in text:
        return True
    # Robot mode transitions
    if message and ("Robot is now" in message):
        return True
    # Warning/Error messages from WPILib (e.g., "Warning at ...", "Error at ...")
    if message and (message.startswith("Warning at") or message.startswith("Error at")):
        return True
    return False


def format_plain_event(text, relative_time="00.000"):
    """Try to format a plain text event. Returns dict or None if not a known plain event.

    Args:
        text: event text string
        relative_time: time string relative to log file start (e.g., "05.123")
    """
    for display_name, pattern in PLAIN_EVENTS.items():
        if pattern.search(text):
            return {"time": relative_time, "display": display_name}
    return None


def parse_tagged_events(text):
    """Parse tagged events from a text payload.

    A single payload may contain multiple <TagVersion> entries.
    Returns a list of formatted event dicts.
    """
    parts = TAG_SPLIT_PATTERN.split(text)
    results = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Try coded event first (more specific)
        m = TAG_CODED_PATTERN.match(part)
        if m:
            time_str = m.group(1)
            flags = int(m.group(3))
            code = int(m.group(4))
            details = m.group(5).strip()
            location = m.group(6).strip()

            if not should_include_tagged(flags, code, details, None):
                continue
            if should_exclude(details):
                continue

            if flags == 2:
                prefix = "ERROR"
            elif flags == 1:
                prefix = "WARNING"
            else:
                prefix = "INFO"

            if code != 0:
                display = f"{prefix} ({code}): {details}"
            else:
                display = details

            results.append({"time": time_str, "display": display, "flags": flags, "code": code})
            continue

        # Try message event
        m = TAG_MESSAGE_PATTERN.match(part)
        if m:
            time_str = m.group(1)
            message = m.group(2).strip()

            if should_exclude(message):
                continue
            if not should_include_tagged(0, 0, None, message):
                continue

            results.append({"time": time_str, "display": message, "flags": 0, "code": 0})

    return results


def format_events(parsed_data):
    """Process all events from a parsed .dsevents file into display-ready list.

    Returns list of dicts with 'time' and 'display' keys.
    """
    formatted = []
    header_ts = parsed_data["header"]["timestamp"]

    for event in parsed_data["events"]:
        text = event["text"]

        # Compute relative time from file start
        rel_seconds = event["timestamp"] - header_ts
        rel_time = f"{abs(rel_seconds):06.3f}"
        if rel_seconds < 0:
            rel_time = f"-{rel_time}"

        # Try plain text events
        plain = format_plain_event(text, rel_time)
        if plain is not None:
            formatted.append(plain)
            continue

        # Try tagged events
        if "<TagVersion>" in text:
            tagged = parse_tagged_events(text)
            formatted.extend(tagged)

    return formatted


def collapse_repeats(events):
    """Collapse consecutive identical display messages.

    If N consecutive events have the same display text (N >= 2):
    - Show the 1st normally
    - Suppress 2nd through (N-1)th
    - Show the Nth with '(repeated {N-1}x)' appended
    """
    if not events:
        return []

    result = []
    i = 0

    while i < len(events):
        # Count consecutive identical messages
        j = i + 1
        while j < len(events) and events[j]["display"] == events[i]["display"]:
            j += 1

        count = j - i

        if count == 1:
            result.append(events[i])
        else:
            # First occurrence
            result.append(events[i])
            # Last occurrence with repeat count
            last = dict(events[j - 1])  # copy
            last["display"] = f"{last['display']} (repeated {count - 1}x)"
            result.append(last)

        i = j

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_event_formatter.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```
feat: add event formatter with filtering, tagged event parsing, and repeat collapsing
```

Files: `event_formatter.py`, `tests/test_event_formatter.py`

---

## Task 4: Match Writer — Generate match_events.txt and Copy Files

**Files:**
- Create: `match_writer.py`
- Create: `tests/test_match_writer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_match_writer.py`:

```python
import os

from conftest import make_dsevents_file


def test_format_match_events_header():
    from match_writer import format_match_events_txt
    fms_info = {
        "match_type": "Qualification",
        "match_number": 52,
        "replay": 1,
        "field_time": "26/3/29 13:35:4",
        "ds_version": "FRC Driver Station - Version 26.0",
        "event_name": "NCPEM",
    }
    match_id = "Q52"
    log_files = [{"seq": 1, "basename": "2026_03_29 09_34_29 Sun"}]
    events_by_log = {1: [{"time": "00.000", "display": "FMS Connected"}]}
    joysticks = [{"number": 0, "name": "Controller (Xbox One For Windows)", "axes": 6, "buttons": 16, "povs": 1}]

    txt = format_match_events_txt(fms_info, match_id, log_files, events_by_log, joysticks)

    assert "Match: Qualification 52" in txt
    assert "Event: NCPEM" in txt
    assert "Field Time: 26/3/29 13:35:4" in txt
    assert "DS Version: FRC Driver Station - Version 26.0" in txt
    assert "Replay: 1" in txt
    assert "[1] 2026_03_29 09_34_29 Sun (Q52_1_)" in txt
    assert "[1] 00.000  FMS Connected" in txt
    assert "0: Controller (Xbox One For Windows) - 6 axes, 16 buttons, 1 POV" in txt


def test_format_match_events_multi_log():
    from match_writer import format_match_events_txt
    fms_info = {
        "match_type": "Qualification",
        "match_number": 60,
        "replay": 1,
        "field_time": "26/3/29 14:00:0",
        "ds_version": "FRC Driver Station - Version 26.0",
        "event_name": "NCPEM",
    }
    match_id = "Q60"
    log_files = [
        {"seq": 1, "basename": "2026_03_29 09_34_29 Sun"},
        {"seq": 2, "basename": "2026_03_29 09_40_12 Sun"},
    ]
    events_by_log = {
        1: [{"time": "00.000", "display": "FMS Connected"}],
        2: [{"time": "00.000", "display": "FMS Connected"}],
    }
    joysticks = []

    txt = format_match_events_txt(fms_info, match_id, log_files, events_by_log, joysticks)

    assert "[1]" in txt
    assert "[2]" in txt
    assert "Q60_1_" in txt
    assert "Q60_2_" in txt


def test_copy_match_files(tmp_dirs):
    src, dst = tmp_dirs

    # Create source files
    dsevents_data = make_dsevents_file(["test event"])
    dsevents_path = src / "2026_03_29 09_34_29 Sun.dsevents"
    dsevents_path.write_bytes(dsevents_data)
    dslog_path = src / "2026_03_29 09_34_29 Sun.dslog"
    dslog_path.write_bytes(b"\x00" * 100)

    from match_writer import copy_match_files
    file_entries = [{"seq": 1, "basename": "2026_03_29 09_34_29 Sun", "dsevents_path": str(dsevents_path)}]
    copy_match_files("Q52", file_entries, str(src), str(dst))

    assert (dst / "Q52_1_2026_03_29 09_34_29 Sun.dsevents").exists()
    assert (dst / "Q52_1_2026_03_29 09_34_29 Sun.dslog").exists()


def test_write_match_events_file(tmp_dirs):
    _, dst = tmp_dirs

    from match_writer import write_match_events_file
    write_match_events_file(str(dst), "Q52", "Match: Qualification 52\n...")

    path = dst / "Q52_match_events.txt"
    assert path.exists()
    assert "Qualification 52" in path.read_text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_match_writer.py -v`
Expected: FAIL — `match_writer` module not found

- [ ] **Step 3: Implement match writer**

Create `match_writer.py`:

```python
"""Write match_events.txt files and copy log file pairs to destination."""

import os
import shutil


def format_match_events_txt(fms_info, match_id, log_files, events_by_log, joysticks):
    """Generate the full match_events.txt content as a string.

    Args:
        fms_info: dict with match_type, match_number, replay, field_time, ds_version, event_name
        match_id: str like 'Q52' or 'E6_R1'
        log_files: list of dicts with seq and basename
        events_by_log: dict mapping seq number -> list of event dicts (time, display)
        joysticks: list of joystick dicts (number, name, axes, buttons, povs)
    """
    lines = []

    # Header
    lines.append(f"Match: {fms_info['match_type']} {fms_info['match_number']}")
    lines.append(f"Event: {fms_info.get('event_name', 'Unknown')}")
    lines.append(f"Field Time: {fms_info['field_time']}")
    lines.append(f"DS Version: {fms_info['ds_version']}")
    lines.append(f"Replay: {fms_info['replay']}")
    lines.append("")

    # Log files
    lines.append("Log Files:")
    for lf in log_files:
        lines.append(f"  [{lf['seq']}] {lf['basename']} ({match_id}_{lf['seq']}_)")
    lines.append("")

    # Events
    lines.append("Events:")
    for lf in log_files:
        seq = lf["seq"]
        for event in events_by_log.get(seq, []):
            lines.append(f"  [{seq}] {event['time']}  {event['display']}")
    lines.append("")

    # Joysticks
    lines.append("Joysticks:")
    for j in joysticks:
        lines.append(f"  {j['number']}: {j['name']} - {j['axes']} axes, {j['buttons']} buttons, {j['povs']} POV")
    lines.append("")

    return "\n".join(lines)


def copy_match_files(match_id, file_entries, source_dir, dest_dir):
    """Copy .dsevents and .dslog file pairs to destination with match prefix.

    Args:
        match_id: str like 'Q52'
        file_entries: list of dicts with seq, basename, dsevents_path
        source_dir: source directory path
        dest_dir: destination directory path
    """
    for entry in file_entries:
        seq = entry["seq"]
        basename = entry["basename"]
        prefix = f"{match_id}_{seq}_"

        for ext in (".dsevents", ".dslog"):
            src_path = os.path.join(source_dir, basename + ext)
            dst_path = os.path.join(dest_dir, prefix + basename + ext)
            if os.path.exists(src_path):
                shutil.copy2(src_path, dst_path)


def write_match_events_file(dest_dir, match_id, content):
    """Write the match_events.txt file to the destination directory."""
    path = os.path.join(dest_dir, f"{match_id}_match_events.txt")
    with open(path, "w") as f:
        f.write(content)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_match_writer.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```
feat: add match writer for generating match_events.txt and copying file pairs
```

Files: `match_writer.py`, `tests/test_match_writer.py`

---

## Task 5: CLI Entry Point — Scanning, Filtering, Confirmation, Orchestration

**Files:**
- Create: `process_matches.py`
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write failing integration tests**

Create `tests/test_integration.py`:

```python
import os
import subprocess
import sys

from conftest import make_dsevents_file


def test_scan_finds_match_files(tmp_dirs):
    src, dst = tmp_dirs

    # Create a match dsevents + dslog pair
    match_data = make_dsevents_file([
        "\x00#Info 26.0Info FMS Event Name: NCPEM",
        "nInfo Joystick 0: (Controller (Xbox One For Windows))6 axes, 16 buttons, 1 POVs. ",
        "hFMS Connected:   Qualification - 52:1, Field Time: 26/3/29 13:35:4\n"
        " -- FRC Driver Station - Version 26.0",
        "Code Start Notification. ",
    ])
    (src / "2026_03_29 09_34_29 Sun.dsevents").write_bytes(match_data)
    (src / "2026_03_29 09_34_29 Sun.dslog").write_bytes(b"\x00" * 100)

    # Create a non-match dsevents + dslog pair
    nonmatch_data = make_dsevents_file([
        "hFMS Connected:   None - 0:0, Field Time: -100/0/0 0:0:0\n"
        " -- FRC Driver Station - Version 26.0",
    ])
    (src / "2026_03_29 10_00_00 Sun.dsevents").write_bytes(nonmatch_data)
    (src / "2026_03_29 10_00_00 Sun.dslog").write_bytes(b"\x00" * 100)

    from process_matches import scan_and_identify
    matches = scan_and_identify(str(src), str(dst))
    assert len(matches) == 1
    key = list(matches.keys())[0]
    assert "Qualification" in key


def test_skip_existing_matches(tmp_dirs):
    src, dst = tmp_dirs

    match_data = make_dsevents_file([
        "hFMS Connected:   Qualification - 52:1, Field Time: 26/3/29 13:35:4\n"
        " -- FRC Driver Station - Version 26.0",
    ])
    (src / "2026_03_29 09_34_29 Sun.dsevents").write_bytes(match_data)
    (src / "2026_03_29 09_34_29 Sun.dslog").write_bytes(b"\x00" * 100)

    # Pre-populate destination with Q52_ files
    (dst / "Q52_match_events.txt").write_text("existing")

    from process_matches import scan_and_identify
    matches = scan_and_identify(str(src), str(dst))
    assert len(matches) == 0


def test_date_filter(tmp_dirs):
    src, dst = tmp_dirs

    match_data = make_dsevents_file([
        "hFMS Connected:   Qualification - 52:1, Field Time: 26/3/29 13:35:4\n"
        " -- FRC Driver Station - Version 26.0",
    ])
    (src / "2026_03_29 09_34_29 Sun.dsevents").write_bytes(match_data)
    (src / "2026_03_29 09_34_29 Sun.dslog").write_bytes(b"\x00" * 100)

    (src / "2026_03_28 09_34_29 Sat.dsevents").write_bytes(match_data)
    (src / "2026_03_28 09_34_29 Sat.dslog").write_bytes(b"\x00" * 100)

    from process_matches import scan_and_identify
    matches = scan_and_identify(str(src), str(dst), date_filter="2026_03_29")
    assert len(matches) == 1


def test_cli_help():
    result = subprocess.run(
        [sys.executable, "process_matches.py", "--help"],
        capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(__file__)) or "."
    )
    assert result.returncode == 0
    assert "source_dir" in result.stdout
    assert "dest_dir" in result.stdout


def test_end_to_end_with_real_files(tmp_path):
    """Integration test using real .dsevents files from the repo."""
    dst = tmp_path / "dest"
    dst.mkdir()

    from process_matches import scan_and_identify
    matches = scan_and_identify("2026/03", str(dst))

    # Should find multiple real matches
    assert len(matches) > 0
    # All keys should be real match types
    for key in matches:
        assert "Qualification" in key or "Elimination" in key
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_integration.py -v`
Expected: FAIL — `process_matches` module not found

- [ ] **Step 3: Implement the CLI entry point**

Create `process_matches.py`:

```python
#!/usr/bin/env python3
"""FRC Match Log Processor — identify match log files and organize them."""

import argparse
import os
import re
import sys
from datetime import date

from dsevents_parser import parse_dsevents_path
from match_identifier import (
    extract_fms_info,
    extract_joystick_info,
    build_match_id,
    build_match_key,
    is_real_match,
    group_files_by_match,
)
from event_formatter import format_events, collapse_repeats
from match_writer import (
    format_match_events_txt,
    copy_match_files,
    write_match_events_file,
)


def get_date_filter(args):
    """Return date filter string as YYYY_MM_DD or None."""
    if args.today:
        return date.today().strftime("%Y_%m_%d")
    elif args.date:
        # Convert YYYY-MM-DD to YYYY_MM_DD
        return args.date.replace("-", "_")
    return None


def find_dsevents_files(source_dir, date_filter=None):
    """Find all .dsevents files in source_dir, optionally filtered by date."""
    files = []
    for name in os.listdir(source_dir):
        if not name.endswith(".dsevents"):
            continue
        if date_filter and not name.startswith(date_filter):
            continue
        files.append(os.path.join(source_dir, name))
    return sorted(files)


def get_existing_match_prefixes(dest_dir):
    """Return set of match prefixes already in dest_dir.

    Checks for any file starting with a match prefix pattern (Q<n>_, E<n>_R<n>_).
    """
    prefixes = set()
    prefix_pattern = re.compile(r"^(Q\d+(?:_R\d+)?|E\d+_R\d+)_")
    for name in os.listdir(dest_dir):
        m = prefix_pattern.match(name)
        if m:
            prefixes.add(m.group(1))
    return prefixes


def has_dslog_pair(dsevents_path):
    """Check if a matching .dslog file exists for this .dsevents file."""
    base = dsevents_path.rsplit(".dsevents", 1)[0]
    return os.path.exists(base + ".dslog")


def scan_and_identify(source_dir, dest_dir, date_filter=None):
    """Scan source for match files, filter, group, and remove already-processed.

    Returns dict mapping match_key -> list of file info dicts.
    """
    dsevents_files = find_dsevents_files(source_dir, date_filter)

    if not dsevents_files:
        return {}

    # Parse all files and extract match info
    file_infos = []
    for path in dsevents_files:
        if not has_dslog_pair(path):
            print(f"  Warning: No .dslog pair for {os.path.basename(path)}, skipping.")
            continue

        try:
            parsed = parse_dsevents_path(path)
        except Exception as e:
            print(f"  Warning: Could not parse {os.path.basename(path)}: {e}")
            continue

        fms_info = extract_fms_info(parsed["events"])
        if not is_real_match(fms_info):
            continue

        file_infos.append({
            "path": path,
            "fms_info": fms_info,
            "header_timestamp": parsed["header"]["timestamp"],
            "parsed": parsed,
        })

    if not file_infos:
        return {}

    # Group by match
    groups = group_files_by_match(file_infos)

    # Remove already-processed matches
    existing = get_existing_match_prefixes(dest_dir)
    filtered = {}
    for key, files in groups.items():
        fms = files[0]["fms_info"]
        match_id = build_match_id(fms["match_type"], fms["match_number"], fms["replay"])
        if match_id not in existing:
            filtered[key] = files

    return filtered


def display_matches(matches):
    """Display found matches and return match_id mapping."""
    print("\nNew matches found:")
    match_ids = {}
    for key, files in sorted(matches.items()):
        fms = files[0]["fms_info"]
        match_id = build_match_id(fms["match_type"], fms["match_number"], fms["replay"])
        match_ids[key] = match_id
        pair_count = len(files)
        desc = f"{fms['match_type']} {fms['match_number']}"
        if fms["match_type"] == "Elimination":
            desc += f" Replay {fms['replay']}"
        if pair_count > 1:
            pairs = f"{pair_count} log pairs \u2014 robot restart detected"
        else:
            pairs = "1 log pair"
        print(f"  {match_id:<8} - {desc} ({pairs})")
    return match_ids


def process_match(key, files, match_id, source_dir, dest_dir):
    """Process a single match: parse events, write summary, copy files."""
    fms_info = files[0]["fms_info"]

    # Build log file entries with sequence numbers
    log_entries = []
    events_by_log = {}

    for seq, fi in enumerate(files, start=1):
        basename = os.path.splitext(os.path.basename(fi["path"]))[0]
        log_entries.append({
            "seq": seq,
            "basename": basename,
            "dsevents_path": fi["path"],
        })

        # Format and collapse events
        formatted = format_events(fi["parsed"])
        collapsed = collapse_repeats(formatted)
        events_by_log[seq] = collapsed

    # Extract joystick info from first log file
    joysticks = extract_joystick_info(files[0]["parsed"]["events"])

    # Generate match_events.txt
    txt = format_match_events_txt(fms_info, match_id, log_entries, events_by_log, joysticks)

    # Write files
    write_match_events_file(dest_dir, match_id, txt)
    copy_match_files(match_id, log_entries, source_dir, dest_dir)

    print(f"  {match_id}: wrote {match_id}_match_events.txt + {len(log_entries)} log pair(s)")


def main():
    parser = argparse.ArgumentParser(
        description="FRC Match Log Processor — identify match .dsevents/.dslog files "
                    "and organize them into an event folder."
    )
    parser.add_argument("source_dir", help="Directory containing .dsevents and .dslog files")
    parser.add_argument("dest_dir", help="Destination directory for organized match files")

    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument("--today", action="store_true",
                            help="Only scan files from today's date")
    date_group.add_argument("--date", metavar="YYYY-MM-DD",
                            help="Only scan files from the specified date")

    args = parser.parse_args()

    # Validate directories
    if not os.path.isdir(args.source_dir):
        print(f"Error: Source directory does not exist: {args.source_dir}")
        sys.exit(1)
    if not os.path.isdir(args.dest_dir):
        print(f"Error: Destination directory does not exist: {args.dest_dir}")
        sys.exit(1)

    date_filter = get_date_filter(args)

    print(f"Scanning {args.source_dir} for match files...")

    # Check for .dsevents files first (distinct message per spec)
    dsevents_files = find_dsevents_files(args.source_dir, date_filter)
    if not dsevents_files:
        print("No .dsevents files found.")
        sys.exit(0)

    matches = scan_and_identify(args.source_dir, args.dest_dir, date_filter)

    if not matches:
        print("No new matches found.")
        sys.exit(0)

    match_ids = display_matches(matches)

    # Confirm
    response = input("\nProcess these matches? [Y/n] ").strip().lower()
    if response and response != "y":
        print("Aborted.")
        sys.exit(0)

    # Process
    print()
    for key, files in sorted(matches.items()):
        process_match(key, files, match_ids[key], args.source_dir, args.dest_dir)

    print("\nDone.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_integration.py -v`
Expected: All PASS

- [ ] **Step 5: Run the tool against real data as a smoke test**

Run: `echo "n" | uv run python process_matches.py 2026/03/ 2026/UNCPembroke/`

Expected: Should list new matches found, then abort when we answer "n". Verify the match list looks correct (should show Qualification and Elimination matches, should NOT show Q52 since it's already in UNCPembroke).

- [ ] **Step 6: Commit**

```
feat: add CLI entry point with scanning, date filtering, confirmation, and orchestration
```

Files: `process_matches.py`, `tests/test_integration.py`

---

## Task 6: Integration Testing with Real Files and Edge Cases

**Files:**
- Modify: `tests/test_integration.py`

- [ ] **Step 1: Add edge case tests**

Append to `tests/test_integration.py`:

```python
def test_missing_dslog_warns(tmp_dirs, capsys):
    src, dst = tmp_dirs

    match_data = make_dsevents_file([
        "hFMS Connected:   Qualification - 99:1, Field Time: 26/3/29 13:35:4\n"
        " -- FRC Driver Station - Version 26.0",
    ])
    (src / "2026_03_29 12_00_00 Sun.dsevents").write_bytes(match_data)
    # Intentionally no .dslog file

    from process_matches import scan_and_identify
    matches = scan_and_identify(str(src), str(dst))
    assert len(matches) == 0

    captured = capsys.readouterr()
    assert "Warning" in captured.out
    assert "No .dslog pair" in captured.out


def test_restart_detection(tmp_dirs):
    src, dst = tmp_dirs

    # Two files for the same match (robot restart)
    match_data_1 = make_dsevents_file([
        "hFMS Connected:   Qualification - 60:1, Field Time: 26/3/29 14:00:0\n"
        " -- FRC Driver Station - Version 26.0",
    ], unix_timestamp=1000.0)
    match_data_2 = make_dsevents_file([
        "hFMS Connected:   Qualification - 60:1, Field Time: 26/3/29 14:00:0\n"
        " -- FRC Driver Station - Version 26.0",
    ], unix_timestamp=2000.0)

    (src / "2026_03_29 09_34_29 Sun.dsevents").write_bytes(match_data_1)
    (src / "2026_03_29 09_34_29 Sun.dslog").write_bytes(b"\x00" * 100)
    (src / "2026_03_29 09_40_12 Sun.dsevents").write_bytes(match_data_2)
    (src / "2026_03_29 09_40_12 Sun.dslog").write_bytes(b"\x00" * 100)

    from process_matches import scan_and_identify
    matches = scan_and_identify(str(src), str(dst))
    assert len(matches) == 1
    key = list(matches.keys())[0]
    assert len(matches[key]) == 2  # Two files grouped together


def test_nonstandard_filename_skipped_with_date_filter(tmp_dirs):
    src, dst = tmp_dirs

    match_data = make_dsevents_file([
        "hFMS Connected:   Qualification - 10:1, Field Time: 26/3/29 10:00:0\n"
        " -- FRC Driver Station - Version 26.0",
    ])
    (src / "weird_name.dsevents").write_bytes(match_data)
    (src / "weird_name.dslog").write_bytes(b"\x00" * 100)

    from process_matches import scan_and_identify
    matches = scan_and_identify(str(src), str(dst), date_filter="2026_03_29")
    assert len(matches) == 0
```

- [ ] **Step 2: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```
test: add edge case tests for missing dslog, restart detection, and date filtering
```

Files: `tests/test_integration.py`

---

## Task 7: README Update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README.md**

Add the following section after the existing content in `README.md`:

```markdown

## Match Log Processor

Process FRC Driver Station log files (`.dsevents` and `.dslog`) from competition matches.

### Usage

```bash
# Scan all files in source directory
python3 process_matches.py <source_dir> <dest_dir>

# Scan only today's files
python3 process_matches.py <source_dir> <dest_dir> --today

# Scan files for a specific date
python3 process_matches.py <source_dir> <dest_dir> --date 2026-03-29
```

### Example

```bash
python3 process_matches.py 2026/03/ 2026/UNCPembroke/
```

Output:
```
Scanning 2026/03/ for match files...

New matches found:
  Q6       - Qualification 6 (1 log pair)
  Q7       - Qualification 7 (1 log pair)
  Q10      - Qualification 10 (1 log pair)
  E3_R1    - Elimination 3 Replay 1 (1 log pair)

Process these matches? [Y/n]
```

The tool:
1. Identifies real FRC match files (skips practice/pit sessions)
2. Groups files from the same match (detects robot restarts)
3. Skips matches already in the destination folder
4. Copies `.dsevents` + `.dslog` pairs with match prefix (e.g., `Q52_1_`)
5. Writes a `match_events.txt` summary with key events for each match

### Requirements

- Python 3.14+ (via `uv run`)
- No external dependencies
```

- [ ] **Step 2: Commit**

```
docs: add Match Log Processor usage to README
```

Files: `README.md`

---

## Task 8: Final Validation

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All PASS

- [ ] **Step 2: End-to-end smoke test with real data**

Run: `echo "n" | uv run python process_matches.py 2026/03/ 2026/UNCPembroke/`

Verify output shows the expected matches (Qualification and Elimination), skips Q52 (already exists), and aborts cleanly.

- [ ] **Step 3: Process one match for real**

Run: `echo "y" | uv run python process_matches.py 2026/03/ 2026/UNCPembroke/ --date 2026-03-29`

Verify:
- Files are copied to `2026/UNCPembroke/` with correct prefixes
- `match_events.txt` files are created and readable
- Running the same command again shows "No new matches found."

- [ ] **Step 4: Review a generated match_events.txt**

Read one of the generated files and verify:
- Header has correct match info
- Events are filtered (no periodic traces)
- Repeat collapsing works
- Joystick info is formatted correctly

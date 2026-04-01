# dslog Transitions and Telemetry — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Also use the frc-log-reviewer skill (`.claude/skills/frc-log-review.md`) with its reference (`.claude/skills/references/frc-log-formats.md`) to validate all binary parsing code.

**Goal:** Parse `.dslog` binary files to extract robot mode transitions and telemetry summary, integrating them into the existing match output.

**Architecture:** Two new modules (`dslog_parser.py` for binary format, `dslog_processor.py` for transition detection and telemetry aggregation) feed into existing `match_writer.py` and `process_matches.py`. All binary parsing uses `struct` with big-endian format strings. The parser yields records lazily; the processor consumes them to produce transition events and telemetry stats.

**Tech Stack:** Python 3.14, struct, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-03-31-dslog-transitions-and-telemetry-design.md`

**Code review skill:** `.claude/skills/frc-log-review.md` — use for all binary parsing validation

---

## File Map

| File | Role | Change |
|------|------|--------|
| `match_processor/dslog_parser.py` | **Create** — dslog binary parser | Parse 20-byte header, iterate variable-length records, extract telemetry fields and status flags |
| `match_processor/dslog_processor.py` | **Create** — transition detection + telemetry summary | Debounced mode transitions, min/max telemetry computation |
| `match_processor/match_writer.py` | **Modify** — match output formatting | Add Telemetry section, reorder Joysticks before Events, merge transition events chronologically |
| `match_processor/process_matches.py` | **Modify** — CLI entry point | Parse dslog files alongside dsevents, pass dslog data to writer |
| `match_processor/tests/conftest.py` | **Modify** — shared test fixtures | Add dslog fixture helpers (`make_dslog_header`, `make_dslog_record`, `make_dslog_file`) |
| `match_processor/tests/test_dslog_parser.py` | **Create** — parser unit tests | Header parsing, record iteration, status mask, PD types, truncation |
| `match_processor/tests/test_dslog_processor.py` | **Create** — processor unit tests | Debounce logic, telemetry aggregation, edge cases |
| `match_processor/tests/test_match_writer.py` | **Modify** — writer tests | Update for new section order, telemetry section, transition events |
| `match_processor/tests/test_integration.py` | **Modify** — integration tests | End-to-end with real dslog data |

---

### Task 1: dslog Test Fixtures

**Files:**
- Modify: `match_processor/tests/conftest.py`

- [ ] **Step 1: Add dslog fixture helpers to conftest.py**

Add these helpers after the existing dsevents helpers:

```python
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
```

- [ ] **Step 2: Verify fixture helpers build valid binary**

Run: `uv run python3 -c "from match_processor.tests.conftest import make_dslog_file; d = make_dslog_file([{'voltage_raw': 3072}]); print(f'Header+1 REV record: {len(d)} bytes'); assert len(d) == 67"`

Expected: `Header+1 REV record: 67 bytes` (20 header + 47 record)

- [ ] **Step 3: Commit**

```
test: add dslog fixture helpers to conftest.py
```

---

### Task 2: dslog Parser — Header Parsing

**Files:**
- Create: `match_processor/dslog_parser.py`
- Create: `match_processor/tests/test_dslog_parser.py`

- [ ] **Step 1: Write failing tests for header parsing**

Create `match_processor/tests/test_dslog_parser.py`:

```python
import struct

from conftest import make_dslog_header, LABVIEW_EPOCH_OFFSET


def test_parse_header_valid():
    from dslog_parser import parse_dslog_header
    data = make_dslog_header(unix_timestamp=1774752353.0)
    result = parse_dslog_header(data)
    assert result["version"] == 4
    assert abs(result["timestamp"] - 1774752353.0) < 1.0


def test_parse_header_version_check():
    from dslog_parser import parse_dslog_header
    data = make_dslog_header(version=99)
    result = parse_dslog_header(data)
    assert result is None


def test_parse_header_truncated():
    from dslog_parser import parse_dslog_header
    result = parse_dslog_header(b"\x00" * 10)
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest match_processor/tests/test_dslog_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dslog_parser'`

- [ ] **Step 3: Implement header parsing**

Create `match_processor/dslog_parser.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest match_processor/tests/test_dslog_parser.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```
feat: add dslog header parsing with version validation
```

---

### Task 3: dslog Parser — Record Iteration

**Files:**
- Modify: `match_processor/dslog_parser.py`
- Modify: `match_processor/tests/test_dslog_parser.py`

- [ ] **Step 1: Write failing tests for record parsing**

Append to `test_dslog_parser.py`:

```python
from conftest import make_dslog_file


def test_parse_records_single_rev():
    from dslog_parser import parse_dslog_records
    # 12.0V, Disabled (status bit 0 = 0 → 0xFE), REV PDH
    data = make_dslog_file([{"voltage_raw": 3072, "status": 0xFE}])
    records = list(parse_dslog_records(data))
    assert len(records) == 1
    r = records[0]
    assert abs(r["voltage"] - 12.0) < 0.01
    assert r["mode"] == "Disabled"


def test_parse_records_autonomous():
    from dslog_parser import parse_dslog_records
    # Autonomous: bit 1 = 0 → 0xFD
    data = make_dslog_file([{"voltage_raw": 3200, "status": 0xFD}])
    records = list(parse_dslog_records(data))
    assert records[0]["mode"] == "Autonomous"


def test_parse_records_teleop():
    from dslog_parser import parse_dslog_records
    # Teleop: bit 2 = 0 → 0xFB
    data = make_dslog_file([{"voltage_raw": 3200, "status": 0xFB}])
    records = list(parse_dslog_records(data))
    assert records[0]["mode"] == "Teleop"


def test_parse_records_disconnected():
    from dslog_parser import parse_dslog_records
    # All bits set → Disconnected
    data = make_dslog_file([{"voltage_raw": 3200, "status": 0xFF}])
    records = list(parse_dslog_records(data))
    assert records[0]["mode"] == "Disconnected"


def test_parse_records_mode_priority():
    from dslog_parser import parse_dslog_records
    # Both Autonomous (bit 1=0) and Teleop (bit 2=0) clear → Autonomous wins
    data = make_dslog_file([{"voltage_raw": 3200, "status": 0xF9}])
    records = list(parse_dslog_records(data))
    assert records[0]["mode"] == "Autonomous"


def test_parse_records_ctre_pdp():
    from dslog_parser import parse_dslog_records
    data = make_dslog_file([{"voltage_raw": 3072, "status": 0xFE, "pd_type": 0x19}])
    records = list(parse_dslog_records(data))
    assert len(records) == 1


def test_parse_records_no_pd():
    from dslog_parser import parse_dslog_records
    data = make_dslog_file([{"voltage_raw": 3072, "status": 0xFE, "pd_type": 0x00}])
    records = list(parse_dslog_records(data))
    assert len(records) == 1


def test_parse_records_telemetry_fields():
    from dslog_parser import parse_dslog_records
    data = make_dslog_file([{
        "trip": 8,         # 8 × 0.5 = 4.0 ms
        "pkt_loss": 10,    # 10 × 4 × 0.01 = 0.40
        "voltage_raw": 3200,  # 3200 / 256 = 12.5 V
        "cpu": 100,        # 100 × 0.5 × 0.01 = 0.50
        "can": 74,         # 74 × 0.5 × 0.01 = 0.37
        "status": 0xFE,
    }])
    records = list(parse_dslog_records(data))
    r = records[0]
    assert abs(r["trip_ms"] - 4.0) < 0.01
    assert abs(r["packet_loss"] - 0.40) < 0.01
    assert abs(r["voltage"] - 12.5) < 0.01
    assert abs(r["cpu"] - 0.50) < 0.01
    assert abs(r["can"] - 0.37) < 0.01


def test_parse_records_truncated_mid_record():
    from dslog_parser import parse_dslog_records
    data = make_dslog_file([{"voltage_raw": 3072, "status": 0xFE}])
    # Truncate in the middle of the record
    truncated = data[:30]
    records = list(parse_dslog_records(truncated))
    assert len(records) == 0


def test_parse_records_unsupported_version():
    from dslog_parser import parse_dslog_records
    import struct
    data = struct.pack(">iqQ", 99, 0, 0)  # bad version
    records = list(parse_dslog_records(data))
    assert len(records) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest match_processor/tests/test_dslog_parser.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_dslog_records'`

- [ ] **Step 3: Implement record iteration**

Append to `match_processor/dslog_parser.py`:

```python
def _decode_mode(status):
    """Determine robot mode from inverted status mask.

    Priority: Autonomous > Teleop > Disabled > Disconnected.
    Bits are inverted: 0 = active.
    """
    if not (status & 0x02):  # bit 1 — Robot Autonomous
        return "Autonomous"
    if not (status & 0x04):  # bit 2 — Robot Teleop
        return "Teleop"
    if not (status & 0x01):  # bit 0 — Robot Disabled
        return "Disabled"
    return "Disconnected"


def parse_dslog_records(data):
    """Parse dslog file and yield record dicts.

    Each record dict contains: index, voltage, cpu, can, trip_ms, packet_loss, mode.
    Yields nothing if header is invalid. Stops on truncated or unknown-PD records.
    """
    header = parse_dslog_header(data)
    if header is None:
        return

    offset = HEADER_SIZE
    index = 0

    while offset + FIXED_SIZE + PD_HEADER_SIZE <= len(data):
        trip, pkt_loss, voltage_raw, cpu, status, can, wifi_sig, wifi_bw = (
            struct.unpack_from(FIXED_FORMAT, data, offset)
        )

        pd_type = data[offset + FIXED_SIZE + 3]
        pd_extra = PD_SIZES.get(pd_type, None)

        # Unknown PD type: can't determine record size, stop
        if pd_extra is None and pd_type not in (0x00,):
            print(f"  Warning: unknown dslog PD type 0x{pd_type:02x} at record {index}, stopping.")
            return
        if pd_extra is None:
            pd_extra = 0

        record_size = FIXED_SIZE + PD_HEADER_SIZE + pd_extra
        if offset + record_size > len(data):
            break  # truncated final record

        yield {
            "index": index,
            "voltage": voltage_raw / 256,
            "cpu": cpu * 0.5 * 0.01,
            "can": can * 0.5 * 0.01,
            "trip_ms": trip * 0.5,
            "packet_loss": max(0.0, min(1.0, pkt_loss * 4 * 0.01)),
            "mode": _decode_mode(status),
        }

        offset += record_size
        index += 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest match_processor/tests/test_dslog_parser.py -v`
Expected: 14 passed

- [ ] **Step 5: Commit**

```
feat: add dslog record iteration with mode detection and telemetry fields
```

---

### Task 4: dslog Parser — File Path Helper

**Files:**
- Modify: `match_processor/dslog_parser.py`
- Modify: `match_processor/tests/test_dslog_parser.py`

- [ ] **Step 1: Write failing test for path-based parsing**

Append to `test_dslog_parser.py`:

```python
def test_parse_dslog_path(tmp_path):
    from dslog_parser import parse_dslog_path
    data = make_dslog_file([
        {"voltage_raw": 3072, "status": 0xFE},
        {"voltage_raw": 3200, "status": 0xFD},
    ])
    path = tmp_path / "test.dslog"
    path.write_bytes(data)
    result = parse_dslog_path(str(path))
    assert result["header"]["version"] == 4
    assert len(result["records"]) == 2
    assert result["records"][0]["mode"] == "Disabled"
    assert result["records"][1]["mode"] == "Autonomous"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest match_processor/tests/test_dslog_parser.py::test_parse_dslog_path -v`
Expected: FAIL

- [ ] **Step 3: Implement path helper**

Append to `match_processor/dslog_parser.py`:

```python
def parse_dslog_path(filepath):
    """Parse a .dslog file from a file path.

    Returns dict with 'header' and 'records' keys.
    Returns dict with None header and empty records if file is invalid.
    """
    with open(filepath, "rb") as f:
        data = f.read()

    header = parse_dslog_header(data)
    records = list(parse_dslog_records(data))

    return {"header": header, "records": records}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest match_processor/tests/test_dslog_parser.py -v`
Expected: 15 passed

- [ ] **Step 5: Commit**

```
feat: add parse_dslog_path file helper
```

---

### Task 5: dslog Processor — Transition Detection

**Files:**
- Create: `match_processor/dslog_processor.py`
- Create: `match_processor/tests/test_dslog_processor.py`

- [ ] **Step 1: Write failing tests for transition detection**

Create `match_processor/tests/test_dslog_processor.py`:

```python
from conftest import make_dslog_file


def test_no_transitions_single_mode():
    from dslog_processor import detect_transitions
    # 10 records, all Disabled (0xFE)
    records_args = [{"voltage_raw": 3072, "status": 0xFE}] * 10
    data = make_dslog_file(records_args)

    from dslog_parser import parse_dslog_records
    records = list(parse_dslog_records(data))
    transitions = detect_transitions(records)
    # Initial mode counts as first transition
    assert len(transitions) == 1
    assert transitions[0]["mode"] == "Disabled"
    assert transitions[0]["time"] == "000.000"


def test_transition_after_debounce():
    from dslog_processor import detect_transitions
    # 5 Disabled, then 5 Autonomous (exactly at debounce threshold)
    records_args = (
        [{"voltage_raw": 3072, "status": 0xFE}] * 5 +
        [{"voltage_raw": 3072, "status": 0xFD}] * 5
    )
    data = make_dslog_file(records_args)

    from dslog_parser import parse_dslog_records
    records = list(parse_dslog_records(data))
    transitions = detect_transitions(records)
    assert len(transitions) == 2
    assert transitions[0]["mode"] == "Disabled"
    assert transitions[1]["mode"] == "Autonomous"
    # Timestamp of transition = first record in new mode = record 5 = 0.100s
    assert transitions[1]["time"] == "000.100"


def test_transition_not_confirmed_under_threshold():
    from dslog_processor import detect_transitions
    # 5 Disabled, 4 Autonomous (not enough), back to Disabled
    records_args = (
        [{"voltage_raw": 3072, "status": 0xFE}] * 5 +
        [{"voltage_raw": 3072, "status": 0xFD}] * 4 +
        [{"voltage_raw": 3072, "status": 0xFE}] * 5
    )
    data = make_dslog_file(records_args)

    from dslog_parser import parse_dslog_records
    records = list(parse_dslog_records(data))
    transitions = detect_transitions(records)
    assert len(transitions) == 1  # Only initial Disabled
    assert transitions[0]["mode"] == "Disabled"


def test_transition_flicker_ignored():
    from dslog_processor import detect_transitions
    # Disabled with single-record flickers to Autonomous
    records_args = []
    for i in range(20):
        if i % 3 == 0:
            records_args.append({"voltage_raw": 3072, "status": 0xFD})  # Auto flicker
        else:
            records_args.append({"voltage_raw": 3072, "status": 0xFE})  # Disabled
    data = make_dslog_file(records_args)

    from dslog_parser import parse_dslog_records
    records = list(parse_dslog_records(data))
    transitions = detect_transitions(records)
    assert len(transitions) == 1
    assert transitions[0]["mode"] == "Disabled"


def test_full_match_sequence():
    from dslog_processor import detect_transitions
    # Disconnected → Disabled → Autonomous → Disabled → Teleop → Disabled
    records_args = (
        [{"voltage_raw": 3072, "status": 0xFF}] * 10 +   # Disconnected
        [{"voltage_raw": 3072, "status": 0xFE}] * 10 +   # Disabled
        [{"voltage_raw": 3072, "status": 0xFD}] * 10 +   # Autonomous
        [{"voltage_raw": 3072, "status": 0xFE}] * 10 +   # Disabled
        [{"voltage_raw": 3072, "status": 0xFB}] * 10 +   # Teleop
        [{"voltage_raw": 3072, "status": 0xFE}] * 10      # Disabled
    )
    data = make_dslog_file(records_args)

    from dslog_parser import parse_dslog_records
    records = list(parse_dslog_records(data))
    transitions = detect_transitions(records)
    modes = [t["mode"] for t in transitions]
    assert modes == ["Disconnected", "Disabled", "Autonomous", "Disabled", "Teleop", "Disabled"]


def test_transition_display_format():
    from dslog_processor import detect_transitions
    records_args = (
        [{"voltage_raw": 3072, "status": 0xFE}] * 5 +
        [{"voltage_raw": 3072, "status": 0xFD}] * 5
    )
    data = make_dslog_file(records_args)

    from dslog_parser import parse_dslog_records
    records = list(parse_dslog_records(data))
    transitions = detect_transitions(records)
    assert transitions[1]["display"] == "***** Transition: Autonomous"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest match_processor/tests/test_dslog_processor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dslog_processor'`

- [ ] **Step 3: Implement transition detection**

Create `match_processor/dslog_processor.py`:

```python
"""dslog processing: mode transition detection and telemetry summary."""

DEBOUNCE_COUNT = 5  # 5 records × 20ms = 100ms
RECORD_INTERVAL = 0.020  # 20ms between records


def _format_timestamp(record_index):
    """Format record index as relative timestamp: 'SSS.mmm' (7 chars, zero-padded, 3 decimals)."""
    seconds = record_index * RECORD_INTERVAL
    return f"{seconds:07.3f}"


def detect_transitions(records):
    """Detect debounced mode transitions from parsed dslog records.

    Args:
        records: list of record dicts from parse_dslog_records (must have 'mode' and 'index' keys).

    Returns:
        list of transition event dicts: {"time": "SSS.mmm", "display": "***** Transition: <mode>"}
        The first entry is the initial mode (no "Transition:" prefix in display for record 0,
        but we include it for consistency — it will be filtered or used as context).
    """
    if not records:
        return []

    transitions = []

    # Initial mode (no debounce needed)
    confirmed_mode = records[0]["mode"]
    transitions.append({
        "time": _format_timestamp(records[0]["index"]),
        "display": f"***** Transition: {confirmed_mode}",
        "mode": confirmed_mode,
    })

    streak_mode = None
    streak_start_index = 0
    streak_count = 0

    for rec in records[1:]:
        mode = rec["mode"]
        if mode != confirmed_mode:
            if mode == streak_mode:
                streak_count += 1
            else:
                streak_mode = mode
                streak_start_index = rec["index"]
                streak_count = 1

            if streak_count >= DEBOUNCE_COUNT:
                confirmed_mode = streak_mode
                transitions.append({
                    "time": _format_timestamp(streak_start_index),
                    "display": f"***** Transition: {confirmed_mode}",
                    "mode": confirmed_mode,
                })
                streak_mode = None
                streak_count = 0
        else:
            streak_mode = None
            streak_count = 0

    return transitions
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest match_processor/tests/test_dslog_processor.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```
feat: add debounced mode transition detection
```

---

### Task 6: dslog Processor — Telemetry Summary

**Files:**
- Modify: `match_processor/dslog_processor.py`
- Modify: `match_processor/tests/test_dslog_processor.py`

- [ ] **Step 1: Write failing tests for telemetry summary**

Append to `test_dslog_processor.py`:

```python
def test_telemetry_summary_basic():
    from dslog_processor import compute_telemetry
    from dslog_parser import parse_dslog_records

    records_args = [
        {"voltage_raw": 2048, "cpu": 50, "can": 100, "trip": 4, "pkt_loss": 10, "status": 0xFE},
        {"voltage_raw": 3200, "cpu": 100, "can": 200, "trip": 20, "pkt_loss": 25, "status": 0xFE},
    ]
    data = make_dslog_file(records_args)
    records = list(parse_dslog_records(data))
    telemetry = compute_telemetry(records)

    assert telemetry is not None
    assert abs(telemetry["voltage_min"] - 8.0) < 0.01    # 2048/256
    assert abs(telemetry["voltage_max"] - 12.5) < 0.01   # 3200/256
    assert abs(telemetry["cpu_min"] - 25.0) < 0.1        # 50 × 0.5 × 0.01 = 0.25 → 25%
    assert abs(telemetry["cpu_max"] - 50.0) < 0.1        # 100 × 0.5 × 0.01 = 0.50 → 50%


def test_telemetry_excludes_garbage_voltage():
    from dslog_processor import compute_telemetry
    from dslog_parser import parse_dslog_records

    records_args = [
        {"voltage_raw": 256, "status": 0xFE},     # 1.0V — garbage, excluded
        {"voltage_raw": 65535, "status": 0xFE},    # 255.99V — garbage, excluded
        {"voltage_raw": 2560, "cpu": 0, "can": 0, "trip": 0, "pkt_loss": 0, "status": 0xFE},  # 10.0V — valid
    ]
    data = make_dslog_file(records_args)
    records = list(parse_dslog_records(data))
    telemetry = compute_telemetry(records)

    assert telemetry is not None
    assert abs(telemetry["voltage_min"] - 10.0) < 0.01
    assert abs(telemetry["voltage_max"] - 10.0) < 0.01


def test_telemetry_none_when_no_valid_records():
    from dslog_processor import compute_telemetry
    from dslog_parser import parse_dslog_records

    # All records have garbage voltage
    records_args = [{"voltage_raw": 65535, "status": 0xFF}] * 5
    data = make_dslog_file(records_args)
    records = list(parse_dslog_records(data))
    telemetry = compute_telemetry(records)

    assert telemetry is None


def test_telemetry_none_when_empty():
    from dslog_processor import compute_telemetry
    telemetry = compute_telemetry([])
    assert telemetry is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest match_processor/tests/test_dslog_processor.py::test_telemetry_summary_basic -v`
Expected: FAIL — `ImportError: cannot import name 'compute_telemetry'`

- [ ] **Step 3: Implement telemetry summary**

Append to `match_processor/dslog_processor.py`:

```python
# Voltage range for valid records (exclude pre-connection garbage)
VOLTAGE_MIN_VALID = 6.0
VOLTAGE_MAX_VALID = 16.0


def compute_telemetry(records):
    """Compute whole-match min/max telemetry from parsed dslog records.

    Only includes records with plausible voltage (6.0 < V < 16.0).
    Returns dict with *_min/*_max keys, or None if no valid records.
    """
    valid = [r for r in records if VOLTAGE_MIN_VALID < r["voltage"] < VOLTAGE_MAX_VALID]

    if not valid:
        return None

    return {
        "voltage_min": min(r["voltage"] for r in valid),
        "voltage_max": max(r["voltage"] for r in valid),
        "cpu_min": min(r["cpu"] * 100 for r in valid),
        "cpu_max": max(r["cpu"] * 100 for r in valid),
        "can_min": min(r["can"] * 100 for r in valid),
        "can_max": max(r["can"] * 100 for r in valid),
        "trip_min": min(r["trip_ms"] for r in valid),
        "trip_max": max(r["trip_ms"] for r in valid),
        "packet_loss_min": min(r["packet_loss"] * 100 for r in valid),
        "packet_loss_max": max(r["packet_loss"] * 100 for r in valid),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest match_processor/tests/test_dslog_processor.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```
feat: add telemetry min/max computation with voltage filtering
```

---

### Task 7: match_writer — Reorder Sections and Add Telemetry

**Files:**
- Modify: `match_processor/match_writer.py`
- Modify: `match_processor/tests/test_match_writer.py`

- [ ] **Step 1: Write failing tests for new section order and telemetry**

Append to `test_match_writer.py`:

```python
def test_section_order_joysticks_telemetry_before_events():
    from match_writer import format_match_events_txt
    fms_info = {
        "match_type": "Qualification", "match_number": 39, "replay": 1,
        "field_time": "26/3/28 21:45:53",
        "ds_version": "FRC Driver Station - Version 26.0",
    }
    log_files = [{"seq": 1, "basename": "2026_03_28 17_45_53 Sat"}]
    events_by_log = {1: [{"time": "000.000", "display": "FMS Connected"}]}
    joysticks = [{"number": 0, "name": "Xbox", "axes": 6, "buttons": 16, "povs": 1}]
    telemetry = {
        "voltage_min": 7.43, "voltage_max": 12.71,
        "cpu_min": 0, "cpu_max": 67,
        "can_min": 0, "can_max": 100,
        "trip_min": 0.0, "trip_max": 11.0,
        "packet_loss_min": 0, "packet_loss_max": 40,
    }

    txt = format_match_events_txt(fms_info, "Q39", "2026ncpem", log_files, events_by_log, joysticks, telemetry=telemetry)
    lines = txt.split("\n")

    joystick_idx = next(i for i, l in enumerate(lines) if l == "Joysticks:")
    telemetry_idx = next(i for i, l in enumerate(lines) if l == "Telemetry:")
    events_idx = next(i for i, l in enumerate(lines) if l == "Events:")

    assert joystick_idx < telemetry_idx < events_idx


def test_telemetry_section_content():
    from match_writer import format_match_events_txt
    fms_info = {
        "match_type": "Qualification", "match_number": 39, "replay": 1,
        "field_time": "26/3/28 21:45:53",
        "ds_version": "FRC Driver Station - Version 26.0",
    }
    log_files = [{"seq": 1, "basename": "2026_03_28 17_45_53 Sat"}]
    events_by_log = {1: []}
    joysticks = []
    telemetry = {
        "voltage_min": 7.43, "voltage_max": 12.71,
        "cpu_min": 0, "cpu_max": 67,
        "can_min": 0, "can_max": 100,
        "trip_min": 0.0, "trip_max": 11.0,
        "packet_loss_min": 0, "packet_loss_max": 40,
    }

    txt = format_match_events_txt(fms_info, "Q39", "2026ncpem", log_files, events_by_log, joysticks, telemetry=telemetry)

    assert "Voltage: 7.43 - 12.71 V" in txt
    assert "CPU: 0 - 67%" in txt
    assert "CAN Utilization: 0 - 100%" in txt
    assert "Trip Time: 0.0 - 11.0 ms" in txt
    assert "Packet Loss: 0 - 40%" in txt


def test_telemetry_section_none():
    from match_writer import format_match_events_txt
    fms_info = {
        "match_type": "Elimination", "match_number": 3, "replay": 1,
        "field_time": "26/3/29 17:42:4",
        "ds_version": "FRC Driver Station - Version 26.0",
    }
    log_files = [{"seq": 1, "basename": "2026_03_29 13_41_30 Sun"}]
    events_by_log = {1: []}
    joysticks = []

    txt = format_match_events_txt(fms_info, "E3_R1", "2026ncpem", log_files, events_by_log, joysticks, telemetry=None)

    assert "No telemetry data available." in txt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest match_processor/tests/test_match_writer.py::test_section_order_joysticks_telemetry_before_events -v`
Expected: FAIL — `format_match_events_txt() got an unexpected keyword argument 'telemetry'`

- [ ] **Step 3: Update format_match_events_txt**

Replace the body of `format_match_events_txt` in `match_processor/match_writer.py`. The new signature adds `telemetry=None` and `transition_events=None` parameters. The section order becomes: Header → NOTE → Log Files → Joysticks → Telemetry → Events.

```python
def format_match_events_txt(fms_info, match_id, event_name, log_files, events_by_log, joysticks,
                            telemetry=None, transition_events=None):
    """Generate the full match_events.txt content as a string.

    Args:
        fms_info: dict with match_type, match_number, replay, field_time, ds_version
        match_id: str like 'Q52' or 'E6_R1'
        event_name: str TBA event key (e.g., '2026ncpem')
        log_files: list of dicts with seq and basename
        events_by_log: dict mapping seq number -> list of event dicts (time, display)
        joysticks: list of joystick dicts (number, name, axes, buttons, povs)
        telemetry: dict with *_min/*_max keys from compute_telemetry, or None
        transition_events: dict mapping seq number -> list of transition event dicts, or None
    """
    lines = []

    # Header
    lines.append(f"Match: {fms_info['match_type']} {fms_info['match_number']}")
    lines.append(f"Event: {event_name}")
    lines.append(f"Field Time: {fms_info['field_time']}")
    lines.append(f"DS Version: {fms_info['ds_version']}")
    lines.append(f"Replay: {fms_info['replay']}")
    tba_url = build_tba_url(event_name, fms_info["match_type"], fms_info["match_number"], fms_info["replay"])
    lines.append(f"The Blue Alliance: {tba_url}")
    lines.append("")

    # Non-participation note
    if detect_non_participation(events_by_log, joysticks):
        lines.append("NOTE: The robot does not appear to have participated in this match.")
        lines.append("")

    # Log files
    lines.append("Log Files:")
    for lf in log_files:
        lines.append(f"  [{lf['seq']}] {lf['basename']} ({match_id}_{lf['seq']}_)")
    lines.append("")

    # Joysticks
    lines.append("Joysticks:")
    for j in joysticks:
        lines.append(f"  {j['number']}: {j['name']} - {j['axes']} axes, {j['buttons']} buttons, {j['povs']} POV")
    lines.append("")

    # Telemetry
    lines.append("Telemetry:")
    if telemetry is None:
        lines.append("  No telemetry data available.")
    else:
        lines.append(f"  Voltage: {telemetry['voltage_min']:.2f} - {telemetry['voltage_max']:.2f} V")
        lines.append(f"  CPU: {telemetry['cpu_min']:.0f} - {telemetry['cpu_max']:.0f}%")
        lines.append(f"  CAN Utilization: {telemetry['can_min']:.0f} - {telemetry['can_max']:.0f}%")
        lines.append(f"  Trip Time: {telemetry['trip_min']:.1f} - {telemetry['trip_max']:.1f} ms")
        lines.append(f"  Packet Loss: {telemetry['packet_loss_min']:.0f} - {telemetry['packet_loss_max']:.0f}%")
    lines.append("")

    # Events (merge dsevents and transition events, sorted chronologically)
    lines.append("Events:")
    for lf in log_files:
        seq = lf["seq"]
        merged = list(events_by_log.get(seq, []))
        if transition_events:
            merged.extend(transition_events.get(seq, []))
        merged.sort(key=lambda e: e["time"])
        for event in merged:
            lines.append(f"  [{seq}] {event['time']}  {event['display']}")
    lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 4: Run ALL match_writer tests**

Run: `uv run pytest match_processor/tests/test_match_writer.py -v`
Expected: All tests pass (existing tests work because `telemetry` defaults to `None`)

- [ ] **Step 5: Commit**

```
feat: reorder sections (Joysticks, Telemetry before Events) and add telemetry output
```

---

### Task 8: match_writer — Transition Events in Output

**Files:**
- Modify: `match_processor/tests/test_match_writer.py`

- [ ] **Step 1: Write test for transition events merged into Events section**

Append to `test_match_writer.py`:

```python
def test_transition_events_interleaved():
    from match_writer import format_match_events_txt
    fms_info = {
        "match_type": "Qualification", "match_number": 39, "replay": 1,
        "field_time": "26/3/28 21:45:53",
        "ds_version": "FRC Driver Station - Version 26.0",
    }
    log_files = [{"seq": 1, "basename": "2026_03_28 17_45_53 Sat"}]
    events_by_log = {1: [
        {"time": "000.000", "display": "FMS Connected"},
        {"time": "001.000", "display": "Code Start Notification"},
    ]}
    joysticks = []
    transition_events = {1: [
        {"time": "000.500", "display": "***** Transition: Disabled"},
    ]}

    txt = format_match_events_txt(fms_info, "Q39", "2026ncpem", log_files, events_by_log, joysticks,
                                  transition_events=transition_events)

    lines = txt.split("\n")
    event_lines = [l.strip() for l in lines if l.strip().startswith("[1]")]
    # Should be chronologically sorted
    assert "FMS Connected" in event_lines[0]
    assert "Transition: Disabled" in event_lines[1]
    assert "Code Start Notification" in event_lines[2]
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest match_processor/tests/test_match_writer.py::test_transition_events_interleaved -v`
Expected: PASS (implementation already handles this from Task 7)

- [ ] **Step 3: Commit**

```
test: add transition event interleaving test for match_writer
```

---

### Task 9: process_matches — Wire Up dslog Parsing

**Files:**
- Modify: `match_processor/process_matches.py`

- [ ] **Step 1: Add dslog imports**

Add to the imports section of `process_matches.py`:

```python
from dslog_parser import parse_dslog_path
from dslog_processor import detect_transitions, compute_telemetry
```

- [ ] **Step 2: Update process_match to parse dslog files**

Replace the `process_match` function body. The key changes:
1. Parse each dslog file alongside its dsevents
2. Aggregate records across all logs for telemetry
3. Detect transitions per log, keyed by seq number
4. Pass telemetry and transition_events to `format_match_events_txt`

```python
def process_match(key, files, match_id, event_name, source_dir, dest_dir):
    """Process a single match: parse events, write summary, copy files."""
    fms_info = files[0]["fms_info"]

    log_entries = []
    events_by_log = {}
    transition_events = {}
    all_dslog_records = []

    for seq, fi in enumerate(files, start=1):
        basename = os.path.splitext(os.path.basename(fi["path"]))[0]
        log_entries.append({
            "seq": seq,
            "basename": basename,
            "dsevents_path": fi["path"],
        })

        # Format and collapse dsevents
        formatted = format_events(fi["parsed"])
        collapsed = collapse_repeats(formatted)
        events_by_log[seq] = collapsed

        # Parse dslog
        dslog_path = fi["path"].rsplit(".dsevents", 1)[0] + ".dslog"
        if os.path.exists(dslog_path):
            dslog_data = parse_dslog_path(dslog_path)
            if dslog_data["records"]:
                all_dslog_records.extend(dslog_data["records"])
                transitions = detect_transitions(dslog_data["records"])
                # Skip initial mode transition (record 0) — it's context, not an event
                transition_events[seq] = [t for t in transitions[1:]]

    # Extract joystick info
    joysticks = []
    for fi in files:
        joysticks = extract_joystick_info(fi["parsed"]["events"])
        if joysticks:
            break

    # Compute telemetry across all logs
    telemetry = compute_telemetry(all_dslog_records)

    # Generate match_events.txt
    txt = format_match_events_txt(
        fms_info, match_id, event_name, log_entries, events_by_log, joysticks,
        telemetry=telemetry, transition_events=transition_events,
    )

    # Write files
    write_match_events_file(dest_dir, match_id, txt)
    copy_match_files(match_id, log_entries, source_dir, dest_dir)

    print(f"  {match_id}: wrote {match_id}_match_events.txt + {len(log_entries)} log pair(s)")
```

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest match_processor/tests/ -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```
feat: wire dslog parsing into match processing pipeline
```

---

### Task 10: Integration Tests with Real Data

**Files:**
- Modify: `match_processor/tests/test_integration.py`

- [ ] **Step 1: Add integration test for dslog transitions in real data**

Append to `test_integration.py`:

```python
def test_real_dslog_produces_transitions(tmp_dirs):
    """Integration test: real dslog files produce debounced transitions."""
    src, dst = tmp_dirs

    from dslog_parser import parse_dslog_path
    from dslog_processor import detect_transitions

    # Use a known match dslog from the test data
    import glob
    dslog_files = sorted(glob.glob("2026/UNCPembroke/Q39_1_*.dslog"))
    if not dslog_files:
        pytest.skip("No Q39 test data available")

    result = parse_dslog_path(dslog_files[0])
    assert result["header"] is not None
    assert len(result["records"]) > 100

    transitions = detect_transitions(result["records"])
    modes = [t["mode"] for t in transitions]
    # Q39 should have Autonomous and Teleop transitions
    assert "Autonomous" in modes
    assert "Teleop" in modes


def test_real_dslog_produces_telemetry(tmp_dirs):
    """Integration test: real dslog files produce telemetry summary."""
    src, dst = tmp_dirs

    from dslog_parser import parse_dslog_path
    from dslog_processor import compute_telemetry

    import glob
    dslog_files = sorted(glob.glob("2026/UNCPembroke/Q39_1_*.dslog"))
    if not dslog_files:
        pytest.skip("No Q39 test data available")

    result = parse_dslog_path(dslog_files[0])
    telemetry = compute_telemetry(result["records"])

    assert telemetry is not None
    assert 6.0 < telemetry["voltage_min"] < 16.0
    assert 6.0 < telemetry["voltage_max"] < 16.0
    assert telemetry["voltage_min"] <= telemetry["voltage_max"]


def test_end_to_end_with_dslog(tmp_dirs):
    """Integration test: full pipeline produces telemetry and transitions in output."""
    src, dst = tmp_dirs

    # Copy a real match's files to src
    import glob
    import shutil

    dsevents = sorted(glob.glob("2026/03/2026_03_28 17_45_53*.dsevents"))
    if not dsevents:
        pytest.skip("No Q39 source data available")

    for f in dsevents:
        base = os.path.basename(f)
        shutil.copy2(f, src / base)
        dslog = f.rsplit(".dsevents", 1)[0] + ".dslog"
        if os.path.exists(dslog):
            shutil.copy2(dslog, src / os.path.basename(dslog))

    from process_matches import find_dsevents_files, scan_and_identify, process_match
    from match_identifier import build_match_id
    matches = scan_and_identify(find_dsevents_files(str(src)), str(dst))

    if not matches:
        pytest.skip("No matches found in test data")

    key = list(matches.keys())[0]
    files = matches[key]
    fms = files[0]["fms_info"]
    match_id = build_match_id(fms["match_type"], fms["match_number"], fms["replay"])
    process_match(key, files, match_id, "2026ncpem", str(src), str(dst))

    txt = (dst / f"{match_id}_match_events.txt").read_text()
    assert "Telemetry:" in txt
    assert "Voltage:" in txt
    assert "***** Transition:" in txt
    # Verify section order
    lines = txt.split("\n")
    joystick_idx = next((i for i, l in enumerate(lines) if l == "Joysticks:"), None)
    telemetry_idx = next((i for i, l in enumerate(lines) if l == "Telemetry:"), None)
    events_idx = next((i for i, l in enumerate(lines) if l == "Events:"), None)
    assert joystick_idx is not None
    assert telemetry_idx is not None
    assert events_idx is not None
    assert joystick_idx < telemetry_idx < events_idx
```

- [ ] **Step 2: Run integration tests**

Run: `uv run pytest match_processor/tests/test_integration.py -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```
test: add integration tests for dslog transitions and telemetry
```

---

### Task 11: Smoke Test and Full Suite

**Files:** None (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest match_processor/tests/ -v`
Expected: All tests pass (58 existing + ~25 new)

- [ ] **Step 2: Smoke test with real data**

Run: `uv run python3 match_processor/process_matches.py 2026/03 /tmp/test_output --event 2026ncpem --date 2026-03-28`

Verify:
- Output includes Telemetry section with voltage ranges
- Events section includes `***** Transition:` entries
- Joysticks appears before Telemetry, Telemetry before Events
- No crashes or warnings about dslog parsing

- [ ] **Step 3: Verify a non-participation match output**

Check a non-participation match output shows `No telemetry data available.`

- [ ] **Step 4: Commit**

```
docs: verify dslog transitions and telemetry implementation
```

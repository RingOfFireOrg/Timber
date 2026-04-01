# Power Analyzer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Also use the frc-log-reviewer skill (`.claude/skills/frc-log-review.md`) with its reference (`.claude/skills/references/frc-log-formats.md`) to validate all binary parsing code.

**Goal:** Build a standalone CLI tool that detects battery voltage dips in `.dslog` files, reports per-channel PDH currents during each dip, and produces a cross-referenceable event log.

**Architecture:** Three phases — (1) extract shared parsers into `shared/` so both `match_processor/` and `power_analyzer/` can import them, (2) extend `dslog_parser.py` to yield raw PD bytes alongside existing fields, (3) build the power analyzer as new modules (`pdh_decoder.py`, `dip_detector.py`, `analyze_power.py`) consuming those shared parsers. All binary parsing uses `struct` with big-endian format strings (`>`). PDH current decoding follows AdvantageScope's `DSLogReader.ts` algorithm.

**Tech Stack:** Python 3.14, struct, csv, argparse, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-04-01-power-analyzer-design.md`

**Code review skill:** `.claude/skills/frc-log-review.md` — use for all binary parsing validation. Key checks: endianness (`>` prefix on all struct formats), correct PD byte offsets, LSB-first bit assembly for channel currents, named constants for magic numbers, truncated-file handling.

---

## File Map

| File | Role | Change |
|------|------|--------|
| `shared/__init__.py` | **Create** — package marker | Empty |
| `shared/dslog_parser.py` | **Move** from `match_processor/` | Add `pd_type` and `pd_data` fields to yielded record dicts |
| `shared/dsevents_parser.py` | **Move** from `match_processor/` | No code changes |
| `shared/event_formatter.py` | **Move** from `match_processor/` | No code changes |
| `shared/tests/__init__.py` | **Create** — test package marker | Empty |
| `shared/tests/conftest.py` | **Move** from `match_processor/tests/` | Fixture helpers for dslog/dsevents binary builders |
| `shared/tests/test_dslog_parser.py` | **Move** from `match_processor/tests/` | Add `pd_type`/`pd_data` field tests |
| `shared/tests/test_dsevents_parser.py` | **Move** from `match_processor/tests/` | No code changes beyond import updates |
| `shared/tests/test_event_formatter.py` | **Move** from `match_processor/tests/` | No code changes beyond import updates |
| `match_processor/process_matches.py` | **Modify** | Update imports: `from shared.dslog_parser import ...` etc. |
| `match_processor/dslog_processor.py` | **Modify** | Update import: `from shared.dslog_parser import ...` |
| `match_processor/tests/test_match_writer.py` | **Modify** | Update conftest import path |
| `match_processor/tests/test_match_identifier.py` | **Modify** | Update conftest import path |
| `match_processor/tests/test_dslog_processor.py` | **Modify** | Update conftest import path |
| `match_processor/tests/test_integration.py` | **Modify** | Update conftest and parser import paths |
| `pyproject.toml` | **Modify** | Add `shared` and `power_analyzer` to `pythonpath`, add `shared/tests` and `power_analyzer/tests` to `testpaths` |
| `power_analyzer/__init__.py` | **Create** — package marker | Empty |
| `power_analyzer/pdh_decoder.py` | **Create** — PDH/PDP current decoding | REV 20+4 channel and CTRE 16 channel extraction |
| `power_analyzer/dip_detector.py` | **Create** — voltage dip detection | Dip start/end with 5-record debounced recovery |
| `power_analyzer/analyze_power.py` | **Create** — CLI entry point | Argument parsing, file pairing, report formatting, orchestration |
| `power_analyzer/profile_parser.py` | **Create** — profile CSV parser | Parse channel-to-motor mapping CSV |
| `power_analyzer/report_formatter.py` | **Create** — output formatters | Dip report and event log formatting |
| `power_analyzer/tests/__init__.py` | **Create** — test package marker | Empty |
| `power_analyzer/tests/conftest.py` | **Create** — power analyzer test fixtures | Profile CSV helpers, dslog record builders with PD data |
| `power_analyzer/tests/test_pdh_decoder.py` | **Create** — decoder unit tests | REV main/extra channels, CTRE channels, edge cases |
| `power_analyzer/tests/test_dip_detector.py` | **Create** — detector unit tests | Dip detection, debouncing, no-recovery, no-dips |
| `power_analyzer/tests/test_analyze_power.py` | **Create** — CLI integration tests | End-to-end with profile CSV and dslog fixture files |
| `power_analyzer/tests/test_profile_parser.py` | **Create** — profile parser tests | Basic parsing, duplicates, bad rows |
| `power_analyzer/tests/test_report_formatter.py` | **Create** — formatter tests | Report output, channel tables, event log |
| `match_processor/__init__.py` | **Create** — package marker | Enables `match_processor` to be importable as a package |
| `match_processor/tests/__init__.py` | **Create** — package marker | Enables `match_processor.tests` subpackage |

---

### Task 1: Extract Shared Parsers

Move `dslog_parser.py`, `dsevents_parser.py`, and `event_formatter.py` from `match_processor/` to `shared/`, along with their tests. Tests should live near the code they test. Update all imports. This is a pure refactor — no behavior changes.

**Files:**
- Create: `shared/__init__.py`, `shared/tests/__init__.py`
- Create: `match_processor/__init__.py`, `match_processor/tests/__init__.py`
- Move: `match_processor/dslog_parser.py` → `shared/dslog_parser.py`
- Move: `match_processor/dsevents_parser.py` → `shared/dsevents_parser.py`
- Move: `match_processor/event_formatter.py` → `shared/event_formatter.py`
- Move: `match_processor/tests/conftest.py` → `shared/tests/conftest.py`
- Move: `match_processor/tests/test_dslog_parser.py` → `shared/tests/test_dslog_parser.py`
- Move: `match_processor/tests/test_dsevents_parser.py` → `shared/tests/test_dsevents_parser.py`
- Move: `match_processor/tests/test_event_formatter.py` → `shared/tests/test_event_formatter.py`
- Modify: `match_processor/process_matches.py`
- Modify: `match_processor/dslog_processor.py`
- Modify: `match_processor/tests/test_dslog_processor.py`
- Modify: `match_processor/tests/test_match_writer.py`
- Modify: `match_processor/tests/test_match_identifier.py`
- Modify: `match_processor/tests/test_integration.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Create package marker files**

```python
# shared/__init__.py — empty package marker
# shared/tests/__init__.py — empty package marker
# match_processor/__init__.py — empty package marker (enables cross-package imports)
# match_processor/tests/__init__.py — empty package marker
```

Create all four empty `__init__.py` files.

- [ ] **Step 2: Move the three parser files and their tests**

```bash
mkdir -p shared/tests
git mv match_processor/dslog_parser.py shared/dslog_parser.py
git mv match_processor/dsevents_parser.py shared/dsevents_parser.py
git mv match_processor/event_formatter.py shared/event_formatter.py
git mv match_processor/tests/conftest.py shared/tests/conftest.py
git mv match_processor/tests/test_dslog_parser.py shared/tests/test_dslog_parser.py
git mv match_processor/tests/test_dsevents_parser.py shared/tests/test_dsevents_parser.py
git mv match_processor/tests/test_event_formatter.py shared/tests/test_event_formatter.py
```

- [ ] **Step 3: Update imports in `match_processor/process_matches.py`**

Replace:
```python
from dsevents_parser import parse_dsevents_path
from event_formatter import format_events, collapse_repeats
from dslog_parser import parse_dslog_path
```

With:
```python
from shared.dsevents_parser import parse_dsevents_path
from shared.event_formatter import format_events, collapse_repeats
from shared.dslog_parser import parse_dslog_path
```

- [ ] **Step 4: Update imports in `match_processor/dslog_processor.py`**

This file currently has no imports from the moved modules. Verify with `grep`. If it imports from `dslog_parser`, update to `from shared.dslog_parser import ...`.

- [ ] **Step 5: Update imports in moved test files (`shared/tests/`)**

In `shared/tests/test_dslog_parser.py`:
```python
# Change:
from conftest import make_dslog_header, LABVIEW_EPOCH_OFFSET
from conftest import make_dslog_file
from dslog_parser import parse_dslog_header
from dslog_parser import parse_dslog_records
from dslog_parser import parse_dslog_path
# To:
from shared.tests.conftest import make_dslog_header, LABVIEW_EPOCH_OFFSET
from shared.tests.conftest import make_dslog_file
from shared.dslog_parser import parse_dslog_header
from shared.dslog_parser import parse_dslog_records
from shared.dslog_parser import parse_dslog_path
```

Apply the same pattern to:
- `shared/tests/test_dsevents_parser.py`: `from shared.dsevents_parser import ...`, `from shared.tests.conftest import ...`
- `shared/tests/test_event_formatter.py`: `from shared.event_formatter import ...`

- [ ] **Step 6: Create a new `match_processor/tests/conftest.py`**

The remaining `match_processor/tests/` test files (`test_dslog_processor.py`, `test_match_writer.py`, `test_match_identifier.py`, `test_integration.py`) need access to the fixture helpers that moved to `shared/tests/conftest.py`. Create a thin conftest that re-imports from shared:

```python
"""match_processor test fixtures — delegates to shared/tests/conftest.py."""

from shared.tests.conftest import *  # noqa: F401,F403
```

This preserves backward compatibility so existing match_processor tests continue to find fixtures via their local conftest.

- [ ] **Step 7: Update remaining `match_processor/tests/` test files**

These files may import directly from the moved modules. Update:
- `test_dslog_processor.py`: if it imports from `conftest`, no change needed (local conftest re-exports). If it imports from `dslog_parser`, change to `from shared.dslog_parser import ...`.
- `test_match_writer.py`: same pattern — check for imports from moved modules.
- `test_match_identifier.py`: same pattern.
- `test_integration.py`: check for imports from `dsevents_parser`, `dslog_parser`, `event_formatter` and update to `from shared.* import ...`.

- [ ] **Step 8: Update `pyproject.toml` pythonpath and testpaths**

```toml
[tool.pytest.ini_options]
pythonpath = [".", "match_processor", "shared"]
testpaths = ["shared/tests", "match_processor/tests"]
```

- [ ] **Step 9: Run all tests to verify refactor**

```bash
uv run pytest -v
```

Expected: all existing tests pass (currently 89 tests) across both `shared/tests/` and `match_processor/tests/`. Zero test failures.

- [ ] **Step 10: Commit**

```bash
git add shared/ match_processor/ pyproject.toml
git commit -m "refactor: extract shared parsers and their tests into shared/ package

Move dslog_parser, dsevents_parser, event_formatter and their tests from
match_processor/ to shared/ so power_analyzer can reuse them. Tests live
near the code they test.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Add `pd_type` and `pd_data` to dslog Parser

Extend `parse_dslog_records()` to include the raw PD bytes in each yielded record dict. Backward-compatible — existing consumers ignore the new fields.

**Files:**
- Modify: `shared/dslog_parser.py:64-104`
- Modify: `shared/tests/test_dslog_parser.py`

- [ ] **Step 1: Write failing tests for `pd_type` and `pd_data` fields**

Add to `shared/tests/test_dslog_parser.py`:

```python
def test_parse_records_pd_type_rev():
    from shared.dslog_parser import parse_dslog_records
    data = make_dslog_file([{"voltage_raw": 3072, "status": 0xFE, "pd_type": 0x21}])
    records = list(parse_dslog_records(data))
    assert len(records) == 1
    assert records[0]["pd_type"] == 0x21
    assert len(records[0]["pd_data"]) == 33


def test_parse_records_pd_type_ctre():
    from shared.dslog_parser import parse_dslog_records
    data = make_dslog_file([{"voltage_raw": 3072, "status": 0xFE, "pd_type": 0x19}])
    records = list(parse_dslog_records(data))
    assert records[0]["pd_type"] == 0x19
    assert len(records[0]["pd_data"]) == 25


def test_parse_records_pd_type_none():
    from shared.dslog_parser import parse_dslog_records
    data = make_dslog_file([{"voltage_raw": 3072, "status": 0xFE, "pd_type": 0x00}])
    records = list(parse_dslog_records(data))
    assert records[0]["pd_type"] == 0x00
    assert len(records[0]["pd_data"]) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest shared/tests/test_dslog_parser.py::test_parse_records_pd_type_rev -v
```

Expected: FAIL — `KeyError: 'pd_type'`

- [ ] **Step 3: Add `pd_type` and `pd_data` to record yield in `shared/dslog_parser.py`**

In `parse_dslog_records`, after the line that computes `record_size` and before the `yield`, add the PD data extraction. The PD data bytes start at `offset + FIXED_SIZE + PD_HEADER_SIZE` (after the 4-byte PD header) and span `pd_extra` bytes:

```python
        # Extract raw PD data for downstream consumers (e.g., PDH current decoding)
        pd_data_offset = offset + FIXED_SIZE + PD_HEADER_SIZE
        pd_data_bytes = data[pd_data_offset : pd_data_offset + pd_extra]

        yield {
            "index": index,
            "voltage": voltage_raw / 256,
            "cpu": cpu * 0.5 * 0.01,
            "can": can * 0.5 * 0.01,
            "trip_ms": trip * 0.5,
            "packet_loss": max(0.0, min(1.0, pkt_loss * 4 * 0.01)),
            "mode": _decode_mode(status),
            "pd_type": pd_type,
            "pd_data": pd_data_bytes,
        }
```

**frc-log-review check:** Verify that `pd_data_offset` is correct: the PD data section starts at the byte immediately after the 4-byte PD header (offset `FIXED_SIZE + PD_HEADER_SIZE = 14`), which is the CAN ID byte. For REV (0x21), this yields 33 bytes (CAN ID + 27 boolean array + 4 extra + 1 temp). For CTRE (0x19), 25 bytes. For type 0x00, 0 bytes. The `pd_type` value comes from `data[offset + FIXED_SIZE + 3]` which is the 4th byte of the PD header — correct per the format spec.

- [ ] **Step 4: Run all dslog parser tests**

```bash
uv run pytest shared/tests/test_dslog_parser.py -v
```

Expected: all tests pass including the 3 new ones.

- [ ] **Step 5: Run full test suite to confirm backward compatibility**

```bash
uv run pytest -v
```

Expected: all tests pass. Existing consumers don't access `pd_type`/`pd_data` so nothing breaks.

- [ ] **Step 6: Commit**

```bash
git add shared/dslog_parser.py shared/tests/test_dslog_parser.py
git commit -m "feat: add pd_type and pd_data fields to dslog record dicts

Expose raw power distribution bytes so downstream consumers (power analyzer)
can decode per-channel currents. Backward-compatible: existing code ignores
the new fields.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: REV PDH Current Decoder

Implement the REV PDH (0x21) channel current extraction from the 33-byte PD data section, following AdvantageScope's algorithm.

**Files:**
- Create: `power_analyzer/__init__.py`
- Create: `power_analyzer/tests/__init__.py`
- Create: `power_analyzer/tests/conftest.py`
- Create: `power_analyzer/tests/test_pdh_decoder.py`
- Create: `power_analyzer/pdh_decoder.py`

- [ ] **Step 1: Create package markers and test fixtures**

`power_analyzer/__init__.py` — empty file.

`power_analyzer/tests/__init__.py` — empty file.

`power_analyzer/tests/conftest.py`:

```python
"""Test fixtures for power analyzer tests."""

import struct
import os
import tempfile

# Re-use dslog fixture helpers from match_processor tests
from shared.tests.conftest import (
    make_dslog_header,
    make_dslog_file,
    make_dsevents_file,
    LABVIEW_EPOCH_OFFSET,
    PD_SIZES,
)


def make_rev_pd_data(channel_currents=None, extra_currents=None):
    """Build a 33-byte REV PDH data section with specified channel currents.

    Args:
        channel_currents: dict mapping channel (0-19) to current in amps.
            Each value is multiplied by 8 to get the 10-bit raw value.
        extra_currents: dict mapping channel (20-23) to current in amps.
            Each value is multiplied by 16 to get the raw byte value.

    Returns:
        33 bytes: 1 CAN ID + 27 boolean array + 4 extra channels + 1 temp.
    """
    if channel_currents is None:
        channel_currents = {}
    if extra_currents is None:
        extra_currents = {}

    can_id = 1  # default CAN ID
    # 27-byte boolean array (216 bits), LSB-first per byte
    bits = [0] * 216
    for ch, amps in channel_currents.items():
        if ch < 0 or ch > 19:
            continue
        raw = int(amps * 8)
        read_pos = (ch // 3) * 32 + (ch % 3) * 10
        for bit_i in range(10):
            if raw & (1 << bit_i):
                bits[read_pos + bit_i] = 1

    # Pack bits into bytes, LSB-first
    bool_bytes = bytearray(27)
    for i, bit in enumerate(bits):
        if bit:
            bool_bytes[i // 8] |= (1 << (i % 8))

    # Extra channels (20-23): 1 byte each, value × 16 = amps
    extra_bytes = bytearray(4)
    for ch, amps in extra_currents.items():
        idx = ch - 20
        if 0 <= idx <= 3:
            extra_bytes[idx] = min(255, int(amps * 16))

    temp = 0
    return bytes([can_id]) + bytes(bool_bytes) + bytes(extra_bytes) + bytes([temp])


def make_ctre_pd_data(channel_currents=None):
    """Build a 25-byte CTRE PDP data section with specified channel currents.

    Args:
        channel_currents: dict mapping channel (0-15) to current in amps.
            Each value is multiplied by 8 to get the 10-bit raw value.

    Returns:
        25 bytes: 1 CAN ID + 21 boolean array + 3 metadata.
    """
    if channel_currents is None:
        channel_currents = {}

    can_id = 1
    # 21-byte boolean array (168 bits), LSB-first per byte
    bits = [0] * 168
    for ch, amps in channel_currents.items():
        if ch < 0 or ch > 15:
            continue
        raw = int(amps * 8)
        read_pos = (ch // 6) * 64 + (ch % 6) * 10
        for bit_i in range(10):
            if raw & (1 << bit_i):
                bits[read_pos + bit_i] = 1

    bool_bytes = bytearray(21)
    for i, bit in enumerate(bits):
        if bit:
            bool_bytes[i // 8] |= (1 << (i % 8))

    metadata = b"\x00" * 3
    return bytes([can_id]) + bytes(bool_bytes) + metadata


def make_dslog_record_with_pd(status=0xFE, voltage_raw=3072, trip=0,
                               pkt_loss=0, cpu=0, can=0, pd_type=0x21,
                               pd_data=None):
    """Build a single dslog record with explicit PD data bytes.

    Unlike conftest.make_dslog_record (which uses zero-filled PD), this
    lets you inject specific PD bytes for current decoding tests.
    """
    fixed = struct.pack(">BbHBBBBH", trip, pkt_loss, voltage_raw, cpu, status, can, 0, 0)
    pd_header = struct.pack("4B", 0, 0, 0, pd_type)
    if pd_data is None:
        pd_extra_size = PD_SIZES.get(pd_type, 0)
        pd_data = b"\x00" * pd_extra_size
    return fixed + pd_header + pd_data


def make_profile_csv(channel_map, path):
    """Write a robot profile CSV file.

    Args:
        channel_map: list of (channel, can_id, description) tuples.
        path: file path to write.
    """
    with open(path, "w") as f:
        f.write("channel,can_id,description\n")
        for ch, can_id, desc in channel_map:
            f.write(f"{ch},{can_id},{desc}\n")
```

- [ ] **Step 2: Write failing tests for REV PDH decoder**

`power_analyzer/tests/test_pdh_decoder.py`:

```python
"""Tests for REV PDH and CTRE PDP current decoding."""

from conftest import make_rev_pd_data, make_ctre_pd_data


def test_decode_rev_single_channel():
    from pdh_decoder import decode_currents
    pd_data = make_rev_pd_data(channel_currents={0: 10.0})  # 10A on ch 0
    result = decode_currents(0x21, pd_data)
    assert abs(result[0] - 10.0) < 0.2  # 10-bit quantization: 1/8 = 0.125A resolution
    assert result[1] == 0.0  # other channels should be zero


def test_decode_rev_multiple_channels():
    from pdh_decoder import decode_currents
    pd_data = make_rev_pd_data(channel_currents={0: 50.0, 5: 25.0, 14: 60.0})
    result = decode_currents(0x21, pd_data)
    assert abs(result[0] - 50.0) < 0.2
    assert abs(result[5] - 25.0) < 0.2
    assert abs(result[14] - 60.0) < 0.2


def test_decode_rev_extra_channels():
    from pdh_decoder import decode_currents
    pd_data = make_rev_pd_data(extra_currents={20: 5.0, 23: 2.0})
    result = decode_currents(0x21, pd_data)
    assert abs(result[20] - 5.0) < 0.1  # 1/16 = 0.0625A resolution
    assert abs(result[23] - 2.0) < 0.1


def test_decode_rev_all_zeros():
    from pdh_decoder import decode_currents
    pd_data = make_rev_pd_data()
    result = decode_currents(0x21, pd_data)
    assert len(result) == 24
    assert all(v == 0.0 for v in result.values())


def test_decode_ctre_single_channel():
    from pdh_decoder import decode_currents
    pd_data = make_ctre_pd_data(channel_currents={0: 10.0})
    result = decode_currents(0x19, pd_data)
    assert abs(result[0] - 10.0) < 0.2
    assert len(result) == 16  # CTRE has 16 channels only


def test_decode_ctre_multiple_channels():
    from pdh_decoder import decode_currents
    pd_data = make_ctre_pd_data(channel_currents={0: 30.0, 8: 15.0, 15: 42.0})
    result = decode_currents(0x19, pd_data)
    assert abs(result[0] - 30.0) < 0.2
    assert abs(result[8] - 15.0) < 0.2
    assert abs(result[15] - 42.0) < 0.2


def test_decode_unknown_pd_type():
    from pdh_decoder import decode_currents
    result = decode_currents(0x00, b"")
    assert result is None


def test_decode_rev_truncated_data():
    from pdh_decoder import decode_currents
    # REV expects 33 bytes, give it 10
    result = decode_currents(0x21, b"\x00" * 10)
    assert result is None
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest power_analyzer/tests/test_pdh_decoder.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'pdh_decoder'`

- [ ] **Step 4: Implement `power_analyzer/pdh_decoder.py`**

```python
"""Decode per-channel currents from REV PDH and CTRE PDP data sections."""

# PD type constants
PD_TYPE_REV = 0x21
PD_TYPE_CTRE = 0x19

# Expected PD data sizes (including CAN ID byte)
REV_PD_DATA_SIZE = 33
CTRE_PD_DATA_SIZE = 25

# REV PDH: 20 main channels (10-bit packed) + 4 extra channels (1 byte each)
REV_MAIN_CHANNELS = 20
REV_EXTRA_CHANNELS = 4
REV_TOTAL_CHANNELS = REV_MAIN_CHANNELS + REV_EXTRA_CHANNELS
REV_BOOL_ARRAY_OFFSET = 1    # skip CAN ID byte
REV_BOOL_ARRAY_SIZE = 27     # 216 bits for 20 × 10-bit channels + padding
REV_EXTRA_OFFSET = 28        # bytes 28-31: extra channel currents
REV_BITS_PER_CHANNEL = 10
REV_CURRENT_DIVISOR = 8.0    # raw 10-bit value ÷ 8 = amps
REV_EXTRA_DIVISOR = 16.0     # raw byte ÷ 16 = amps

# CTRE PDP: 16 channels (10-bit packed)
CTRE_CHANNELS = 16
CTRE_BOOL_ARRAY_OFFSET = 1   # skip CAN ID byte
CTRE_BOOL_ARRAY_SIZE = 21    # 168 bits for 16 × 10-bit channels + padding
CTRE_BITS_PER_CHANNEL = 10
CTRE_CURRENT_DIVISOR = 8.0


def _read_bits_lsb(data_bytes, start_bit, count):
    """Read `count` bits starting at `start_bit`, assembled LSB-first.

    Args:
        data_bytes: bytes to read from.
        start_bit: bit index (0-based) into data_bytes, LSB-first per byte.
        count: number of bits to read.

    Returns:
        Integer assembled from the bits, LSB-first.
    """
    value = 0
    for i in range(count):
        bit_index = start_bit + i
        byte_index = bit_index // 8
        bit_offset = bit_index % 8
        if byte_index < len(data_bytes):
            if data_bytes[byte_index] & (1 << bit_offset):
                value |= (1 << i)
    return value


def _decode_rev(pd_data):
    """Decode REV PDH channel currents from 33-byte PD data section.

    Layout:
        Byte 0: CAN ID
        Bytes 1-27: boolean array (216 bits) encoding 20 main channels
        Bytes 28-31: 4 extra channel currents (1 byte each)
        Byte 32: temperature (not used)

    Main channels (0-19): 10-bit values packed at:
        read_position = (channel // 3) * 32 + (channel % 3) * 10
    Assembled LSB-first, divided by 8 for amps.

    Extra channels (20-23): each byte ÷ 16 for amps.
    """
    bool_array = pd_data[REV_BOOL_ARRAY_OFFSET : REV_BOOL_ARRAY_OFFSET + REV_BOOL_ARRAY_SIZE]
    currents = {}

    # Main channels 0-19
    for ch in range(REV_MAIN_CHANNELS):
        read_pos = (ch // 3) * 32 + (ch % 3) * REV_BITS_PER_CHANNEL
        raw = _read_bits_lsb(bool_array, read_pos, REV_BITS_PER_CHANNEL)
        currents[ch] = raw / REV_CURRENT_DIVISOR

    # Extra channels 20-23
    for i in range(REV_EXTRA_CHANNELS):
        ch = REV_MAIN_CHANNELS + i
        raw = pd_data[REV_EXTRA_OFFSET + i]
        currents[ch] = raw / REV_EXTRA_DIVISOR

    return currents


def _decode_ctre(pd_data):
    """Decode CTRE PDP channel currents from 25-byte PD data section.

    Layout:
        Byte 0: CAN ID
        Bytes 1-21: boolean array (168 bits) encoding 16 channels
        Bytes 22-24: metadata (not used)

    Channels (0-15): 10-bit values packed at:
        read_position = (channel // 6) * 64 + (channel % 6) * 10
    Assembled LSB-first, divided by 8 for amps.
    """
    bool_array = pd_data[CTRE_BOOL_ARRAY_OFFSET : CTRE_BOOL_ARRAY_OFFSET + CTRE_BOOL_ARRAY_SIZE]
    currents = {}

    for ch in range(CTRE_CHANNELS):
        read_pos = (ch // 6) * 64 + (ch % 6) * CTRE_BITS_PER_CHANNEL
        raw = _read_bits_lsb(bool_array, read_pos, CTRE_BITS_PER_CHANNEL)
        currents[ch] = raw / CTRE_CURRENT_DIVISOR

    return currents


def decode_currents(pd_type, pd_data):
    """Decode per-channel currents from PD data.

    Args:
        pd_type: PD type byte (0x21=REV, 0x19=CTRE).
        pd_data: raw PD data bytes (33 for REV, 25 for CTRE).

    Returns:
        dict mapping channel number -> current in amps, or None if
        pd_type is unknown or pd_data is too short.
    """
    if pd_type == PD_TYPE_REV:
        if len(pd_data) < REV_PD_DATA_SIZE:
            return None
        return _decode_rev(pd_data)
    elif pd_type == PD_TYPE_CTRE:
        if len(pd_data) < CTRE_PD_DATA_SIZE:
            return None
        return _decode_ctre(pd_data)
    return None
```

**frc-log-review checks applied:**
- Named constants for all magic numbers (offsets, sizes, divisors, type codes)
- LSB-first bit assembly matches AdvantageScope algorithm
- Stride formulas: REV `(ch // 3) * 32 + (ch % 3) * 10`, CTRE `(ch // 6) * 64 + (ch % 6) * 10`
- Truncated PD data returns `None` instead of crashing
- No endianness concern for bit-level operations (byte-at-a-time)

- [ ] **Step 5: Update `pyproject.toml` for power_analyzer tests**

```toml
[tool.pytest.ini_options]
pythonpath = [".", "match_processor", "shared", "power_analyzer"]
testpaths = ["shared/tests", "match_processor/tests", "power_analyzer/tests"]
```

- [ ] **Step 6: Run pdh_decoder tests**

```bash
uv run pytest power_analyzer/tests/test_pdh_decoder.py -v
```

Expected: all 8 tests pass.

- [ ] **Step 7: Commit**

```bash
git add power_analyzer/ pyproject.toml
git commit -m "feat: add REV PDH and CTRE PDP channel current decoder

Decode per-channel currents from dslog PD data sections using
AdvantageScope's LSB-first bit packing algorithm. Supports REV PDH
(24 channels) and CTRE PDP (16 channels).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Voltage Dip Detector

Detect voltage dips below a configurable threshold with debounced recovery, tracking per-channel peak currents during each dip.

**Files:**
- Create: `power_analyzer/dip_detector.py`
- Create: `power_analyzer/tests/test_dip_detector.py`

- [ ] **Step 1: Write failing tests for dip detection**

`power_analyzer/tests/test_dip_detector.py`:

```python
"""Tests for voltage dip detection with debounced recovery."""

from dip_detector import detect_dips

RECORD_INTERVAL = 0.020  # 20ms per record


def _make_record(index, voltage, mode="Teleop", pd_type=0x21, pd_data=None):
    """Build a minimal record dict for dip detection."""
    return {
        "index": index,
        "voltage": voltage,
        "mode": mode,
        "pd_type": pd_type,
        "pd_data": pd_data or b"\x00" * 33,
        "cpu": 0.5,
        "can": 0.5,
        "trip_ms": 5.0,
        "packet_loss": 0.0,
    }


def test_no_dips():
    records = [_make_record(i, 12.0) for i in range(100)]
    dips = detect_dips(records, voltage_threshold=10.0)
    assert dips == []


def test_single_dip_with_recovery():
    records = []
    # 10 records at 12V, then 5 at 8V, then 10 at 12V
    for i in range(10):
        records.append(_make_record(i, 12.0))
    for i in range(10, 15):
        records.append(_make_record(i, 8.0))
    for i in range(15, 25):
        records.append(_make_record(i, 12.0))

    dips = detect_dips(records, voltage_threshold=10.0)
    assert len(dips) == 1
    assert dips[0]["start_index"] == 10
    assert abs(dips[0]["min_voltage"] - 8.0) < 0.01
    assert dips[0]["recovered"] is True
    assert abs(dips[0]["recovery_voltage"] - 12.0) < 0.01


def test_dip_no_recovery():
    records = []
    for i in range(10):
        records.append(_make_record(i, 12.0))
    for i in range(10, 20):
        records.append(_make_record(i, 8.0))

    dips = detect_dips(records, voltage_threshold=10.0)
    assert len(dips) == 1
    assert dips[0]["recovered"] is False


def test_debounced_recovery():
    """Brief voltage bounce above threshold should not end the dip."""
    records = []
    for i in range(5):
        records.append(_make_record(i, 12.0))
    # Dip starts
    for i in range(5, 15):
        records.append(_make_record(i, 8.0))
    # Brief bounce above (4 records = below debounce threshold of 5)
    for i in range(15, 19):
        records.append(_make_record(i, 11.0))
    # Back below
    for i in range(19, 25):
        records.append(_make_record(i, 8.0))
    # Real recovery (5+ records above)
    for i in range(25, 35):
        records.append(_make_record(i, 12.0))

    dips = detect_dips(records, voltage_threshold=10.0)
    assert len(dips) == 1  # one continuous dip, not two


def test_multiple_dips():
    records = []
    # First dip
    for i in range(10):
        records.append(_make_record(i, 12.0))
    for i in range(10, 15):
        records.append(_make_record(i, 8.0))
    # Recovery (5+ records)
    for i in range(15, 25):
        records.append(_make_record(i, 12.0))
    # Second dip
    for i in range(25, 30):
        records.append(_make_record(i, 9.0))
    for i in range(30, 40):
        records.append(_make_record(i, 12.0))

    dips = detect_dips(records, voltage_threshold=10.0)
    assert len(dips) == 2
    assert abs(dips[0]["min_voltage"] - 8.0) < 0.01
    assert abs(dips[1]["min_voltage"] - 9.0) < 0.01


def test_implausible_voltage_filtered():
    """Records with voltage <= 1V or >= 16V should be skipped."""
    records = [_make_record(i, 0.5) for i in range(20)]
    dips = detect_dips(records, voltage_threshold=10.0)
    assert dips == []


def test_dip_tracks_peak_currents():
    """Peak per-channel currents should be tracked during a dip."""
    from conftest import make_rev_pd_data
    records = []
    for i in range(5):
        records.append(_make_record(i, 12.0))
    # Dip with current data
    pd1 = make_rev_pd_data(channel_currents={0: 30.0, 5: 10.0})
    pd2 = make_rev_pd_data(channel_currents={0: 50.0, 5: 20.0})
    records.append(_make_record(5, 8.0, pd_data=pd1))
    records.append(_make_record(6, 7.5, pd_data=pd2))
    for i in range(7, 15):
        records.append(_make_record(i, 12.0))

    dips = detect_dips(records, voltage_threshold=10.0)
    assert len(dips) == 1
    # Peak should be the max across dip records
    assert abs(dips[0]["peak_currents"][0] - 50.0) < 0.5
    assert abs(dips[0]["peak_currents"][5] - 20.0) < 0.5
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest power_analyzer/tests/test_dip_detector.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'dip_detector'`

- [ ] **Step 3: Implement `power_analyzer/dip_detector.py`**

```python
"""Detect voltage dips in dslog records and track per-channel peak currents."""

from pdh_decoder import decode_currents

RECORD_INTERVAL = 0.020  # 20ms between records (50 Hz)
DEBOUNCE_COUNT = 5        # 5 consecutive records above threshold = confirmed recovery (100ms)
VOLTAGE_MIN_PLAUSIBLE = 1.0   # below this, record is pre-connection garbage
VOLTAGE_MAX_PLAUSIBLE = 16.0  # above this, record is invalid


def _format_timestamp(record_index):
    """Format record index as relative timestamp: 'SSS.SSS' (7 chars, zero-padded, 3 decimals)."""
    seconds = record_index * RECORD_INTERVAL
    return f"{seconds:07.3f}"


def detect_dips(records, voltage_threshold=10.0):
    """Detect voltage dips and track per-channel peak currents during each dip.

    Args:
        records: list of record dicts from parse_dslog_records.
            Each must have: index, voltage, pd_type, pd_data.
        voltage_threshold: voltage below which a dip starts (default 10.0V).

    Returns:
        list of dip dicts, each containing:
            - start_index: record index where dip started
            - start_time: formatted timestamp string
            - end_index: record index where recovery confirmed (or None)
            - end_time: formatted timestamp string (or None)
            - min_voltage: minimum voltage during the dip
            - duration_s: dip duration in seconds (or None if didn't recover)
            - peak_currents: dict mapping channel -> peak amps during dip
            - recovered: bool
    """
    dips = []
    in_dip = False
    dip_start_index = 0
    min_voltage = 0.0
    peak_currents = {}
    recovery_streak = 0
    recovery_start_index = 0
    recovery_voltage = 0.0

    for rec in records:
        v = rec["voltage"]

        # Skip implausible voltage readings
        if v <= VOLTAGE_MIN_PLAUSIBLE or v >= VOLTAGE_MAX_PLAUSIBLE:
            continue

        if not in_dip:
            if v < voltage_threshold:
                # Dip starts
                in_dip = True
                dip_start_index = rec["index"]
                min_voltage = v
                peak_currents = {}
                recovery_streak = 0
                _update_peak_currents(peak_currents, rec)
        else:
            if v >= voltage_threshold:
                # Possible recovery
                if recovery_streak == 0:
                    recovery_start_index = rec["index"]
                    recovery_voltage = v
                recovery_streak += 1

                if recovery_streak >= DEBOUNCE_COUNT:
                    # Confirmed recovery
                    dips.append(_make_dip(
                        dip_start_index, recovery_start_index,
                        min_voltage, peak_currents, recovered=True,
                        recovery_voltage=recovery_voltage,
                    ))
                    in_dip = False
            else:
                # Still in dip (or bounce failed)
                recovery_streak = 0
                if v < min_voltage:
                    min_voltage = v
                _update_peak_currents(peak_currents, rec)

    # Dip that doesn't recover
    if in_dip:
        dips.append(_make_dip(
            dip_start_index, None, min_voltage, peak_currents, recovered=False,
        ))

    return dips


def _update_peak_currents(peak_currents, rec):
    """Update peak current tracking for a record during a dip."""
    currents = decode_currents(rec["pd_type"], rec["pd_data"])
    if currents is None:
        return
    for ch, amps in currents.items():
        if ch not in peak_currents or amps > peak_currents[ch]:
            peak_currents[ch] = amps


def _make_dip(start_index, end_index, min_voltage, peak_currents, recovered,
              recovery_voltage=None):
    """Construct a dip result dict."""
    start_time = _format_timestamp(start_index)
    end_time = _format_timestamp(end_index) if end_index is not None else None
    duration = None
    if end_index is not None:
        duration = round((end_index - start_index) * RECORD_INTERVAL, 3)

    return {
        "start_index": start_index,
        "start_time": start_time,
        "end_index": end_index,
        "end_time": end_time,
        "min_voltage": min_voltage,
        "duration_s": duration,
        "peak_currents": peak_currents,
        "recovered": recovered,
        "recovery_voltage": recovery_voltage,
    }
```

**frc-log-review checks applied:**
- Plausible voltage filter uses 1V lower bound (per spec, different from telemetry's 6V)
- 5-record debounce matches existing pattern in `dslog_processor.py`
- Recovery timestamp is the **first** record in the recovery streak
- Named constants for all thresholds and intervals

- [ ] **Step 4: Run dip detector tests**

```bash
uv run pytest power_analyzer/tests/test_dip_detector.py -v
```

Expected: all 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add power_analyzer/dip_detector.py power_analyzer/tests/test_dip_detector.py
git commit -m "feat: add voltage dip detection with debounced recovery

Detect voltage dips below configurable threshold, track per-channel
peak currents during each dip, and debounce recovery with 5 consecutive
records above threshold (100ms).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Robot Profile CSV Parser

Parse the channel-to-motor mapping CSV file that the user provides via `--profile`.

**Files:**
- Create: `power_analyzer/profile_parser.py`
- Create: `power_analyzer/tests/test_profile_parser.py`

- [ ] **Step 1: Write failing tests**

`power_analyzer/tests/test_profile_parser.py`:

```python
"""Tests for robot profile CSV parsing."""

import os
from conftest import make_profile_csv


def test_parse_profile_basic(tmp_path):
    from profile_parser import parse_profile
    path = tmp_path / "robot.csv"
    make_profile_csv([
        (0, 10, "Front Left Drive NEO"),
        (5, 15, "Front Right Drive NEO"),
        (9, 20, "Climber NEO"),
    ], str(path))
    profile = parse_profile(str(path))
    assert profile[0] == {"can_id": 10, "description": "Front Left Drive NEO"}
    assert profile[5] == {"can_id": 15, "description": "Front Right Drive NEO"}
    assert profile[9] == {"can_id": 20, "description": "Climber NEO"}
    assert 1 not in profile  # unmapped channels not present


def test_parse_profile_duplicate_uses_last(tmp_path):
    from profile_parser import parse_profile
    path = tmp_path / "robot.csv"
    make_profile_csv([
        (0, 10, "First"),
        (0, 11, "Second"),
    ], str(path))
    profile = parse_profile(str(path))
    assert profile[0]["can_id"] == 11


def test_parse_profile_skips_bad_rows(tmp_path):
    from profile_parser import parse_profile
    path = tmp_path / "robot.csv"
    with open(str(path), "w") as f:
        f.write("channel,can_id,description\n")
        f.write("0,10,Good Row\n")
        f.write("bad,10,Non-numeric channel\n")
        f.write("1\n")  # missing columns
        f.write("5,15,Another Good Row\n")
    profile = parse_profile(str(path))
    assert 0 in profile
    assert 5 in profile
    assert len(profile) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest power_analyzer/tests/test_profile_parser.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'profile_parser'`

- [ ] **Step 3: Implement `power_analyzer/profile_parser.py`**

```python
"""Parse robot profile CSV mapping PDH channels to motor descriptions."""

import csv


def parse_profile(filepath):
    """Parse a robot profile CSV file.

    Expected columns: channel, can_id, description.
    Rows with non-numeric channel or missing columns are skipped with a warning.
    Duplicate channel entries use the last one.

    Returns:
        dict mapping channel number (int) -> {"can_id": int, "description": str}
    """
    profile = {}
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                channel = int(row["channel"])
                can_id = int(row["can_id"])
                description = row["description"].strip()
            except (KeyError, ValueError, TypeError):
                print(f"  Warning: skipping invalid profile row: {row}")
                continue
            profile[channel] = {"can_id": can_id, "description": description}
    return profile
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest power_analyzer/tests/test_profile_parser.py -v
```

Expected: all 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add power_analyzer/profile_parser.py power_analyzer/tests/test_profile_parser.py
git commit -m "feat: add robot profile CSV parser for PDH channel mapping

Parse channel-to-motor CSV files. Skips invalid rows with warnings,
last entry wins for duplicate channels.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Report Formatters

Format the dip report and event log output files.

**Files:**
- Create: `power_analyzer/report_formatter.py`
- Create: `power_analyzer/tests/test_report_formatter.py`

- [ ] **Step 1: Write failing tests for dip report formatting**

`power_analyzer/tests/test_report_formatter.py`:

```python
"""Tests for dip report and event log formatting."""


def test_format_dip_report_no_dips():
    from report_formatter import format_dip_report
    result = format_dip_report(
        basename="2026_03_28 17_45_53 Sat",
        dips=[],
        profile={},
        voltage_threshold=10.0,
        current_threshold=1.0,
        profile_name="robot.csv",
    )
    assert "No voltage dips below 10.0V detected" in result
    assert "Summary:" in result


def test_format_dip_report_single_dip():
    from report_formatter import format_dip_report
    dip = {
        "start_index": 100,
        "start_time": "002.000",
        "end_index": 115,
        "end_time": "002.300",
        "min_voltage": 8.12,
        "duration_s": 0.3,
        "peak_currents": {0: 53.5, 5: 0.2, 14: 60.1},
        "recovered": True,
        "recovery_voltage": 11.2,
    }
    profile = {
        0: {"can_id": 10, "description": "Front Left Drive NEO"},
        14: {"can_id": 25, "description": "Shooter NEO"},
    }
    result = format_dip_report(
        basename="test",
        dips=[dip],
        profile=profile,
        voltage_threshold=10.0,
        current_threshold=1.0,
        profile_name="robot.csv",
    )
    assert "Dip 1 at 002.000s" in result
    assert "min 8.12V" in result
    assert "Front Left Drive NEO" in result
    assert "Shooter NEO" in result
    # Channel 5 at 0.2A is below 1.0A threshold — should NOT appear
    assert "Front Right" not in result
    assert "Recovered at 002.300s" in result
    assert "11.2V" in result
    assert "Summary: 1 dip" in result


def test_format_dip_report_unmapped_channel():
    from report_formatter import format_dip_report
    dip = {
        "start_index": 100,
        "start_time": "002.000",
        "end_index": 115,
        "end_time": "002.300",
        "min_voltage": 9.0,
        "duration_s": 0.3,
        "peak_currents": {7: 53.5},
        "recovered": True,
        "recovery_voltage": 10.5,
    }
    result = format_dip_report(
        basename="test", dips=[dip], profile={},
        voltage_threshold=10.0, current_threshold=1.0, profile_name="robot.csv",
    )
    assert "(unmapped)" in result
    assert "\u2014" in result or "—" in result  # em dash for missing CAN ID


def test_format_dip_report_no_recovery():
    from report_formatter import format_dip_report
    dip = {
        "start_index": 100,
        "start_time": "002.000",
        "end_index": None,
        "end_time": None,
        "min_voltage": 7.01,
        "duration_s": None,
        "peak_currents": {0: 50.0},
        "recovered": False,
    }
    result = format_dip_report(
        basename="test", dips=[dip], profile={0: {"can_id": 10, "description": "Motor"}},
        voltage_threshold=10.0, current_threshold=1.0, profile_name="robot.csv",
    )
    assert "did not recover" in result


def test_format_event_log_basic():
    from report_formatter import format_event_log
    events = [
        {"time": "000.000", "display": "FMS Connected"},
        {"time": "150.223", "display": "Code Start Notification"},
    ]
    transitions = [
        {"time": "563.360", "display": "***** Transition: Autonomous"},
    ]
    result = format_event_log(
        basename="2026_03_28 17_45_53 Sat",
        events=events,
        transitions=transitions,
    )
    assert "Event Log: 2026_03_28 17_45_53 Sat" in result
    assert "000.000  FMS Connected" in result
    assert "563.360  ***** Transition: Autonomous" in result


def test_format_event_log_sorted():
    from report_formatter import format_event_log
    events = [{"time": "200.000", "display": "Late event"}]
    transitions = [{"time": "100.000", "display": "***** Transition: Teleop"}]
    result = format_event_log(basename="test", events=events, transitions=transitions)
    lines = result.strip().split("\n")
    # Transition at 100s should come before event at 200s
    event_lines = [l for l in lines if l.strip() and not l.startswith("Event Log")]
    assert "100.000" in event_lines[0]
    assert "200.000" in event_lines[1]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest power_analyzer/tests/test_report_formatter.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'report_formatter'`

- [ ] **Step 3: Implement `power_analyzer/report_formatter.py`**

```python
"""Format dip report and event log output files."""


def format_dip_report(basename, dips, profile, voltage_threshold,
                      current_threshold, profile_name):
    """Format the voltage dip analysis report.

    Args:
        basename: log file basename for the header.
        dips: list of dip dicts from detect_dips.
        profile: dict from parse_profile (channel -> {can_id, description}).
        voltage_threshold: threshold used for detection.
        current_threshold: minimum peak current to show a channel row.
        profile_name: profile filename for the header.

    Returns:
        Formatted report string.
    """
    lines = []
    lines.append(f"Power Dip Analysis: {basename}")
    lines.append(f"Voltage Threshold: {voltage_threshold}V")
    lines.append(f"Current Threshold: {current_threshold}A")
    lines.append(f"Profile: {profile_name}")
    lines.append("")

    if not dips:
        lines.append(f"Summary: No voltage dips below {voltage_threshold}V detected.")
        lines.append("")
        return "\n".join(lines)

    lowest_voltage = min(d["min_voltage"] for d in dips)

    for i, dip in enumerate(dips, start=1):
        if dip["recovered"]:
            duration_str = f"lasted {dip['duration_s']:.1f}s"
        else:
            duration_str = "did not recover (log ended)"

        lines.append(f"=== Dip {i} at {dip['start_time']}s — min {dip['min_voltage']:.2f}V, {duration_str} ===")
        lines.append("")

        # Channel table
        if dip["peak_currents"]:
            _format_channel_table(lines, dip, profile, current_threshold)
        else:
            lines.append("  (No power distribution data available)")

        lines.append("")

        if dip["recovered"]:
            rv = dip.get("recovery_voltage")
            if rv is not None:
                lines.append(f"=== Recovered at {dip['end_time']}s — {rv:.1f}V ===")
            else:
                lines.append(f"=== Recovered at {dip['end_time']}s ===")
            lines.append("")

    lines.append(f"Summary: {len(dips)} dip{'s' if len(dips) != 1 else ''} detected, lowest voltage: {lowest_voltage:.2f}V")
    lines.append("")
    return "\n".join(lines)


def _format_channel_table(lines, dip, profile, current_threshold):
    """Format the per-channel current table for a single dip."""
    lines.append("  Ch  | Peak A | CAN ID | Description")
    lines.append("  ----|--------|--------|------------------")

    total_current = 0.0
    for ch in sorted(dip["peak_currents"].keys()):
        amps = dip["peak_currents"][ch]
        if amps < current_threshold:
            continue

        total_current += amps

        if ch in profile:
            can_str = str(profile[ch]["can_id"]).center(4)
            desc = profile[ch]["description"]
        else:
            can_str = " —  "
            desc = "(unmapped)"

        lines.append(f"  {ch:>3}  | {amps:>5.1f}  | {can_str} | {desc}")

    lines.append(f"  Total: {total_current:.1f} A @ {dip['min_voltage']:.2f}V")


def format_event_log(basename, events, transitions):
    """Format the chronological event log.

    Args:
        basename: log file basename for the header.
        events: list of event dicts from format_events (time, display).
        transitions: list of transition dicts from detect_transitions (time, display).

    Returns:
        Formatted event log string.
    """
    lines = []
    lines.append(f"Event Log: {basename}")
    lines.append("")

    # Merge and sort by timestamp
    merged = list(events) + list(transitions)
    merged.sort(key=lambda e: e["time"])

    for event in merged:
        lines.append(f"{event['time']}  {event['display']}")

    lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest power_analyzer/tests/test_report_formatter.py -v
```

Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add power_analyzer/report_formatter.py power_analyzer/tests/test_report_formatter.py
git commit -m "feat: add dip report and event log formatters

Format voltage dip analysis tables with per-channel currents and
chronological event log output. Supports unmapped channels, no-recovery
dips, and configurable current threshold filtering.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: CLI Entry Point

Wire everything together in `analyze_power.py`: argument parsing, file auto-pairing, orchestration, and file output.

**Files:**
- Create: `power_analyzer/analyze_power.py`
- Create: `power_analyzer/tests/test_analyze_power.py`

- [ ] **Step 1: Write failing integration tests**

`power_analyzer/tests/test_analyze_power.py`:

```python
"""Integration tests for power analyzer CLI."""

import os
import struct
from conftest import (
    make_rev_pd_data,
    make_dslog_record_with_pd,
    make_profile_csv,
    make_dsevents_file,
    LABVIEW_EPOCH_OFFSET,
)
from conftest import make_dslog_header


def _make_test_dslog(records_data, unix_timestamp=1774752353.0):
    """Build a dslog file with explicit record bytes."""
    header = make_dslog_header(unix_timestamp)
    return header + b"".join(records_data)


def _make_test_files(tmp_path, dslog_bytes, dsevents_bytes=None):
    """Write test dslog and optional dsevents files, return paths."""
    basename = "2026_03_28 17_45_53 Sat"
    dslog_path = tmp_path / f"{basename}.dslog"
    dslog_path.write_bytes(dslog_bytes)

    dsevents_path = None
    if dsevents_bytes is not None:
        dsevents_path = tmp_path / f"{basename}.dsevents"
        dsevents_path.write_bytes(dsevents_bytes)

    return str(dslog_path), str(dsevents_path) if dsevents_path else None


def test_cli_produces_dip_report(tmp_path):
    from analyze_power import run_analysis

    # Build dslog: 20 records at 12V, 10 records at 8V with current, 20 records at 12V
    pd_normal = make_rev_pd_data()
    pd_dip = make_rev_pd_data(channel_currents={0: 50.0, 14: 60.0})

    records = []
    for _ in range(20):
        records.append(make_dslog_record_with_pd(voltage_raw=3072, pd_data=pd_normal))  # 12V
    for _ in range(10):
        records.append(make_dslog_record_with_pd(voltage_raw=2048, pd_data=pd_dip))  # 8V
    for _ in range(20):
        records.append(make_dslog_record_with_pd(voltage_raw=3072, pd_data=pd_normal))  # 12V

    dslog_data = _make_test_dslog(records)
    dslog_path, _ = _make_test_files(tmp_path, dslog_data)

    profile_path = tmp_path / "robot.csv"
    make_profile_csv([
        (0, 10, "Front Left Drive NEO"),
        (14, 25, "Shooter NEO"),
    ], str(profile_path))

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    run_analysis(
        log_file=dslog_path,
        profile_path=str(profile_path),
        voltage_threshold=10.0,
        current_threshold=1.0,
        output_dir=str(output_dir),
    )

    dip_file = output_dir / "2026_03_28 17_45_53 Sat_dips.txt"
    assert dip_file.exists()
    content = dip_file.read_text()
    assert "Dip 1" in content
    assert "Front Left Drive NEO" in content
    assert "Shooter NEO" in content


def test_cli_produces_event_log_when_dsevents_exists(tmp_path):
    from analyze_power import run_analysis

    pd_data = make_rev_pd_data()
    records = [make_dslog_record_with_pd(voltage_raw=3072, pd_data=pd_data) for _ in range(10)]
    dslog_data = _make_test_dslog(records)
    dsevents_data = make_dsevents_file(["Code Start Notification"])

    dslog_path, dsevents_path = _make_test_files(tmp_path, dslog_data, dsevents_data)

    profile_path = tmp_path / "robot.csv"
    make_profile_csv([], str(profile_path))

    run_analysis(
        log_file=dslog_path,
        profile_path=str(profile_path),
        voltage_threshold=10.0,
        current_threshold=1.0,
        output_dir=str(tmp_path),
    )

    event_file = tmp_path / "2026_03_28 17_45_53 Sat_events.txt"
    assert event_file.exists()
    content = event_file.read_text()
    assert "Event Log:" in content


def test_cli_no_event_log_without_dsevents(tmp_path):
    from analyze_power import run_analysis

    pd_data = make_rev_pd_data()
    records = [make_dslog_record_with_pd(voltage_raw=3072, pd_data=pd_data) for _ in range(10)]
    dslog_data = _make_test_dslog(records)
    dslog_path, _ = _make_test_files(tmp_path, dslog_data)

    profile_path = tmp_path / "robot.csv"
    make_profile_csv([], str(profile_path))

    run_analysis(
        log_file=dslog_path,
        profile_path=str(profile_path),
        voltage_threshold=10.0,
        current_threshold=1.0,
        output_dir=str(tmp_path),
    )

    event_file = tmp_path / "2026_03_28 17_45_53 Sat_events.txt"
    assert not event_file.exists()


def test_cli_no_dips_report(tmp_path):
    from analyze_power import run_analysis

    pd_data = make_rev_pd_data()
    records = [make_dslog_record_with_pd(voltage_raw=3072, pd_data=pd_data) for _ in range(50)]
    dslog_data = _make_test_dslog(records)
    dslog_path, _ = _make_test_files(tmp_path, dslog_data)

    profile_path = tmp_path / "robot.csv"
    make_profile_csv([], str(profile_path))

    run_analysis(
        log_file=dslog_path,
        profile_path=str(profile_path),
        voltage_threshold=10.0,
        current_threshold=1.0,
        output_dir=str(tmp_path),
    )

    dip_file = tmp_path / "2026_03_28 17_45_53 Sat_dips.txt"
    assert dip_file.exists()
    content = dip_file.read_text()
    assert "No voltage dips" in content
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest power_analyzer/tests/test_analyze_power.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'analyze_power'`

- [ ] **Step 3: Implement `power_analyzer/analyze_power.py`**

```python
#!/usr/bin/env python3
"""Power Analyzer — detect voltage dips and report per-channel PDH currents."""

import argparse
import os
import sys

from shared.dslog_parser import parse_dslog_records
from shared.dsevents_parser import parse_dsevents_path
from shared.event_formatter import format_events
from dslog_processor import detect_transitions
from dip_detector import detect_dips
from profile_parser import parse_profile
from report_formatter import format_dip_report, format_event_log


def find_paired_file(log_path):
    """Find the paired .dslog/.dsevents file by swapping the extension.

    Returns:
        tuple (dslog_path, dsevents_path). dsevents_path may be None.
        Raises SystemExit if dslog is missing.
    """
    base, ext = os.path.splitext(log_path)
    ext_lower = ext.lower()

    if ext_lower == ".dslog":
        dslog_path = log_path
        dsevents_path = base + ".dsevents"
    elif ext_lower == ".dsevents":
        dslog_path = base + ".dslog"
        dsevents_path = log_path
    else:
        print(f"Error: Expected .dslog or .dsevents file, got: {ext}")
        sys.exit(1)

    if not os.path.exists(dslog_path):
        print(f"Error: .dslog file not found: {dslog_path}")
        sys.exit(1)

    if not os.path.exists(dsevents_path):
        print(f"  Warning: No .dsevents file found at {dsevents_path}")
        dsevents_path = None

    return dslog_path, dsevents_path


def run_analysis(log_file, profile_path, voltage_threshold=10.0,
                 current_threshold=1.0, output_dir=None):
    """Run the full power analysis pipeline.

    Args:
        log_file: path to .dslog or .dsevents file.
        profile_path: path to robot profile CSV.
        voltage_threshold: voltage dip threshold in volts.
        current_threshold: minimum peak current for channel table rows.
        output_dir: output directory (default: same dir as log_file).
    """
    dslog_path, dsevents_path = find_paired_file(log_file)
    profile = parse_profile(profile_path)

    if output_dir is None:
        output_dir = os.path.dirname(dslog_path)

    basename = os.path.splitext(os.path.basename(dslog_path))[0]
    profile_name = os.path.basename(profile_path)

    # Parse dslog
    with open(dslog_path, "rb") as f:
        dslog_data = f.read()

    records = list(parse_dslog_records(dslog_data))
    if not records:
        print("  Warning: No valid dslog records found.")

    # Detect dips
    dips = detect_dips(records, voltage_threshold=voltage_threshold)

    # Write dip report
    report = format_dip_report(
        basename=basename,
        dips=dips,
        profile=profile,
        voltage_threshold=voltage_threshold,
        current_threshold=current_threshold,
        profile_name=profile_name,
    )
    dip_path = os.path.join(output_dir, f"{basename}_dips.txt")
    with open(dip_path, "w") as f:
        f.write(report)
    print(f"  Dip report: {dip_path}")

    # Write event log (only if dsevents exists)
    if dsevents_path is not None:
        parsed_events = parse_dsevents_path(dsevents_path)
        formatted_events = format_events(parsed_events)
        transitions = detect_transitions(records)
        event_log = format_event_log(
            basename=basename,
            events=formatted_events,
            transitions=transitions,
        )
        event_path = os.path.join(output_dir, f"{basename}_events.txt")
        with open(event_path, "w") as f:
            f.write(event_log)
        print(f"  Event log: {event_path}")

    # Summary
    if dips:
        lowest = min(d["min_voltage"] for d in dips)
        print(f"  {len(dips)} voltage dip{'s' if len(dips) != 1 else ''} detected (lowest: {lowest:.2f}V)")
    else:
        print(f"  No voltage dips below {voltage_threshold}V detected.")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze FRC .dslog files for voltage dips and per-channel PDH currents."
    )
    parser.add_argument("log_file",
                        help="Path to a .dslog or .dsevents file. "
                             "The paired file is auto-detected.")
    parser.add_argument("--profile", required=True,
                        help="Path to robot profile CSV mapping PDH channels to motors.")
    parser.add_argument("--voltage-threshold", type=float, default=10.0,
                        help="Voltage below which a dip is reported (default: 10.0V)")
    parser.add_argument("--current-threshold", type=float, default=1.0,
                        help="Minimum peak current to include in table (default: 1.0A)")
    parser.add_argument("--output-dir",
                        help="Output directory (default: same as input file)")

    args = parser.parse_args()

    if not os.path.exists(args.log_file):
        print(f"Error: File not found: {args.log_file}")
        sys.exit(1)
    if not os.path.exists(args.profile):
        print(f"Error: Profile file not found: {args.profile}")
        sys.exit(1)
    if args.output_dir and not os.path.isdir(args.output_dir):
        print(f"Error: Output directory does not exist: {args.output_dir}")
        sys.exit(1)

    run_analysis(
        log_file=args.log_file,
        profile_path=args.profile,
        voltage_threshold=args.voltage_threshold,
        current_threshold=args.current_threshold,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run integration tests**

```bash
uv run pytest power_analyzer/tests/test_analyze_power.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest -v
```

Expected: all tests pass across both `match_processor/tests/` and `power_analyzer/tests/`.

- [ ] **Step 6: Commit**

```bash
git add power_analyzer/analyze_power.py power_analyzer/tests/test_analyze_power.py
git commit -m "feat: add power analyzer CLI entry point

Wire together dslog parsing, dip detection, PDH decoding, profile parsing,
and report formatting. Auto-pairs .dslog/.dsevents files, produces dip
report and optional event log.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Manual Smoke Test with Real Data

Verify the tool works against real FRC log files from this repo.

**Files:**
- No files created or modified

- [ ] **Step 1: Create a test profile CSV**

```bash
cat > /tmp/test_profile.csv << 'EOF'
channel,can_id,description
0,10,Front Left Drive NEO
1,11,Front Left Turn NEO 550
5,15,Front Right Drive NEO
9,20,Climber NEO
13,24,Intake NEO
14,25,Shooter NEO
EOF
```

- [ ] **Step 2: Run against a real log file**

Pick one of the log files from `2026/03/`:

```bash
ls 2026/03/*.dslog | head -3
```

Run the analyzer:

```bash
uv run python power_analyzer/analyze_power.py "2026/03/<pick_a_file>.dslog" --profile /tmp/test_profile.csv --output-dir /tmp/power_output
```

- [ ] **Step 3: Inspect the output**

```bash
cat /tmp/power_output/*_dips.txt
cat /tmp/power_output/*_events.txt
```

Verify:
- Dip report has correct header fields
- If dips exist, channel table is formatted correctly
- Event log has chronological entries with mode transitions
- Timestamps look plausible (not in the 2060s — would indicate epoch bug)

- [ ] **Step 4: Verify `--help` works**

```bash
uv run python power_analyzer/analyze_power.py --help
```

Expected: clean help output with all arguments listed.

---

### Task 9: Update pyproject.toml and README

Update project configuration and documentation to include the power analyzer.

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md`

- [ ] **Step 1: Verify final `pyproject.toml` state**

The `pyproject.toml` should already have `shared` and `power_analyzer` in `pythonpath` and both test directories in `testpaths` from earlier tasks. Verify:

```toml
[tool.pytest.ini_options]
pythonpath = [".", "match_processor", "shared", "power_analyzer"]
testpaths = ["shared/tests", "match_processor/tests", "power_analyzer/tests"]
```

- [ ] **Step 2: Add Power Analyzer section to README.md**

Add a new section after the existing Match Log Processor section. Follow the same style (student-friendly, practical):

```markdown
## Power Analyzer

Analyzes `.dslog` files to find voltage dips (potential brownouts) and shows which motors were drawing the most current during each dip. Useful for figuring out which mechanisms are overloading your battery.

### Usage

```bash
python3 power_analyzer/analyze_power.py <log_file> --profile <robot_profile.csv> [options]
```

| Option | Description |
|--------|-------------|
| `log_file` | Path to a `.dslog` or `.dsevents` file (the paired file is auto-detected) |
| `--profile <path>` | **Required.** CSV file mapping PDH channels to motor descriptions |
| `--voltage-threshold <V>` | Voltage below which a dip is reported (default: 10.0V) |
| `--current-threshold <A>` | Minimum peak current to show in the table (default: 1.0A) |
| `--output-dir <path>` | Output directory (default: same as input file) |

### Robot Profile CSV

Create a CSV file that maps your PDH channels to your robot's motors:

```csv
channel,can_id,description
0,10,Front Left Drive NEO
1,11,Front Left Turn NEO 550
9,20,Climber NEO
14,25,Shooter NEO
```

### Example

```bash
python3 power_analyzer/analyze_power.py "2026/03/2026_03_28 17_45_53 Sat.dslog" --profile robot.csv
```
```

- [ ] **Step 3: Run full test suite one final time**

```bash
uv run pytest -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml README.md
git commit -m "docs: add power analyzer to README and finalize project config

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

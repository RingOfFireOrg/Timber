# dslog Parsing — Transitions and Telemetry Design Spec

**Status:** COMPLETE — Implemented 2026-04-01. 89 tests passing.

## Overview

Parse `.dslog` binary files to extract robot mode transitions (Autonomous, Teleop, Disabled, Disconnected) and telemetry summary (voltage, CPU, CAN, trip time, packet loss). Transition events are interleaved chronologically with existing `.dsevents` events in the Events section. A new Telemetry section shows whole-match min/max values.

## dslog Binary Format (DS Version 26.0)

Based on AdvantageScope's parser (`src/hub/dataSources/dslog/DSLogReader.ts`), the actual format differs from community documentation:

### Header: 20 bytes

| Offset | Size | Type | Description |
|--------|------|------|-------------|
| 0 | 4 | int32 (BE) | Version (expected: 4) |
| 4 | 8 | int64 (BE) | LabVIEW epoch seconds |
| 12 | 8 | uint64 (BE) | LabVIEW epoch fractional |

LabVIEW epoch offset: `-2082826800` seconds (1904-01-01 to Unix epoch).

### Records: Variable-length

Each record has a 10-byte fixed section, a 4-byte power distribution header, and variable-length PD data.

**Fixed section (10 bytes):**

| Offset | Size | Type | Field | Conversion |
|--------|------|------|-------|------------|
| 0 | 1 | uint8 | Trip time | × 0.5 = ms |
| 1 | 1 | int8 | Packet loss | × 4 × 0.01, clamp [0, 1] |
| 2 | 2 | uint16 (BE) | Battery voltage | ÷ 256 = volts |
| 4 | 1 | uint8 | CPU utilization | × 0.5 × 0.01 = fraction |
| 5 | 1 | uint8 | Status mask | See below |
| 6 | 1 | uint8 | CAN utilization | × 0.5 × 0.01 = fraction |
| 7 | 1 | uint8 | WiFi signal | × 0.5 = dB |
| 8 | 2 | uint16 (BE) | WiFi bandwidth | ÷ 256 = MB/s |

**Status mask (byte 5) — inverted logic (0 = active):**

| Bit | Meaning (when bit is 0) |
|-----|------------------------|
| 7 | Brownout |
| 6 | Watchdog |
| 5 | DS Teleop |
| 4 | (unused/reserved) |
| 3 | DS Disabled |
| 2 | Robot Teleop |
| 1 | Robot Autonomous |
| 0 | Robot Disabled |

**Power distribution header (4 bytes):**

The first 3 bytes of the PD header are opaque metadata (not parsed). Byte 3 identifies the PD type:
- `33` (0x21) = REV PDH → 33 additional bytes (1 CAN ID + 27 booleans + 4 extra channels + 1 temperature)
- `25` (0x19) = CTRE PDP → 25 additional bytes (1 CAN ID + 21 data + 3 metadata)
- Other = None → 0 additional bytes

**Total record size:** 14 bytes (no PD), 47 bytes (REV), 39 bytes (CTRE).

### Record Timing

Records are written at 20ms intervals (50 Hz). Record timestamp = header timestamp + (record_index × 0.020).

### Error Handling

- **Unsupported version**: If the version is not 4, print a warning and return empty results (no transitions, no telemetry). Do not raise an exception — the match can still be processed using dsevents data alone.
- **Truncated header**: If the file is shorter than 20 bytes, print a warning and return empty results.
- **Truncated record**: If fewer bytes remain than needed for the next record (based on the 10-byte fixed section + 4-byte PD header + PD data), stop iteration and return what was parsed so far. Do not raise an exception.
- **Unknown PD type**: Treat as `None` (0 additional bytes). This may cause subsequent records to be misaligned, so print a warning and stop iteration.

## Robot Mode Determination

From the status mask, determine robot mode using this priority:
1. Robot Autonomous (bit 1 == 0) → `Autonomous`
2. Robot Teleop (bit 2 == 0) → `Teleop`
3. Robot Disabled (bit 0 == 0) → `Disabled`
4. None of the above → `Disconnected`

## Transition Detection

### Debouncing

Raw status flags flicker at the 20ms record rate — a single record in a different mode is noise, not a real transition. Apply debouncing:

- A mode transition is confirmed when 5 consecutive records (100ms) report the same new mode.
- The transition timestamp is the **first** record in the new mode (not the 5th confirming record).
- The initial mode (record 0) requires no debouncing.

### Output

Each confirmed transition produces an event dict:

```python
{"time": "563.360", "display": "***** Transition: Autonomous"}
```

These are merged into the existing events list and sorted chronologically with dsevents events.

## Telemetry Summary

Compute whole-match min and max for all records with plausible voltage (6.0 < V < 16.0):

- **Voltage** (V) — min and max
- **CPU** (%) — min and max
- **CAN Utilization** (%) — min and max
- **Trip Time** (ms) — min and max
- **Packet Loss** (%) — min and max

Records with voltage outside 6-16V are excluded (pre-connection garbage data).

### Output Format

```
Telemetry:
  Voltage: 7.43 - 12.71 V
  CPU: 0 - 67%
  CAN Utilization: 0 - 100%
  Trip Time: 0.0 - 11.0 ms
  Packet Loss: 0 - 40%
```

If no records have valid voltage (non-participation match), the Telemetry section shows:

```
Telemetry:
  No telemetry data available.
```

## Updated `match_events.txt` Section Order

The Joysticks and Telemetry sections move **before** Events to provide summary context before the detailed timeline.

### Normal match

```
Match: Qualification 39
Event: 2026ncpem
Field Time: 26/3/28 21:45:53
DS Version: FRC Driver Station - Version 26.0
Replay: 1
The Blue Alliance: https://www.thebluealliance.com/match/2026ncpem_qm39

Log Files:
  [1] 2026_03_28 17_45_53 Sat (Q39_1_)

Joysticks:
  0: Controller (Xbox One For Windows) - 6 axes, 16 buttons, 1 POV

Telemetry:
  Voltage: 7.43 - 12.71 V
  CPU: 0 - 67%
  CAN Utilization: 0 - 100%
  Trip Time: 0.0 - 11.0 ms
  Packet Loss: 0 - 40%

Events:
  [1] 000.000  FMS Connected
  [1] 001.000  Code Start Notification
  [1] 006.082  ERROR (44003): FRC: No robot code is currently running.
  [1] 563.360  ***** Transition: Autonomous
  [1] 584.860  ***** Transition: Disabled
  [1] 588.220  ***** Transition: Teleop
  [1] 728.040  ***** Transition: Disabled
```

### Non-participation match

```
Match: Elimination 3
...
The Blue Alliance: https://www.thebluealliance.com/match/2026ncpem_sf3m1

NOTE: The robot does not appear to have participated in this match.

Log Files:
  [1] 2026_03_29 13_41_30 Sun (E3_R1_1_)

Joysticks:

Telemetry:
  No telemetry data available.

Events:
  [1] 000.418  ERROR (44004): FRC: The Driver Station has lost communication with the robot.
  [1] 000.619  FMS Connected
```

## Relative Timestamps for Transition Events

Transition events use the same relative timestamp format as dsevents: seconds since the dslog file header timestamp, formatted as `f"{seconds:07.3f}"` (7 chars, zero-padded, 3 decimal places).

For multi-log matches (robot restarts), each dslog file is parsed independently. Transition timestamps are relative to that log file's header, matching how dsevents timestamps work.

## Files Changed

| File | Role | Change |
|------|------|--------|
| `match_processor/dslog_parser.py` | **New** — dslog binary parser | Parse header, iterate variable-length records, extract telemetry fields and status flags |
| `match_processor/dslog_processor.py` | **New** — transition detection and telemetry summary | Debounced mode transitions, min/max telemetry computation |
| `match_processor/match_writer.py` | Match output formatting | Add Telemetry section, reorder Joysticks before Events, merge transition events chronologically |
| `match_processor/process_matches.py` | CLI entry point | Parse dslog files alongside dsevents, pass dslog data to writer |
| `match_processor/tests/test_dslog_parser.py` | **New** — parser unit tests | Header parsing, record iteration, status mask decoding, PD type handling, truncated files |
| `match_processor/tests/test_dslog_processor.py` | **New** — processor unit tests | Debounce logic, telemetry aggregation, edge cases |
| `match_processor/tests/test_match_writer.py` | Writer tests | Update for new section order, telemetry section, transition events in output |
| `match_processor/tests/test_integration.py` | Integration tests | End-to-end with dslog data |
| `.claude/skills/references/frc-log-formats.md` | Format reference | Update dslog section with correct v4 format |

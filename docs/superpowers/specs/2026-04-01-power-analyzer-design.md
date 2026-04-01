# Power Analyzer — Design Spec

**Status:** APPROVED — Reviewed 2026-04-01.

## Overview

A standalone CLI tool that analyzes FRC Driver Station `.dslog` files to detect battery voltage dips and report which PDH channels (motors/mechanisms) were drawing the most current during each dip. Helps FRC students identify what's causing brownout risk. Works on any log file — match or practice — so teams can compare runs.

Produces two output files:
1. **Dip report** — one block per voltage dip showing peak per-channel currents and min voltage
2. **Event log** — raw chronological dump of all dsevents + mode transitions for cross-referencing timestamps

## Directory Structure

Shared parsers are extracted from `match_processor/` into a new `shared/` directory so both tools can use them:

```
shared/
  __init__.py
  dslog_parser.py        # moved from match_processor/
  dsevents_parser.py     # moved from match_processor/
  event_formatter.py     # moved from match_processor/

match_processor/
  dslog_processor.py     # stays (match-specific: transitions, telemetry)
  match_identifier.py    # stays
  match_writer.py        # stays
  process_matches.py     # updated imports: from shared.* import ...
  tests/

power_analyzer/
  analyze_power.py       # CLI entry point
  pdh_decoder.py         # REV/CTRE channel current decoding
  dip_detector.py        # voltage dip detection logic
  tests/
```

All existing `match_processor/` imports update from `from dslog_parser import ...` to `from shared.dslog_parser import ...`. Tests update accordingly.

## CLI Interface

```bash
python3 power_analyzer/analyze_power.py <log_file> [options]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `log_file` | Yes | Path to a `.dslog` or `.dsevents` file. The script auto-finds the paired file by swapping the extension. |
| `--profile <path>` | Yes | CSV file mapping PDH channels to CAN IDs and descriptions. |
| `--voltage-threshold <V>` | No | Voltage below which a dip is reported. Default: `10.0`. |
| `--current-threshold <A>` | No | Minimum peak current (amps) to include a channel row in the table. Default: `1.0`. |
| `--output-dir <path>` | No | Directory for output files. Default: same directory as input file. |

**Output files** (auto-named from input basename):
- `<basename>_dips.txt`
- `<basename>_events.txt`

**Auto-pairing:** Given either a `.dslog` or `.dsevents` path, the script locates the paired file by replacing the extension. If the `.dsevents` pair is missing, the dip report is still produced but no event log file is written (a warning is printed). If the `.dslog` is missing, the script exits with an error (no power data to analyze).

**Error on missing profile:** The `--profile` flag is required. The script exits with an error message if not provided.

## Robot Profile CSV

Maps PDH channels to CAN IDs and human-readable motor/mechanism descriptions.

```csv
channel,can_id,description
0,10,Front Left Drive NEO
1,11,Front Left Turn NEO 550
5,15,Front Right Drive NEO
9,20,Climber NEO
13,24,Intake NEO
14,25,Shooter NEO
```

- **channel**: PDH channel number (0-23, where 0-19 are main channels and 20-23 are extra/switchable channels)
- **can_id**: CAN bus ID of the device on that channel
- **description**: Human-readable label (e.g., "Climber Neo")

The CSV is parsed with Python's `csv` module. Rows with missing columns or non-numeric `channel` values are skipped with a warning. Duplicate channel entries use the last one.

Channels not listed in the profile appear in dip tables as `(unmapped)` with `—` for CAN ID:

```
  Ch  | Peak A | CAN ID | Description
   7  |  53.5  |   —    | (unmapped)
```

## dslog_parser.py Changes

The existing `parse_dslog_records` yields record dicts with `voltage`, `cpu`, `can`, `trip_ms`, `packet_loss`, and `mode` — but discards the raw PD bytes. The power analyzer needs those bytes to decode per-channel currents.

**Change:** Add two fields to each yielded record dict:
- `pd_type`: the PD type byte (0x21 for REV, 0x19 for CTRE, 0x00 for none)
- `pd_data`: raw bytes of the PD data section (33 bytes for REV, 25 bytes for CTRE, 0 bytes for none) — includes CAN ID byte and all subsequent bytes

This is backward-compatible — existing consumers (match_processor) ignore the new fields. The `pdh_decoder.py` module consumes `pd_type` and `pd_data` to extract per-channel currents.

## REV PDH Channel Current Decoding

Based on AdvantageScope's `DSLogReader.ts`. The 33-byte REV PDH data section is structured as:

| Offset | Size | Description |
|--------|------|-------------|
| 0 | 1 | CAN ID |
| 1-27 | 27 | Boolean array (216 bits) encoding 20 main channel currents |
| 28-31 | 4 | Extra channel currents (1 byte each) |
| 32 | 1 | Temperature data (not used) |

### Main channels (0-19)

The 27 bytes are treated as a flat boolean (bit) array, LSB-first per byte. Each channel's current is a 10-bit value packed with a stride pattern:

```
read_position = (channel // 3) * 32 + (channel % 3) * 10
```

The 10 bits starting at `read_position` are assembled LSB-first into an integer, then divided by 8 to get amps.

### Extra channels (20-23)

Four bytes at offsets 28-31. Each byte divided by 16 gives amps.

### CTRE PDP (25-byte PD section)

Similar boolean-packed scheme but with **16 channels only** (no extra channels). Offset 0 is CAN ID, bytes 1-21 are boolean array (168 bits), remaining 3 bytes are metadata.

Each channel's current is a 10-bit value at:
```
read_position = (channel // 6) * 64 + (channel % 6) * 10
```

Assembled LSB-first, divided by 8 for amps.

CTRE PDP only has channels 0-15. Profile entries referencing channels 16+ are ignored for CTRE robots.

### No PD

If PD type is neither REV nor CTRE, no channel currents are available. The dip report notes this:
```
  (No power distribution data available)
```

## Voltage Dip Detection

### Algorithm

1. Iterate through dslog records with plausible voltage (1V < V < 16V). Note: this lower bound (1V) differs from `compute_telemetry` (6V) because we need to see and report on deep voltage dips, not exclude them.
2. **Dip starts** when voltage drops below threshold (default 10V).
3. During the dip, track per-channel **peak current** and **minimum voltage**.
4. **Dip ends** when voltage recovers above threshold for **5 consecutive records** (100ms debounce). The recovery timestamp is the first record in the recovery streak.
5. If the log ends during a dip, report it with "did not recover."
6. The dip timestamp is the **first record** below threshold.

### Debouncing

Same pattern as mode transition detection: 5 consecutive records (100ms at 50Hz) required to confirm recovery. This prevents brief voltage bounces at the threshold from splitting one dip into multiple reports.

## Dip Report Output Format

### File: `<basename>_dips.txt`

```
Power Dip Analysis: 2026_03_28 17_45_53 Sat
Voltage Threshold: 10.0V
Current Threshold: 1.0A
Profile: robot.csv

=== Dip 1 at 588.340s — min 8.12V, lasted 2.3s ===

  Ch  | Peak A | CAN ID | Description
  ----|--------|--------|------------------
   0  |  53.5  |   10   | Front Left Drive NEO
   9  |  51.6  |   20   | Climber NEO
  14  |  60.1  |   25   | Shooter NEO
  Total: 165.2 A @ 8.12V

=== Recovered at 590.640s — 11.2V ===

=== Dip 2 at 724.100s — min 9.41V, lasted 0.8s ===

  Ch  | Peak A | CAN ID | Description
  ----|--------|--------|------------------
  13  |  42.6  |   24   | Intake NEO
  Total: 42.6 A @ 9.41V

=== Recovered at 724.900s — 10.8V ===

Summary: 2 dips detected, lowest voltage: 8.12V
```

### Table rules

- Only channels with peak current >= current threshold (default 1.0A) are included as rows.
- Channels not in the profile show CAN ID as `—` and description as `(unmapped)`.
- **Total** line sums peak currents of displayed rows and shows the minimum voltage during the dip.
- Channels sorted by channel number.

### No dips detected

```
Power Dip Analysis: 2026_03_28 17_45_53 Sat
Voltage Threshold: 10.0V
Current Threshold: 1.0A
Profile: robot.csv

Summary: No voltage dips below 10.0V detected.
```

### Dip that doesn't recover

```
=== Dip 3 at 728.040s — min 7.01V, did not recover (log ended) ===

  Ch  | Peak A | CAN ID | Description
  ----|--------|--------|------------------
  ...
  Total: 200.1 A @ 7.01V
```

## Event Log Output Format

### File: `<basename>_events.txt`

A raw chronological dump of all events from the `.dsevents` file, plus mode transitions from the `.dslog`, merged and sorted by timestamp. No filtering, no collapsing repeats.

```
Event Log: 2026_03_28 17_45_53 Sat

000.000  FMS Connected
001.251  ERROR (44002): Ping Results: link-bad, DS radio(.4)-GOOD, ...
150.223  Code Start Notification
150.223  Code Start Notification
150.695  [phoenix] Signal Logger Started (Network: rio)
150.695  WARNING (2): [Spark Max] IDs: 43, timed out while waiting for Period Status 2
159.980  ***** Transition: Disabled
563.360  ***** Transition: Autonomous
584.860  ***** Transition: Disabled
588.220  ***** Transition: Teleop
728.040  ***** Transition: Disabled
```

Timestamps are seconds from the dslog header timestamp, formatted as `SSS.SSS` (zero-padded, 3 decimal places). This matches the dip report timestamps for easy cross-referencing.

Mode transitions include the initial mode (record 0) since this is a raw log, not a match summary.

If no `.dsevents` file is paired, the event log contains only mode transitions from the `.dslog`.

## Files Changed

| File | Role | Change |
|------|------|--------|
| `shared/__init__.py` | **New** — package marker | Empty init |
| `shared/dslog_parser.py` | **Moved** from `match_processor/` | Add `pd_type` and `pd_data` (raw bytes) to yielded record dicts |
| `shared/dsevents_parser.py` | **Moved** from `match_processor/` | No code changes |
| `shared/event_formatter.py` | **Moved** from `match_processor/` | No code changes |
| `match_processor/process_matches.py` | Import path update | `from shared.dslog_parser import ...` etc. |
| `match_processor/dslog_processor.py` | Import path update | `from shared.dslog_parser import ...` |
| `match_processor/tests/*` | Import path updates | Update imports for shared modules |
| `power_analyzer/__init__.py` | **New** — package marker | Empty init |
| `power_analyzer/analyze_power.py` | **New** — CLI entry point | Argument parsing, file pairing, orchestration |
| `power_analyzer/pdh_decoder.py` | **New** — PDH current decoding | REV and CTRE channel current extraction |
| `power_analyzer/dip_detector.py` | **New** — voltage dip detection | Dip detection with debounced recovery |
| `power_analyzer/tests/` | **New** — power analyzer tests | Unit and integration tests |

# FRC Match Log Processor — Design Spec

## Overview

A Python script (`process_matches.py`) that identifies FRC match log files (`.dsevents` and `.dslog`), extracts match information, writes a human-readable match events file, and copies everything to a designated match folder for committing to GitHub.

## Usage

```
python3 process_matches.py <source_dir> <dest_dir>
python3 process_matches.py <source_dir> <dest_dir> --today
python3 process_matches.py <source_dir> <dest_dir> --date 2026-03-29
```

- **Default:** Scans all `.dsevents` files in `source_dir` (non-recursive, single directory only).
- **`--today`:** Scans only files with today's date in the filename.
- **`--date YYYY-MM-DD`:** Scans only files matching the specified date.
- **`--today` and `--date` are mutually exclusive.**
- **`-h` / `--help`:** Print usage information (provided by `argparse`).

### Date Filtering

Filenames follow the pattern `YYYY_MM_DD HH_MM_SS Day.dsevents`. Date filtering matches the `YYYY_MM_DD` prefix of the filename against the target date formatted as `YYYY_MM_DD`. Files whose names do not match the expected `YYYY_MM_DD ...` pattern are skipped when date filtering is active.

## Dependencies

Python 3 standard library only: `struct`, `os`, `shutil`, `sys`, `datetime`, `argparse`, `re`.

## Workflow

1. Scan `source_dir` for `.dsevents` files (non-recursive), optionally filtered by date.
2. Parse each file's event records to find the `FMS Connected:` line. This is typically within the first few records but is not guaranteed to be the first.
3. Filter to real matches only — skip files where match type is `None` or FMS data is absent.
4. Group files by the full FMS match key (`<MatchType> - <Number>:<Replay>`, e.g., `Qualification - 52:1`) to detect robot restarts. Multiple files with the same key represent robot restarts within one match play.
5. Check `dest_dir` for existing match prefixes (e.g., `Q52_`, `E6_R1_`). Skip matches already present.
6. Display new matches with groupings and ask for user confirmation.
7. For each confirmed match:
   - Copy `.dsevents` and `.dslog` pairs with match prefix.
   - Write a `match_events.txt` summary file.

### Missing `.dslog` Pair

If a `.dsevents` file has no matching `.dslog` file (same base filename), print a warning and skip that file. Vice versa: orphan `.dslog` files without a `.dsevents` partner are ignored.

## File Naming

Files are named with a match prefix, sequence number, and original filename:

```
<match_id>_<seq>_<original_filename>
```

Examples:

| Match | Files |
|-------|-------|
| Qualification 52, single log pair | `Q52_match_events.txt`, `Q52_1_2026_03_29 09_34_29 Sun.dsevents`, `Q52_1_2026_03_29 09_34_29 Sun.dslog` |
| Qualification 52, robot restarted (2 pairs) | `Q52_match_events.txt`, `Q52_1_2026_03_29 09_34_29 Sun.dsevents`, `Q52_1_2026_03_29 09_34_29 Sun.dslog`, `Q52_2_2026_03_29 09_40_12 Sun.dsevents`, `Q52_2_2026_03_29 09_40_12 Sun.dslog` |
| Elimination 6 replay 1 | `E6_R1_match_events.txt`, `E6_R1_1_2026_03_29 14_10_33 Sun.dsevents`, `E6_R1_1_2026_03_29 14_10_33 Sun.dslog` |

Sequence number `_1_` is always present, even when there is only one log pair.

### Sequence Number Assignment

Sequence numbers are assigned in chronological order based on the LabView timestamp in the file header. The earliest file is `_1_`, the next `_2_`, etc.

## Match ID Construction

From the FMS Connected string `<MatchType> - <Number>:<Replay>`:

Replay values in FMS data are always >= 1. Replay 1 means the original play. Replay 2 means the match was replayed once (e.g., due to a field fault).

- **Qualification:** `Q<number>` when replay is 1 (e.g., `Q52`). If replay > 1: `Q<number>_R<replay>` (e.g., `Q52_R2`).
- **Elimination:** `E<number>_R<replay>` always includes the replay number (e.g., `E6_R1`).

## Duplicate Detection

Before processing, the tool checks `dest_dir` for files starting with the match prefix (e.g., `Q52_`). If any exist, that match is skipped. This makes the tool idempotent — safe to run multiple times during a competition weekend.

## `.dsevents` Binary Format

### Header (20 bytes, big-endian)

| Offset | Size | Type | Field |
|--------|------|------|-------|
| 0 | 4 | int32 | Version (current: 4) |
| 4 | 8 | int64 | LabView timestamp seconds (epoch: 1904-01-01) |
| 12 | 8 | uint64 | LabView timestamp fractional |

### Event Records (sequential, variable length)

| Field | Size | Type | Description |
|-------|------|------|-------------|
| Timestamp high | 8 | int64 | LabView seconds |
| Timestamp low | 8 | uint64 | LabView fractional |
| Text length | 4 | int32 | Byte length of text payload |
| Text data | variable | UTF-8 | Event message |

**LabView timestamp to Unix time:** `unix_time = -2082826800 + seconds + fractional / 2^64`

### Event Text Formats

A single event record's text payload may contain one of the following:

1. **Plain text** — Direct message strings like `Code Start Notification.`

2. **FMS Connected line** — Format: `FMS Connected:   <MatchType> - <Number>:<Replay>, Field Time: <YY/M/D H:M:S>\n -- FRC Driver Station - Version <version>`

3. **Info records** — Contain DS version and event name: `Info <version>Info FMS Event Name: <event_code>`. Also contains joystick info: `Info Joystick <N>: (<Name>)<axes> axes, <buttons> buttons, <povs> POVs.` (multiple joysticks concatenated in a single record, may be duplicated).

4. **Warning records** — Distinct from tagged events. Format: `Warning <Code> NNNNN <secondsSinceReboot> SSS.SSS\r<Description>Message text.` Tags are `<Code>`, `<secondsSinceReboot>`, `<Description>` — completely different from the `<TagVersion>` structure. These contain FRC system warnings (e.g., `FRC: Time since robot boot.`).

5. **Tagged events** — A single text payload may contain multiple `<TagVersion>` entries concatenated together. Each `<TagVersion>` entry is treated as an individual event for filtering and display purposes. Two sub-formats:
   - Message: `<TagVersion>1 <time> SS.SSS <message> ...`
   - Coded event: `<TagVersion>1 <time> SS.SSS <count> N <flags> F <Code> C <details> ... <location> ... <stack> ...`

### Parsing the FMS Connected String

Regex pattern:

```
FMS Connected:\s+(\w+)\s*-\s*(\d+):(\d+),\s*Field Time:\s*(.+)\n\s*--\s*(.+)
```

Capture groups: (1) match type, (2) match number, (3) replay number, (4) field time string, (5) DS version string.

### Parsing Info Records

**Event name:** Match `Info FMS Event Name:\s*(\w+)` within the text payload.

**Joystick config:** Match all occurrences of `Info Joystick (\d+): \(([^)]+)\)(\d+) axes, (\d+) buttons, (\d+) POVs\.` and deduplicate by joystick number (keep first occurrence).

### Parsing Warning Records

Regex pattern:

```
Warning <Code> (\d+) <secondsSinceReboot> ([\d.]+)(?:\r)?<Description>(.+)
```

Capture groups: (1) warning code, (2) seconds since reboot, (3) description text.

Formatted as `WARNING (<code>): <description>`. The `<secondsSinceReboot>` value is not used for display — event timestamp comes from the record header like all other events.

## Match Events File Format

```
Match: Qualification 52
Event: NCPEM
Field Time: 2026/3/29 13:35:04
DS Version: FRC Driver Station - Version 26.0
Replay: 1

Log Files:
  [1] 2026_03_29 09_34_29 Sun (Q52_1_)

Events:
  [1] 00.000  FMS Connected
  [1] 00.000  Code Start Notification
  [1] 00.000  ERROR (44000): Driver Station not keeping up with protocol rates
  [1] 00.169  USB Camera 0: Attempting to connect on /dev/video0
  [1] 07.215  USB Camera 0: Attempting to connect on /dev/video0 (repeated 5x)
  [1] 25.402  WARNING (44007): FRC: Time since robot boot
  ...

Joysticks:
  0: Controller (Xbox One For Windows) - 6 axes, 16 buttons, 1 POV
  1: Controller (Gamepad F310) - 6 axes, 10 buttons, 1 POV
  2: Controller (Gamepad F310) - 6 axes, 10 buttons, 1 POV
  3: Logitech Dual Action - 0 axes, 0 buttons, 0 POV
  4: Logitech Extreme 3D - 0 axes, 0 buttons, 0 POV
```

### Field Time Formatting

Field Time is displayed as-is from the FMS string (e.g., `26/3/29 13:35:4`). No reformatting is applied.

### Output Sections

- `[1]` / `[2]` prefix indicates which log file produced the event (for restart tracking).
- Timestamps are relative to each log file's start.
- Events are grouped by log file: all events from `[1]` appear first, followed by all events from `[2]`, etc. Within each group, events are in chronological order.
- Header values (Match, Event, Field Time, DS Version, Replay) are taken from the first log file (sequence `_1_`).
- Joystick config is reformatted from raw `Info Joystick N: (Name)A axes, B buttons, C POVs.` to `N: Name - A axes, B buttons, C POV`. Joystick info is taken from the first log file; if it differs after a restart, both are shown with log file prefix.

## Event Filtering

### Include

- FMS Connected/Disconnected — plain text starting with `FMS Connected:`
- Code Start Notification — plain text `Code Start Notification.`
- Warning records — `Warning <Code> ... <Description> ...` format, always included
- Warnings and errors — tagged events with `<flags>` value 1 (warning) or 2 (error), or non-zero `<Code>`
- Comms lost/restored — Code `44004` (`FRC: The Driver Station has lost communication with the robot.`)
- Phoenix Signal Logger messages — tagged events where `<details>` starts with `[phoenix] Signal Logger`
- PhotonVision errors — tagged events where `<message>` or `<details>` contains `PhotonVision` or `org.photonvision`
- Robot mode transitions — tagged events where `<message>` contains mode change text (e.g., `Robot is now in Autonomous`, `Robot is now in Teleop`, `Robot is now Disabled`)

### Exclude

- Periodic timer traces — tagged events where `<message>` matches patterns like `disabledPeriodic():`, `robotPeriodic():`, `Shuffleboard.update():`, `LiveWindow.updateValues():`, `SmartDashboard.updateValues():`

### Repeat Collapsing

When the same message text appears N times consecutively (N >= 2, after tag stripping):
- Display the 1st occurrence normally.
- Suppress the 2nd through (N-1)th occurrences.
- Display the Nth (last) occurrence with `(repeated {N-1}x)` appended.
- Example: a message appearing 6 times shows the 1st normally, suppresses 2nd-5th, and shows the 6th with `(repeated 5x)`.
- Example: a message appearing 2 times shows the 1st normally and the 2nd with `(repeated 1x)`.
- Messages are considered "the same" if their display text (after formatting) is identical.
- Repeat collapsing applies within a single log file only — it does not span across log files `[1]` to `[2]`.

## Confirmation Prompt

When new matches are found, the tool displays them before processing:

```
New matches found:
  Q52  - Qualification 52 (1 log pair)
  Q60  - Qualification 60 (2 log pairs — robot restart detected)
  E6_R1 - Elimination 6 Replay 1 (1 log pair)

Process these matches? [Y/n]
```

If all matches are already in the destination:

```
No new matches found.
```

## Error Handling

| Condition | Behavior |
|-----------|----------|
| `source_dir` does not exist | Print error, exit code 1 |
| `dest_dir` does not exist | Print error, exit code 1 |
| No `.dsevents` files found (after date filter) | Print "No .dsevents files found.", exit code 0 |
| No new matches found | Print "No new matches found.", exit code 0 |
| Corrupt/unreadable `.dsevents` file | Print warning with filename, skip file, continue |
| Missing `.dslog` pair for a match file | Print warning, skip that file |
| User declines confirmation | Print "Aborted.", exit code 0 |

## README Update

Add a section to `README.md` documenting the script usage with examples.

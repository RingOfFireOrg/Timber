# TBA Link & Non-Participation Detection — Design Spec

**Status:** APPROVED — Reviewed 2026-03-31. Ready for implementation.

## Overview

Two enhancements to the match log processor's `match_events.txt` output:

1. Add a **The Blue Alliance** link to each match's header, constructed from the `--event` CLI parameter.
2. Detect matches where the robot did not participate and insert a **NOTE** in the output.

## `--event` Parameter Change

The existing `--event` CLI parameter changes meaning from a free-form display name to a **TBA event key** (e.g., `2026ncpem`). It remains required. The value is used for:

- The `Event:` line in `match_events.txt` (replaces the previous display name — e.g., `Event: 2026ncpem` instead of `Event: UNCPembroke`).
- Constructing the TBA URL.

Users find their event key by visiting [The Blue Alliance](https://www.thebluealliance.com), navigating to their event, and using the key from the URL (e.g., `https://www.thebluealliance.com/event/2026ncpem` → `2026ncpem`).

## TBA URL Construction

A `The Blue Alliance:` line is added to the `match_events.txt` header block, immediately after `Replay:`.

| Match Type | URL Format |
|------------|-----------|
| Qualification | `https://www.thebluealliance.com/match/{event_key}_qm{number}` |
| Playoff (Elimination) | `https://www.thebluealliance.com/match/{event_key}_sf{number}m{replay}` |

- `{event_key}` is the value of the `--event` CLI parameter (e.g., `2026ncpem`).
- `{number}` is the match number from the FMS Connected string.
- `{replay}` is the replay number from the FMS Connected string.
- For qualification matches, replay is not included in the URL (TBA uses `qm{number}` only, regardless of replay value).
- For playoff/elimination matches, replay is always included as `m{replay}`.
- The FMS elimination number maps directly to TBA's `sf` number (e.g., FMS `Elimination - 4:1` → TBA `sf4m1`).

### Examples

- Qualification 13 at `2026ncpem`: `https://www.thebluealliance.com/match/2026ncpem_qm13`
- Elimination 4 Replay 1 at `2026ncpem`: `https://www.thebluealliance.com/match/2026ncpem_sf4m1`

## Non-Participation Detection

A match is considered a **non-participation** match when:

- No `Code Start Notification` event is present in any log file for the match, **AND**
- No joystick info records are found in any `.dsevents` file for the match (i.e., the `Joysticks:` section would be empty).

When detected, a note is inserted between the header block and the `Log Files:` section:

```
NOTE: The robot does not appear to have participated in this match.
```

The `Events:`, `Log Files:`, and `Joysticks:` sections are still included as normal — the note is informational, not a filter.

## Updated `match_events.txt` Format

### Normal match (with participation)

```
Match: Qualification 13
Event: 2026ncpem
Field Time: 26/3/28 17:29:45
DS Version: FRC Driver Station - Version 26.0
Replay: 1
The Blue Alliance: https://www.thebluealliance.com/match/2026ncpem_qm13

Log Files:
  [1] 2026_03_28 13_29_12 Sat (Q13_1_)
  ...

Events:
  ...

Joysticks:
  ...
```

### Non-participation match

```
Match: Elimination 3
Event: 2026ncpem
Field Time: 26/3/29 17:42:4
DS Version: FRC Driver Station - Version 26.0
Replay: 1
The Blue Alliance: https://www.thebluealliance.com/match/2026ncpem_sf3m1

NOTE: The robot does not appear to have participated in this match.

Log Files:
  [1] 2026_03_29 13_41_30 Sun (E3_R1_1_)

Events:
  [1] 000.418  ERROR (44004): FRC: The Driver Station has lost communication with the robot.
  [1] 000.619  FMS Connected
  [1] 003.633  ERROR (44002): Ping Results: ...
  [1] 120.943  ERROR (44005): FMS Disconnect

Joysticks:
```

## README Update

Add instructions for finding the TBA event key:

1. Visit [The Blue Alliance](https://www.thebluealliance.com).
2. Search for the event or navigate via the team page.
3. The event key is in the URL: `https://www.thebluealliance.com/event/{event_key}` — use the `{event_key}` portion (e.g., `2026ncpem`).

## Files Changed

| File | Change |
|------|--------|
| `match_processor/match_writer.py` | Add TBA URL construction and non-participation detection to `match_events.txt` output |
| `match_processor/process_matches.py` | Update `--event` help text to describe TBA event key |
| `match_processor/tests/test_match_writer.py` | Tests for TBA URL generation and non-participation note |
| `match_processor/tests/test_integration.py` | Update integration tests for new output format |
| `README.md` | Document `--event` key usage and how to find it |

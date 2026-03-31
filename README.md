# Timber
Pyro Tech Robot Logs

## Match Log Processor

Process FRC Driver Station log files (`.dsevents` and `.dslog`) from competition matches.

### Usage

```bash
# Scan all files in source directory
uv run match_processor/process_matches.py <source_dir> <dest_dir> --event <tba_event_key>

# Scan only today's files
uv run match_processor/process_matches.py <source_dir> <dest_dir> --event <tba_event_key> --today

# Scan files for a specific date
uv run match_processor/process_matches.py <source_dir> <dest_dir> --event <tba_event_key> --date 2026-03-29
```

### Finding Your TBA Event Key

The `--event` parameter takes a [The Blue Alliance](https://www.thebluealliance.com) event key. To find it:

1. Go to [thebluealliance.com](https://www.thebluealliance.com)
2. Search for your event or navigate via your team page
3. The event key is in the URL: `https://www.thebluealliance.com/event/2026ncpem` → use `2026ncpem`

The event key is used in the `Event:` line of match output files and to generate direct links to each match on The Blue Alliance.

### Example

```bash
uv run match_processor/process_matches.py 2026/03/ 2026/UNCPembroke/ --event 2026ncpem
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

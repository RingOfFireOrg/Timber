# Timber
Pyro Tech Robot Logs

## Match Log Processor

Process FRC Driver Station log files (`.dsevents` and `.dslog`) from competition matches.

### Usage

```bash
# Scan all files in source directory
python3 match_processor/process_matches.py <source_dir> <dest_dir>

# Scan only today's files
python3 match_processor/process_matches.py <source_dir> <dest_dir> --today

# Scan files for a specific date
python3 match_processor/process_matches.py <source_dir> <dest_dir> --date 2026-03-29
```

### Example

```bash
python3 match_processor/process_matches.py 2026/03/ 2026/UNCPembroke/
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

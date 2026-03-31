# Timber

Pyro Tech Robot Logs

## Match Log Processor

Automatically organizes your FRC Driver Station match logs from competition and generates a per-match event summary for each match. Instead of digging through dozens of raw `.dsevents` and `.dslog` files after an event, you get one clean text file per match with timestamped events, joystick info, and a direct link to the match on The Blue Alliance.

### What it does

1. Scans a folder containing `.dsevents` and `.dslog` files. These are the log files from your Driver Station laptop, typically found in `C:\Users\Public\Documents\FRC\Log Files\`.
2. Identifies real FRC matches (skips logs created during practice and pit sessions)
3. Groups files from the same match together and detects robot restarts mid-match
4. Skips matches you've already processed
5. Copies each match's log files into your event folder with clear names (e.g., `Q52_1_`)
6. Writes a `match_events.txt` summary with key events, errors, and warnings for each match
7. Flags matches where the robot didn't appear to participate but still generated log files

### Prerequisites

- **Python 3.10+** — if you have the FRC tools installed, you likely already have Python
- No additional packages are needed

If you use [`uv`](https://docs.astral.sh/uv/) (a fast Python package manager), you can use `uv run` instead of `python3` in the examples below.

### Getting started

```bash
# Clone the repository
git clone https://github.com/RingOfFireOrg/Timber.git
cd timber

# Verify it works
python3 match_processor/process_matches.py --help
```

### Usage

```bash
# Process all log files in a source directory
python3 match_processor/process_matches.py <source_dir> <dest_dir> --event <tba_event_key>

# Process only today's log files
python3 match_processor/process_matches.py <source_dir> <dest_dir> --event <tba_event_key> --today

# Process log files from a specific date
python3 match_processor/process_matches.py <source_dir> <dest_dir> --event <tba_event_key> --date 2026-03-29
```

### Finding your TBA event key

The `--event` parameter takes a [The Blue Alliance](https://www.thebluealliance.com) event key. To find yours:

1. Go to [thebluealliance.com](https://www.thebluealliance.com)
2. Search for your team number and click on the event you attended
3. Look at the URL in your browser's address bar — it will look like `https://www.thebluealliance.com/event/2026ncpem`
4. The event key is the last part: **`2026ncpem`**

The event key is used to generate direct links to each match on The Blue Alliance in the output files.

### Example

```bash
python3 match_processor/process_matches.py 2026/03/ 2026/UNCPembroke/ --event 2026ncpem
```

The tool scans for matches and asks you to confirm before processing:

```
Scanning 2026/03/ for match files...

New matches found:
  Q6       - Qualification 6 (1 log pair)
  Q7       - Qualification 7 (1 log pair)
  Q10      - Qualification 10 (1 log pair)
  E3_R1    - Elimination 3 Replay 1 (1 log pair)

Process these matches? [Y/n]
```

### Sample output

Each match gets a `match_events.txt` file like this:

```
Match: Elimination 4
Event: 2026ncpem
Field Time: 26/3/29 17:44:21
DS Version: FRC Driver Station - Version 26.0
Replay: 1
The Blue Alliance: https://www.thebluealliance.com/match/2026ncpem_sf4m1

Log Files:
  [1] 2026_03_29 13_43_47 Sun (E4_R1_1_)

Events:
  [1] 000.000  FMS Connected
  [1] 001.817  ERROR (44002): Ping Results: ...
  [1] 006.082  ERROR (44003): FRC: No robot code is currently running.
  ...

Joysticks:
  0: Controller (Xbox One For Windows) - 6 axes, 16 buttons, 1 POV
```

If the robot didn't participate in a match (no code running, no joysticks detected), the output includes a note:

```
NOTE: The robot does not appear to have participated in this match.
```

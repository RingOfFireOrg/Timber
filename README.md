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
6. Writes a `match_events.txt` summary for each match containing:
   - Timestamped events, errors, and warnings from the Driver Station
   - Robot mode transitions (Autonomous, Teleop, Disabled) parsed from the `.dslog` binary data
   - Telemetry summary with min/max battery voltage, CPU, CAN utilization, trip time, and packet loss
   - Joystick configuration and a direct link to the match on The Blue Alliance
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
Match: Qualification 39
Event: 2026ncpem
Field Time: 26/3/28 21:46:26
DS Version: FRC Driver Station - Version 26.0
Replay: 1
The Blue Alliance: https://www.thebluealliance.com/match/2026ncpem_qm39

Log Files:
  [1] 2026_03_28 17_45_53 Sat (Q39_1_)

Joysticks:
  0: Controller (Xbox One For Windows) - 6 axes, 16 buttons, 1 POV

Telemetry:
  Voltage: 7.43 - 12.77 V
  CPU: 27 - 90%
  CAN Utilization: 0 - 100%
  Trip Time: 4.5 - 11.0 ms
  Packet Loss: 0 - 40%

Events:
  [1] 000.000  FMS Connected
  [1] 150.223  Code Start Notification
  [1] 563.360  ***** Transition: Autonomous
  [1] 584.860  ***** Transition: Disabled
  [1] 588.220  ***** Transition: Teleop
  [1] 728.040  ***** Transition: Disabled
```

The Telemetry section gives you a quick health check of your robot during the match — if you see low voltage or high CAN utilization, that's worth investigating. The transition timestamps tell you exactly when your robot entered each mode, which is useful for debugging auto routines or figuring out why you lost connection mid-match.

If the robot didn't participate in a match (no code running, no joysticks detected), the output flags it:

```
NOTE: The robot does not appear to have participated in this match.

Telemetry:
  No telemetry data available.
```

# TBA Link & Non-Participation Detection Implementation Plan

**Status:** COMPLETE — Implemented 2026-03-31. All 58 tests passing.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add The Blue Alliance match links and non-participation notes to `match_events.txt` output.

**Architecture:** Two changes to `match_writer.py`: (1) a `build_tba_url()` helper that constructs the correct TBA URL from match type/number/replay and the event key, added to the header block; (2) a `detect_non_participation()` helper that checks events and joysticks to insert a NOTE when the robot didn't play. The `--event` parameter semantics change from display name to TBA event key. All changes are confined to `match_writer.py`, `process_matches.py` (help text only), tests, and `README.md`.

**Tech Stack:** Python 3.14, pytest, no new dependencies

**Spec:** `docs/superpowers/specs/2026-03-31-tba-link-and-participation-design.md`

**Code review skill:** Use `@.claude/skills/frc-log-review.md` at review checkpoints

---

## File Map

| File | Role | Change |
|------|------|--------|
| `match_processor/match_writer.py` | Match output formatting | Add `build_tba_url()`, `detect_non_participation()`, update `format_match_events_txt()` |
| `match_processor/process_matches.py` | CLI entry point | Update `--event` help text; extract joysticks from all log files (not just first) |
| `match_processor/tests/test_match_writer.py` | Unit tests for writer | Add TBA URL tests, non-participation tests, update existing header tests |
| `match_processor/tests/test_integration.py` | Integration tests | Add TBA link and non-participation integration tests |
| `README.md` | User documentation | Update usage examples, add TBA event key instructions |

---

### Task 1: TBA URL Construction — Tests

**Files:**
- Modify: `match_processor/tests/test_match_writer.py`

- [ ] **Step 1: Write failing tests for `build_tba_url`**

Add these tests to `test_match_writer.py`:

```python
def test_build_tba_url_qualification():
    from match_writer import build_tba_url
    url = build_tba_url("2026ncpem", "Qualification", 13, 1)
    assert url == "https://www.thebluealliance.com/match/2026ncpem_qm13"


def test_build_tba_url_qualification_ignores_replay():
    from match_writer import build_tba_url
    url = build_tba_url("2026ncpem", "Qualification", 13, 2)
    assert url == "https://www.thebluealliance.com/match/2026ncpem_qm13"


def test_build_tba_url_elimination():
    from match_writer import build_tba_url
    url = build_tba_url("2026ncpem", "Elimination", 4, 1)
    assert url == "https://www.thebluealliance.com/match/2026ncpem_sf4m1"


def test_build_tba_url_elimination_replay_2():
    from match_writer import build_tba_url
    url = build_tba_url("2026ncpem", "Elimination", 6, 2)
    assert url == "https://www.thebluealliance.com/match/2026ncpem_sf6m2"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest match_processor/tests/test_match_writer.py -v -k "test_build_tba_url"`
Expected: FAIL — `ImportError: cannot import name 'build_tba_url'`

- [ ] **Step 3: Commit**

```
test: add failing tests for TBA URL construction
```

---

### Task 2: TBA URL Construction — Implementation

**Files:**
- Modify: `match_processor/match_writer.py`

- [ ] **Step 1: Add `build_tba_url` to `match_writer.py`**

Add this function before `format_match_events_txt`:

```python
TBA_BASE_URL = "https://www.thebluealliance.com/match"


def build_tba_url(event_key, match_type, match_number, replay):
    """Construct a The Blue Alliance match URL.

    Args:
        event_key: TBA event key (e.g., '2026ncpem')
        match_type: 'Qualification' or 'Elimination'
        match_number: match number from FMS
        replay: replay number from FMS
    """
    if match_type == "Elimination":
        return f"{TBA_BASE_URL}/{event_key}_sf{match_number}m{replay}"
    return f"{TBA_BASE_URL}/{event_key}_qm{match_number}"
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run pytest match_processor/tests/test_match_writer.py -v -k "test_build_tba_url"`
Expected: 4 PASSED

- [ ] **Step 3: Commit**

```
feat: add TBA URL construction for qualification and elimination matches
```

---

### Task 3: Non-Participation Detection — Tests

**Files:**
- Modify: `match_processor/tests/test_match_writer.py`

- [ ] **Step 1: Write failing tests for `detect_non_participation`**

Add these tests to `test_match_writer.py`:

```python
def test_detect_non_participation_true_no_code_start_no_joysticks():
    from match_writer import detect_non_participation
    events_by_log = {1: [
        {"time": "000.418", "display": "ERROR (44004): FRC: The Driver Station has lost communication with the robot."},
        {"time": "000.619", "display": "FMS Connected"},
    ]}
    joysticks = []
    assert detect_non_participation(events_by_log, joysticks) is True


def test_detect_non_participation_false_has_code_start():
    from match_writer import detect_non_participation
    events_by_log = {1: [
        {"time": "000.000", "display": "FMS Connected"},
        {"time": "001.000", "display": "Code Start Notification"},
    ]}
    joysticks = []
    assert detect_non_participation(events_by_log, joysticks) is False


def test_detect_non_participation_false_has_joysticks():
    from match_writer import detect_non_participation
    events_by_log = {1: [
        {"time": "000.000", "display": "FMS Connected"},
    ]}
    joysticks = [{"number": 0, "name": "Xbox", "axes": 6, "buttons": 16, "povs": 1}]
    assert detect_non_participation(events_by_log, joysticks) is False


def test_detect_non_participation_false_code_start_in_second_log():
    from match_writer import detect_non_participation
    events_by_log = {
        1: [{"time": "000.000", "display": "FMS Connected"}],
        2: [{"time": "000.000", "display": "Code Start Notification"}],
    }
    joysticks = []
    assert detect_non_participation(events_by_log, joysticks) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest match_processor/tests/test_match_writer.py -v -k "test_detect_non_participation"`
Expected: FAIL — `ImportError: cannot import name 'detect_non_participation'`

- [ ] **Step 3: Commit**

```
test: add failing tests for non-participation detection
```

---

### Task 4: Non-Participation Detection — Implementation

**Files:**
- Modify: `match_processor/match_writer.py`

- [ ] **Step 1: Add `detect_non_participation` to `match_writer.py`**

Add this function after `build_tba_url`:

```python
def detect_non_participation(events_by_log, joysticks):
    """Check if the robot participated in a match.

    Returns True if BOTH conditions hold:
    - No 'Code Start Notification' in any log's events
    - No joystick info records (empty joysticks list)
    """
    if joysticks:
        return False
    for seq_events in events_by_log.values():
        for event in seq_events:
            if "Code Start Notification" in event["display"]:
                return False
    return True
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run pytest match_processor/tests/test_match_writer.py -v -k "test_detect_non_participation"`
Expected: 4 PASSED

- [ ] **Step 3: Commit**

```
feat: add non-participation detection for match events
```

---

### Task 5: Integrate Into `format_match_events_txt` — Tests

**Files:**
- Modify: `match_processor/tests/test_match_writer.py`

- [ ] **Step 1: Write failing test for TBA link in header output**

```python
def test_format_match_events_includes_tba_link():
    from match_writer import format_match_events_txt
    fms_info = {
        "match_type": "Qualification",
        "match_number": 13,
        "replay": 1,
        "field_time": "26/3/28 17:29:45",
        "ds_version": "FRC Driver Station - Version 26.0",
    }
    log_files = [{"seq": 1, "basename": "2026_03_28 13_29_12 Sat"}]
    events_by_log = {1: [
        {"time": "000.000", "display": "FMS Connected"},
        {"time": "001.000", "display": "Code Start Notification"},
    ]}
    joysticks = [{"number": 0, "name": "Xbox", "axes": 6, "buttons": 16, "povs": 1}]

    txt = format_match_events_txt(fms_info, "Q13", "2026ncpem", log_files, events_by_log, joysticks)

    assert "The Blue Alliance: https://www.thebluealliance.com/match/2026ncpem_qm13" in txt
    # TBA line should come after Replay and before Log Files
    lines = txt.split("\n")
    tba_idx = next(i for i, l in enumerate(lines) if "The Blue Alliance:" in l)
    replay_idx = next(i for i, l in enumerate(lines) if l.startswith("Replay:"))
    log_idx = next(i for i, l in enumerate(lines) if l == "Log Files:")
    assert replay_idx < tba_idx < log_idx
```

- [ ] **Step 2: Write failing test for non-participation NOTE in output**

```python
def test_format_match_events_non_participation_note():
    from match_writer import format_match_events_txt
    fms_info = {
        "match_type": "Elimination",
        "match_number": 3,
        "replay": 1,
        "field_time": "26/3/29 17:42:4",
        "ds_version": "FRC Driver Station - Version 26.0",
    }
    log_files = [{"seq": 1, "basename": "2026_03_29 13_41_30 Sun"}]
    events_by_log = {1: [
        {"time": "000.418", "display": "ERROR (44004): FRC: The Driver Station has lost communication with the robot."},
        {"time": "000.619", "display": "FMS Connected"},
    ]}
    joysticks = []

    txt = format_match_events_txt(fms_info, "E3_R1", "2026ncpem", log_files, events_by_log, joysticks)

    assert "NOTE: The robot does not appear to have participated in this match." in txt
    assert "The Blue Alliance: https://www.thebluealliance.com/match/2026ncpem_sf3m1" in txt
    # NOTE should come after TBA line and before Log Files
    lines = txt.split("\n")
    note_idx = next(i for i, l in enumerate(lines) if l.startswith("NOTE:"))
    tba_idx = next(i for i, l in enumerate(lines) if "The Blue Alliance:" in l)
    log_idx = next(i for i, l in enumerate(lines) if l == "Log Files:")
    assert tba_idx < note_idx < log_idx
```

- [ ] **Step 3: Write failing test that participation match has no NOTE**

```python
def test_format_match_events_no_note_when_participating():
    from match_writer import format_match_events_txt
    fms_info = {
        "match_type": "Qualification",
        "match_number": 52,
        "replay": 1,
        "field_time": "26/3/29 13:35:4",
        "ds_version": "FRC Driver Station - Version 26.0",
    }
    log_files = [{"seq": 1, "basename": "2026_03_29 09_34_29 Sun"}]
    events_by_log = {1: [
        {"time": "000.000", "display": "FMS Connected"},
        {"time": "001.000", "display": "Code Start Notification"},
    ]}
    joysticks = [{"number": 0, "name": "Xbox", "axes": 6, "buttons": 16, "povs": 1}]

    txt = format_match_events_txt(fms_info, "Q52", "2026ncpem", log_files, events_by_log, joysticks)

    assert "NOTE:" not in txt
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest match_processor/tests/test_match_writer.py -v -k "test_format_match_events_includes_tba or test_format_match_events_non_participation or test_format_match_events_no_note"`
Expected: FAIL — output missing TBA link line and NOTE

- [ ] **Step 5: Commit**

```
test: add failing tests for TBA link and non-participation note in match output
```

---

### Task 6: Integrate Into `format_match_events_txt` — Implementation

**Files:**
- Modify: `match_processor/match_writer.py`
- Modify: `match_processor/tests/test_match_writer.py` (update existing tests)

- [ ] **Step 1: Update `format_match_events_txt` to add TBA link and non-participation note**

Replace the header section and add non-participation note logic in `format_match_events_txt`. The updated function:

```python
def format_match_events_txt(fms_info, match_id, event_name, log_files, events_by_log, joysticks):
    """Generate the full match_events.txt content as a string.

    Args:
        fms_info: dict with match_type, match_number, replay, field_time, ds_version
        match_id: str like 'Q52' or 'E6_R1'
        event_name: str TBA event key (e.g., '2026ncpem') — previously a display name,
            now a TBA key used for both the Event: header line and TBA URL construction
        log_files: list of dicts with seq and basename
        events_by_log: dict mapping seq number -> list of event dicts (time, display)
        joysticks: list of joystick dicts (number, name, axes, buttons, povs)
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

    # Events
    lines.append("Events:")
    for lf in log_files:
        seq = lf["seq"]
        for event in events_by_log.get(seq, []):
            lines.append(f"  [{seq}] {event['time']}  {event['display']}")
    lines.append("")

    # Joysticks
    lines.append("Joysticks:")
    for j in joysticks:
        lines.append(f"  {j['number']}: {j['name']} - {j['axes']} axes, {j['buttons']} buttons, {j['povs']} POV")
    lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 2: Update existing tests to use TBA event key and fix test data**

In `test_format_match_events_header`: change `"NCPEM"` to `"2026ncpem"`, fix event time format from `"00.000"` to `"000.000"` (the real formatter uses `f"{seconds:07.3f}"` — 7 chars, zero-padded), add `Code Start Notification` event so the test doesn't falsely trigger non-participation, and update assertions:

```python
def test_format_match_events_header():
    from match_writer import format_match_events_txt
    fms_info = {
        "match_type": "Qualification",
        "match_number": 52,
        "replay": 1,
        "field_time": "26/3/29 13:35:4",
        "ds_version": "FRC Driver Station - Version 26.0",
    }
    match_id = "Q52"
    log_files = [{"seq": 1, "basename": "2026_03_29 09_34_29 Sun"}]
    events_by_log = {1: [
        {"time": "000.000", "display": "FMS Connected"},
        {"time": "001.000", "display": "Code Start Notification"},
    ]}
    joysticks = [{"number": 0, "name": "Controller (Xbox One For Windows)", "axes": 6, "buttons": 16, "povs": 1}]

    txt = format_match_events_txt(fms_info, match_id, "2026ncpem", log_files, events_by_log, joysticks)

    assert "Match: Qualification 52" in txt
    assert "Event: 2026ncpem" in txt
    assert "Field Time: 26/3/29 13:35:4" in txt
    assert "DS Version: FRC Driver Station - Version 26.0" in txt
    assert "Replay: 1" in txt
    assert "The Blue Alliance: https://www.thebluealliance.com/match/2026ncpem_qm52" in txt
    assert "[1] 2026_03_29 09_34_29 Sun (Q52_1_)" in txt
    assert "[1] 000.000  FMS Connected" in txt
    assert "0: Controller (Xbox One For Windows) - 6 axes, 16 buttons, 1 POV" in txt
    assert "NOTE:" not in txt
```

In `test_format_match_events_multi_log`: change `"NCPEM"` to `"2026ncpem"`, fix event time format from `"00.000"` to `"000.000"` (same format correction as above), add Code Start Notification to events so it doesn't falsely trigger non-participation:

```python
def test_format_match_events_multi_log():
    from match_writer import format_match_events_txt
    fms_info = {
        "match_type": "Qualification",
        "match_number": 60,
        "replay": 1,
        "field_time": "26/3/29 14:00:0",
        "ds_version": "FRC Driver Station - Version 26.0",
    }
    match_id = "Q60"
    log_files = [
        {"seq": 1, "basename": "2026_03_29 09_34_29 Sun"},
        {"seq": 2, "basename": "2026_03_29 09_40_12 Sun"},
    ]
    events_by_log = {
        1: [{"time": "000.000", "display": "FMS Connected"}],
        2: [
            {"time": "000.000", "display": "FMS Connected"},
            {"time": "001.000", "display": "Code Start Notification"},
        ],
    }
    joysticks = []

    txt = format_match_events_txt(fms_info, match_id, "2026ncpem", log_files, events_by_log, joysticks)

    assert "[1]" in txt
    assert "[2]" in txt
    assert "Q60_1_" in txt
    assert "Q60_2_" in txt
    assert "NOTE:" not in txt  # Code Start Notification in log 2 prevents false positive
```

- [ ] **Step 3: Run all match_writer tests**

Run: `uv run pytest match_processor/tests/test_match_writer.py -v`
Expected: All PASSED

- [ ] **Step 4: Commit**

```
feat: add TBA link and non-participation note to match_events.txt output
```

---

### Task 7: Update CLI — Help Text + Joystick Extraction Fix

**Files:**
- Modify: `match_processor/process_matches.py`

**Note:** The `process_match()` call site at line 165 passes `event_name` to `format_match_events_txt()` — this parameter name is unchanged, so no code change is needed there. The semantic shift from display name to TBA event key is handled entirely by the user passing a different value via `--event`.

- [ ] **Step 1: Update `--event` help text**

In `process_matches.py`, change line 182-183:

```python
    parser.add_argument("--event", required=True,
                        help="FRC event code (e.g., NCPEM)")
```

to:

```python
    parser.add_argument("--event", required=True,
                        help="The Blue Alliance event key (e.g., 2026ncpem). "
                             "Find it at https://www.thebluealliance.com — the key is in the event URL.")
```

- [ ] **Step 2: Fix joystick extraction to check all log files**

In `process_matches.py`, the `process_match` function (line 162) currently extracts joysticks only from the first log file:

```python
    joysticks = extract_joystick_info(files[0]["parsed"]["events"])
```

This causes false non-participation detection for restart matches where joystick info only appears in a later log. Replace with:

```python
    # Extract joystick info from all log files (may appear in any restart)
    joysticks = []
    for fi in files:
        joysticks = extract_joystick_info(fi["parsed"]["events"])
        if joysticks:
            break
```

This tries each log file in sequence and uses the first one that has joystick data.

- [ ] **Step 3: Run CLI help test**

Run: `uv run pytest match_processor/tests/test_integration.py::test_cli_help -v`
Expected: PASSED

- [ ] **Step 4: Commit**

```
fix: extract joysticks from all log files; update --event help text
```

---

### Task 8: Update Integration Tests

**Files:**
- Modify: `match_processor/tests/test_integration.py`

- [ ] **Step 1: Add integration test for non-participation match**

Add a test that creates a dsevents file with FMS Connected but no Code Start Notification and no joysticks, processes it, and verifies the NOTE appears in the output:

```python
def test_non_participation_match_note(tmp_dirs):
    src, dst = tmp_dirs

    # FMS Connected but no Code Start Notification, no joysticks
    match_data = make_dsevents_file([
        "FMS Connected:   Elimination - 3:1, Field Time: 26/3/29 17:42:4\n"
        " -- FRC Driver Station - Version 26.0",
    ])
    (src / "2026_03_29 13_41_30 Sun.dsevents").write_bytes(match_data)
    (src / "2026_03_29 13_41_30 Sun.dslog").write_bytes(b"\x00" * 100)

    from process_matches import find_dsevents_files, scan_and_identify, process_match
    matches = scan_and_identify(find_dsevents_files(str(src)), str(dst))
    assert len(matches) == 1
    key = list(matches.keys())[0]
    files = matches[key]
    fms = files[0]["fms_info"]
    from match_identifier import build_match_id
    match_id = build_match_id(fms["match_type"], fms["match_number"], fms["replay"])

    process_match(key, files, match_id, "2026ncpem", str(src), str(dst))

    txt = (dst / f"{match_id}_match_events.txt").read_text()
    assert "NOTE: The robot does not appear to have participated in this match." in txt
    assert "The Blue Alliance: https://www.thebluealliance.com/match/2026ncpem_sf3m1" in txt
```

- [ ] **Step 2: Add integration test for participation match with TBA link**

```python
def test_participation_match_has_tba_link_no_note(tmp_dirs):
    src, dst = tmp_dirs

    match_data = make_dsevents_file([
        "Info Joystick 0: (Controller (Xbox One For Windows))6 axes, 16 buttons, 1 POVs. ",
        "FMS Connected:   Qualification - 13:1, Field Time: 26/3/28 17:29:45\n"
        " -- FRC Driver Station - Version 26.0",
        "Code Start Notification. ",
    ])
    (src / "2026_03_28 13_29_12 Sat.dsevents").write_bytes(match_data)
    (src / "2026_03_28 13_29_12 Sat.dslog").write_bytes(b"\x00" * 100)

    from process_matches import find_dsevents_files, scan_and_identify, process_match
    matches = scan_and_identify(find_dsevents_files(str(src)), str(dst))
    assert len(matches) == 1
    key = list(matches.keys())[0]
    files = matches[key]
    fms = files[0]["fms_info"]
    from match_identifier import build_match_id
    match_id = build_match_id(fms["match_type"], fms["match_number"], fms["replay"])

    process_match(key, files, match_id, "2026ncpem", str(src), str(dst))

    txt = (dst / f"{match_id}_match_events.txt").read_text()
    assert "The Blue Alliance: https://www.thebluealliance.com/match/2026ncpem_qm13" in txt
    assert "NOTE:" not in txt
```

- [ ] **Step 3: Run all integration tests**

Run: `uv run pytest match_processor/tests/test_integration.py -v`
Expected: All PASSED

- [ ] **Step 4: Commit**

```
test: add integration tests for TBA link and non-participation note
```

---

### Task 9: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README with `--event` key docs and usage example**

Replace the current Usage and Example sections. Note: this intentionally changes `python3` to `uv run` to match how the project is actually run (consistent with test commands and `pyproject.toml`). Replace with:

```markdown
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
```

Keep the existing "Output:" block and "The tool:" list unchanged.

- [ ] **Step 2: Commit**

```
docs: update README with TBA event key instructions
```

---

### Task 10: Smoke Test With Real Data

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest match_processor/tests/ -v`
Expected: All PASSED

- [ ] **Step 2: Smoke test against real match data**

Run: `uv run pytest match_processor/tests/test_integration.py::test_end_to_end_with_real_files -v`
Expected: PASSED — real `.dsevents` files from `2026/03/` are parsed correctly

- [ ] **Step 3: Commit (if any fixes needed)**

Only commit if smoke testing revealed issues that required code changes.

"""Write match_events.txt files and copy log file pairs to destination."""

import os
import shutil


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


def copy_match_files(match_id, file_entries, source_dir, dest_dir):
    """Copy .dsevents and .dslog file pairs to destination with match prefix.

    Args:
        match_id: str like 'Q52'
        file_entries: list of dicts with seq, basename, dsevents_path
        source_dir: source directory path
        dest_dir: destination directory path
    """
    for entry in file_entries:
        seq = entry["seq"]
        basename = entry["basename"]
        prefix = f"{match_id}_{seq}_"

        for ext in (".dsevents", ".dslog"):
            src_path = os.path.join(source_dir, basename + ext)
            dst_path = os.path.join(dest_dir, prefix + basename + ext)
            if os.path.exists(src_path):
                shutil.copy2(src_path, dst_path)


def write_match_events_file(dest_dir, match_id, content):
    """Write the match_events.txt file to the destination directory."""
    path = os.path.join(dest_dir, f"{match_id}_match_events.txt")
    with open(path, "w") as f:
        f.write(content)

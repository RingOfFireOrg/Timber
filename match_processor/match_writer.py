"""Write match_events.txt files and copy log file pairs to destination."""

import os
import shutil


def format_match_events_txt(fms_info, match_id, log_files, events_by_log, joysticks):
    """Generate the full match_events.txt content as a string.

    Args:
        fms_info: dict with match_type, match_number, replay, field_time, ds_version, event_name
        match_id: str like 'Q52' or 'E6_R1'
        log_files: list of dicts with seq and basename
        events_by_log: dict mapping seq number -> list of event dicts (time, display)
        joysticks: list of joystick dicts (number, name, axes, buttons, povs)
    """
    lines = []

    # Header
    lines.append(f"Match: {fms_info['match_type']} {fms_info['match_number']}")
    lines.append(f"Event: {fms_info.get('event_name', 'Unknown')}")
    lines.append(f"Field Time: {fms_info['field_time']}")
    lines.append(f"DS Version: {fms_info['ds_version']}")
    lines.append(f"Replay: {fms_info['replay']}")
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

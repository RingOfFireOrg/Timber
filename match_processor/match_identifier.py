"""Extract FMS match info from parsed .dsevents data and group files by match."""

import re

FMS_PATTERN = re.compile(
    r"FMS Connected:\s+(\w+)\s*-\s*(\d+):(\d+),\s*Field Time:\s*(.+)\n\s*--\s*(.+)"
)

EVENT_NAME_PATTERN = re.compile(r"Info FMS Event Name:\s*(\w+)")

JOYSTICK_PATTERN = re.compile(
    r"Info Joystick (\d+): \((.+?)\)(\d+) axes, (\d+) buttons, (\d+) POVs\."
)


def extract_fms_info(events):
    """Extract FMS match info from a list of event dicts.

    Scans event text for the FMS Connected line and Info records.
    Returns a dict with match_type, match_number, replay, field_time,
    ds_version, event_name — or None if no FMS data found.
    """
    fms_match = None
    event_name = None

    for event in events:
        text = event["text"]

        if fms_match is None:
            m = FMS_PATTERN.search(text)
            if m:
                fms_match = m

        if event_name is None:
            m = EVENT_NAME_PATTERN.search(text)
            if m:
                event_name = m.group(1)

        if fms_match and event_name:
            break

    if fms_match is None:
        return None

    return {
        "match_type": fms_match.group(1),
        "match_number": int(fms_match.group(2)),
        "replay": int(fms_match.group(3)),
        "field_time": fms_match.group(4).strip(),
        "ds_version": fms_match.group(5).strip(),
        "event_name": event_name,
    }


def extract_joystick_info(events):
    """Extract joystick configuration from event records.

    Returns a list of dicts with number, name, axes, buttons, povs.
    Deduplicates by joystick number (keeps first occurrence).
    """
    seen = set()
    joysticks = []

    for event in events:
        for m in JOYSTICK_PATTERN.finditer(event["text"]):
            num = int(m.group(1))
            if num not in seen:
                seen.add(num)
                joysticks.append({
                    "number": num,
                    "name": m.group(2),
                    "axes": int(m.group(3)),
                    "buttons": int(m.group(4)),
                    "povs": int(m.group(5)),
                })

    joysticks.sort(key=lambda j: j["number"])
    return joysticks


def build_match_key(match_type, match_number, replay):
    """Build the grouping key from match info (e.g., 'Qualification - 52:1')."""
    return f"{match_type} - {match_number}:{replay}"


def build_match_id(match_type, match_number, replay):
    """Build the file prefix match ID (e.g., 'Q52', 'E6_R1')."""
    if match_type == "Qualification":
        base = f"Q{match_number}"
        if replay > 1:
            base += f"_R{replay}"
        return base
    elif match_type == "Elimination":
        return f"E{match_number}_R{replay}"
    else:
        return f"{match_type}{match_number}"


def is_real_match(fms_info):
    """Return True if the FMS info represents a real match (not None or absent)."""
    if fms_info is None:
        return False
    return fms_info["match_type"] != "None"


def group_files_by_match(file_infos):
    """Group file info dicts by match key. Sort each group by header timestamp.

    Args:
        file_infos: list of dicts with keys: path, fms_info, header_timestamp

    Returns:
        dict mapping match_key -> list of file_info dicts, sorted by timestamp
    """
    groups = {}
    for fi in file_infos:
        key = build_match_key(
            fi["fms_info"]["match_type"],
            fi["fms_info"]["match_number"],
            fi["fms_info"]["replay"],
        )
        groups.setdefault(key, []).append(fi)

    for key in groups:
        groups[key].sort(key=lambda fi: fi["header_timestamp"])

    return groups

#!/usr/bin/env python3
"""FRC Match Log Processor — identify match log files and organize them."""

import argparse
import os
import re
import sys
from datetime import date

from dsevents_parser import parse_dsevents_path
from match_identifier import (
    extract_fms_info,
    extract_joystick_info,
    build_match_id,
    build_match_key,
    is_real_match,
    group_files_by_match,
)
from event_formatter import format_events, collapse_repeats
from match_writer import (
    format_match_events_txt,
    copy_match_files,
    write_match_events_file,
)
from dslog_parser import parse_dslog_path
from dslog_processor import detect_transitions, compute_telemetry


def get_date_filter(args):
    """Return date filter string as YYYY_MM_DD or None."""
    if args.today:
        return date.today().strftime("%Y_%m_%d")
    elif args.date:
        # Convert YYYY-MM-DD to YYYY_MM_DD
        return args.date.replace("-", "_")
    return None


def find_dsevents_files(source_dir, date_filter=None):
    """Find all .dsevents files in source_dir, optionally filtered by date."""
    files = []
    for name in os.listdir(source_dir):
        if not name.endswith(".dsevents"):
            continue
        if date_filter and not name.startswith(date_filter):
            continue
        files.append(os.path.join(source_dir, name))
    return sorted(files)


def get_existing_match_prefixes(dest_dir):
    """Return set of match prefixes already in dest_dir."""
    prefixes = set()
    prefix_pattern = re.compile(r"^(Q\d+(?:_R\d+)?|E\d+_R\d+)_")
    for name in os.listdir(dest_dir):
        m = prefix_pattern.match(name)
        if m:
            prefixes.add(m.group(1))
    return prefixes


def has_dslog_pair(dsevents_path):
    """Check if a matching .dslog file exists for this .dsevents file."""
    base = dsevents_path.rsplit(".dsevents", 1)[0]
    return os.path.exists(base + ".dslog")


def scan_and_identify(dsevents_files, dest_dir):
    """Parse match files, filter, group, and remove already-processed.

    Args:
        dsevents_files: list of .dsevents file paths (from find_dsevents_files)
        dest_dir: destination directory to check for existing matches

    Returns dict mapping match_key -> list of file info dicts.
    """
    if not dsevents_files:
        return {}

    # Parse all files and extract match info
    file_infos = []
    for path in dsevents_files:
        if not has_dslog_pair(path):
            print(f"  Warning: No .dslog pair for {os.path.basename(path)}, skipping.")
            continue

        try:
            parsed = parse_dsevents_path(path)
        except Exception as e:
            print(f"  Warning: Could not parse {os.path.basename(path)}: {e}")
            continue

        fms_info = extract_fms_info(parsed["events"])
        if not is_real_match(fms_info):
            continue

        file_infos.append({
            "path": path,
            "fms_info": fms_info,
            "header_timestamp": parsed["header"]["timestamp"],
            "parsed": parsed,
        })

    if not file_infos:
        return {}

    # Group by match
    groups = group_files_by_match(file_infos)

    # Remove already-processed matches
    existing = get_existing_match_prefixes(dest_dir)
    filtered = {}
    for key, files in groups.items():
        fms = files[0]["fms_info"]
        match_id = build_match_id(fms["match_type"], fms["match_number"], fms["replay"])
        if match_id not in existing:
            filtered[key] = files

    return filtered


def display_matches(matches):
    """Display found matches and return match_id mapping."""
    print("\nNew matches found:")
    match_ids = {}
    for key, files in sorted(matches.items()):
        fms = files[0]["fms_info"]
        match_id = build_match_id(fms["match_type"], fms["match_number"], fms["replay"])
        match_ids[key] = match_id
        pair_count = len(files)
        desc = f"{fms['match_type']} {fms['match_number']}"
        if fms["match_type"] == "Elimination":
            desc += f" Replay {fms['replay']}"
        if pair_count > 1:
            pairs = f"{pair_count} log pairs — robot restart detected"
        else:
            pairs = "1 log pair"
        print(f"  {match_id:<8} - {desc} ({pairs})")
    return match_ids


def process_match(key, files, match_id, event_name, source_dir, dest_dir):
    """Process a single match: parse events, write summary, copy files."""
    fms_info = files[0]["fms_info"]

    log_entries = []
    events_by_log = {}
    transition_events = {}
    all_dslog_records = []

    for seq, fi in enumerate(files, start=1):
        basename = os.path.splitext(os.path.basename(fi["path"]))[0]
        log_entries.append({
            "seq": seq,
            "basename": basename,
            "dsevents_path": fi["path"],
        })

        # Format and collapse dsevents
        formatted = format_events(fi["parsed"])
        collapsed = collapse_repeats(formatted)
        events_by_log[seq] = collapsed

        # Parse dslog
        dslog_path = fi["path"].rsplit(".dsevents", 1)[0] + ".dslog"
        if os.path.exists(dslog_path):
            dslog_data = parse_dslog_path(dslog_path)
            if dslog_data["records"]:
                all_dslog_records.extend(dslog_data["records"])
                transitions = detect_transitions(dslog_data["records"])
                # Skip initial mode transition (record 0) — it's context, not an event
                transition_events[seq] = [t for t in transitions[1:]]

    # Extract joystick info
    joysticks = []
    for fi in files:
        joysticks = extract_joystick_info(fi["parsed"]["events"])
        if joysticks:
            break

    # Compute telemetry across all logs
    telemetry = compute_telemetry(all_dslog_records)

    # Generate match_events.txt
    txt = format_match_events_txt(
        fms_info, match_id, event_name, log_entries, events_by_log, joysticks,
        telemetry=telemetry, transition_events=transition_events,
    )

    # Write files
    write_match_events_file(dest_dir, match_id, txt)
    copy_match_files(match_id, log_entries, source_dir, dest_dir)

    print(f"  {match_id}: wrote {match_id}_match_events.txt + {len(log_entries)} log pair(s)")


def main():
    parser = argparse.ArgumentParser(
        description="FRC Match Log Processor — identify match .dsevents/.dslog files "
                    "and organize them into an event folder."
    )
    parser.add_argument("source_dir", help="Directory containing .dsevents and .dslog files")
    parser.add_argument("dest_dir", help="Destination directory for organized match files")

    parser.add_argument("--event", required=True,
                        help="The Blue Alliance event key (e.g., 2026ncpem). "
                             "Find it at https://www.thebluealliance.com — the key is in the event URL.")

    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument("--today", action="store_true",
                            help="Only scan files from today's date")
    date_group.add_argument("--date", metavar="YYYY-MM-DD",
                            help="Only scan files from the specified date")

    args = parser.parse_args()

    # Validate directories
    if not os.path.isdir(args.source_dir):
        print(f"Error: Source directory does not exist: {args.source_dir}")
        sys.exit(1)
    if not os.path.isdir(args.dest_dir):
        print(f"Error: Destination directory does not exist: {args.dest_dir}")
        sys.exit(1)

    date_filter = get_date_filter(args)

    print(f"Scanning {args.source_dir} for match files...")

    # Check for .dsevents files first (distinct message per spec)
    dsevents_files = find_dsevents_files(args.source_dir, date_filter)
    if not dsevents_files:
        print("No .dsevents files found.")
        sys.exit(0)

    matches = scan_and_identify(dsevents_files, args.dest_dir)

    if not matches:
        print("No new matches found.")
        sys.exit(0)

    match_ids = display_matches(matches)

    # Confirm
    response = input("\nProcess these matches? [Y/n] ").strip().lower()
    if response and response != "y":
        print("Aborted.")
        sys.exit(0)

    # Process
    print()
    for key, files in sorted(matches.items()):
        process_match(key, files, match_ids[key], args.event, args.source_dir, args.dest_dir)

    print("\nDone.")


if __name__ == "__main__":
    main()

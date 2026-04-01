#!/usr/bin/env python3
"""Power Analyzer — detect voltage dips and report per-channel PDH currents."""

import argparse
import os
import sys

from shared.dslog_parser import parse_dslog_records
from shared.dsevents_parser import parse_dsevents_path
from shared.event_formatter import format_events
from dslog_processor import detect_transitions
from dip_detector import detect_dips
from profile_parser import parse_profile
from report_formatter import format_dip_report, format_event_log


def find_paired_file(log_path):
    """Find the paired .dslog/.dsevents file by swapping the extension.

    Returns:
        tuple (dslog_path, dsevents_path). dsevents_path may be None.
        Raises SystemExit if dslog is missing.
    """
    base, ext = os.path.splitext(log_path)
    ext_lower = ext.lower()

    if ext_lower == ".dslog":
        dslog_path = log_path
        dsevents_path = base + ".dsevents"
    elif ext_lower == ".dsevents":
        dslog_path = base + ".dslog"
        dsevents_path = log_path
    else:
        print(f"Error: Expected .dslog or .dsevents file, got: {ext}")
        sys.exit(1)

    if not os.path.exists(dslog_path):
        print(f"Error: .dslog file not found: {dslog_path}")
        sys.exit(1)

    if not os.path.exists(dsevents_path):
        print(f"  Warning: No .dsevents file found at {dsevents_path}")
        dsevents_path = None

    return dslog_path, dsevents_path


def run_analysis(log_file, profile_path, voltage_threshold=10.0,
                 current_threshold=1.0, output_dir=None):
    """Run the full power analysis pipeline."""
    dslog_path, dsevents_path = find_paired_file(log_file)
    profile = parse_profile(profile_path)

    if output_dir is None:
        output_dir = os.path.dirname(dslog_path)

    basename = os.path.splitext(os.path.basename(dslog_path))[0]
    profile_name = os.path.basename(profile_path)

    with open(dslog_path, "rb") as f:
        dslog_data = f.read()

    records = list(parse_dslog_records(dslog_data))
    if not records:
        print("  Warning: No valid dslog records found.")

    dips = detect_dips(records, voltage_threshold=voltage_threshold)

    report = format_dip_report(
        basename=basename,
        dips=dips,
        profile=profile,
        voltage_threshold=voltage_threshold,
        current_threshold=current_threshold,
        profile_name=profile_name,
    )
    dip_path = os.path.join(output_dir, f"{basename}_dips.txt")
    with open(dip_path, "w") as f:
        f.write(report)
    print(f"  Dip report: {dip_path}")

    if dsevents_path is not None:
        parsed_events = parse_dsevents_path(dsevents_path)
        formatted_events = format_events(parsed_events)
        transitions = detect_transitions(records)
        event_log = format_event_log(
            basename=basename,
            events=formatted_events,
            transitions=transitions,
        )
        event_path = os.path.join(output_dir, f"{basename}_events.txt")
        with open(event_path, "w") as f:
            f.write(event_log)
        print(f"  Event log: {event_path}")

    if dips:
        lowest = min(d["min_voltage"] for d in dips)
        print(f"  {len(dips)} voltage dip{'s' if len(dips) != 1 else ''} detected (lowest: {lowest:.2f}V)")
    else:
        print(f"  No voltage dips below {voltage_threshold}V detected.")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze FRC .dslog files for voltage dips and per-channel PDH currents."
    )
    parser.add_argument("log_file",
                        help="Path to a .dslog or .dsevents file. "
                             "The paired file is auto-detected.")
    parser.add_argument("--profile", required=True,
                        help="Path to robot profile CSV mapping PDH channels to motors.")
    parser.add_argument("--voltage-threshold", type=float, default=10.0,
                        help="Voltage below which a dip is reported (default: 10.0V)")
    parser.add_argument("--current-threshold", type=float, default=1.0,
                        help="Minimum peak current to include in table (default: 1.0A)")
    parser.add_argument("--output-dir",
                        help="Output directory (default: same as input file)")

    args = parser.parse_args()

    if not os.path.exists(args.log_file):
        print(f"Error: File not found: {args.log_file}")
        sys.exit(1)
    if not os.path.exists(args.profile):
        print(f"Error: Profile file not found: {args.profile}")
        sys.exit(1)
    if args.output_dir and not os.path.isdir(args.output_dir):
        print(f"Error: Output directory does not exist: {args.output_dir}")
        sys.exit(1)

    run_analysis(
        log_file=args.log_file,
        profile_path=args.profile,
        voltage_threshold=args.voltage_threshold,
        current_threshold=args.current_threshold,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()

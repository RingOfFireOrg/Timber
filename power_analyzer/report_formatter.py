"""Format dip report and event log output files."""


def format_dip_report(basename, dips, profile, voltage_threshold,
                      current_threshold, profile_name):
    """Format the voltage dip analysis report.

    Args:
        basename: log file basename for the header.
        dips: list of dip dicts from detect_dips.
        profile: dict from parse_profile (channel -> {can_id, description}).
        voltage_threshold: threshold used for detection.
        current_threshold: minimum peak current to show a channel row.
        profile_name: profile filename for the header.

    Returns:
        Formatted report string.
    """
    lines = []
    lines.append(f"Power Dip Analysis: {basename}")
    lines.append(f"Voltage Threshold: {voltage_threshold}V")
    lines.append(f"Current Threshold: {current_threshold}A")
    lines.append(f"Profile: {profile_name}")
    lines.append("")

    if not dips:
        lines.append(f"Summary: No voltage dips below {voltage_threshold}V detected.")
        lines.append("")
        return "\n".join(lines)

    lowest_voltage = min(d["min_voltage"] for d in dips)

    for i, dip in enumerate(dips, start=1):
        if dip["recovered"]:
            duration_str = f"lasted {dip['duration_s']:.1f}s"
        else:
            duration_str = "did not recover (log ended)"

        lines.append(f"=== Dip {i} at {dip['start_time']}s — min {dip['min_voltage']:.2f}V, {duration_str} ===")
        lines.append("")

        if dip["peak_currents"]:
            _format_channel_table(lines, dip, profile, current_threshold)
        else:
            lines.append("  (No power distribution data available)")

        lines.append("")

        if dip["recovered"]:
            rv = dip.get("recovery_voltage")
            if rv is not None:
                lines.append(f"=== Recovered at {dip['end_time']}s — {rv:.1f}V ===")
            else:
                lines.append(f"=== Recovered at {dip['end_time']}s ===")
            lines.append("")

    lines.append(f"Summary: {len(dips)} dip{'s' if len(dips) != 1 else ''} detected, lowest voltage: {lowest_voltage:.2f}V")
    lines.append("")
    return "\n".join(lines)


def _format_channel_table(lines, dip, profile, current_threshold):
    """Format the per-channel current table for a single dip."""
    lines.append("  Ch  | Peak A | CAN ID | Description")
    lines.append("  ----|--------|--------|------------------")

    total_current = 0.0
    for ch in sorted(dip["peak_currents"].keys()):
        amps = dip["peak_currents"][ch]
        if amps < current_threshold:
            continue

        total_current += amps

        if ch in profile:
            can_str = str(profile[ch]["can_id"]).center(4)
            desc = profile[ch]["description"]
        else:
            can_str = " —  "
            desc = "(unmapped)"

        lines.append(f"  {ch:>3}  | {amps:>5.1f}  | {can_str} | {desc}")

    lines.append(f"  Total: {total_current:.1f} A @ {dip['min_voltage']:.2f}V")


def format_event_log(basename, events, transitions):
    """Format the chronological event log.

    Args:
        basename: log file basename for the header.
        events: list of event dicts from format_events (time, display).
        transitions: list of transition dicts from detect_transitions (time, display).

    Returns:
        Formatted event log string.
    """
    lines = []
    lines.append(f"Event Log: {basename}")
    lines.append("")

    merged = list(events) + list(transitions)
    merged.sort(key=lambda e: e["time"])

    for event in merged:
        lines.append(f"{event['time']}  {event['display']}")

    lines.append("")
    return "\n".join(lines)

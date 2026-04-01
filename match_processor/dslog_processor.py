"""dslog processing: mode transition detection and telemetry summary."""

DEBOUNCE_COUNT = 5  # 5 records × 20ms = 100ms
RECORD_INTERVAL = 0.020  # 20ms between records


def _format_timestamp(record_index):
    """Format record index as relative timestamp: 'SSS.mmm' (7 chars, zero-padded, 3 decimals)."""
    seconds = record_index * RECORD_INTERVAL
    return f"{seconds:07.3f}"


def detect_transitions(records):
    """Detect debounced mode transitions from parsed dslog records.

    Args:
        records: list of record dicts from parse_dslog_records (must have 'mode' and 'index' keys).

    Returns:
        list of transition event dicts: {"time": "SSS.mmm", "display": "***** Transition: <mode>", "mode": "<mode>"}
        The first entry is the initial mode (record 0).
    """
    if not records:
        return []

    transitions = []

    # Initial mode (no debounce needed per spec)
    confirmed_mode = records[0]["mode"]
    transitions.append({
        "time": _format_timestamp(records[0]["index"]),
        "display": f"***** Transition: {confirmed_mode}",
        "mode": confirmed_mode,
    })

    streak_mode = None
    streak_start_index = 0
    streak_count = 0

    for rec in records[1:]:
        mode = rec["mode"]
        if mode != confirmed_mode:
            if mode == streak_mode:
                streak_count += 1
            else:
                streak_mode = mode
                streak_start_index = rec["index"]
                streak_count = 1

            if streak_count >= DEBOUNCE_COUNT:
                confirmed_mode = streak_mode
                transitions.append({
                    "time": _format_timestamp(streak_start_index),
                    "display": f"***** Transition: {confirmed_mode}",
                    "mode": confirmed_mode,
                })
                streak_mode = None
                streak_count = 0
        else:
            streak_mode = None
            streak_count = 0

    return transitions


# Voltage range for valid records (exclude pre-connection garbage)
VOLTAGE_MIN_VALID = 6.0
VOLTAGE_MAX_VALID = 16.0


def compute_telemetry(records):
    """Compute whole-match min/max telemetry from parsed dslog records.

    Only includes records with plausible voltage (6.0 < V < 16.0).
    Returns dict with *_min/*_max keys, or None if no valid records.
    """
    valid = [r for r in records if VOLTAGE_MIN_VALID < r["voltage"] < VOLTAGE_MAX_VALID]

    if not valid:
        return None

    return {
        "voltage_min": min(r["voltage"] for r in valid),
        "voltage_max": max(r["voltage"] for r in valid),
        "cpu_min": min(r["cpu"] * 100 for r in valid),
        "cpu_max": max(r["cpu"] * 100 for r in valid),
        "can_min": min(r["can"] * 100 for r in valid),
        "can_max": max(r["can"] * 100 for r in valid),
        "trip_min": min(r["trip_ms"] for r in valid),
        "trip_max": max(r["trip_ms"] for r in valid),
        "packet_loss_min": min(r["packet_loss"] * 100 for r in valid),
        "packet_loss_max": max(r["packet_loss"] * 100 for r in valid),
    }

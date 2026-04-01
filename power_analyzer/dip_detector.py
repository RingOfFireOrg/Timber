"""Detect voltage dips in dslog records and track per-channel peak currents."""

from pdh_decoder import decode_currents

RECORD_INTERVAL = 0.020  # 20ms between records (50 Hz)
DEBOUNCE_COUNT = 5        # 5 consecutive records above threshold = confirmed recovery (100ms)
VOLTAGE_MIN_PLAUSIBLE = 1.0   # below this, record is pre-connection garbage
VOLTAGE_MAX_PLAUSIBLE = 16.0  # above this, record is invalid


def _format_timestamp(record_index):
    """Format record index as relative timestamp: 'SSS.SSS' (7 chars, zero-padded, 3 decimals)."""
    seconds = record_index * RECORD_INTERVAL
    return f"{seconds:07.3f}"


def detect_dips(records, voltage_threshold=10.0):
    """Detect voltage dips and track per-channel peak currents during each dip.

    Args:
        records: list of record dicts from parse_dslog_records.
            Each must have: index, voltage, pd_type, pd_data.
        voltage_threshold: voltage below which a dip starts (default 10.0V).

    Returns:
        list of dip dicts, each containing:
            - start_index, start_time, end_index, end_time
            - min_voltage, duration_s, peak_currents, recovered, recovery_voltage
    """
    dips = []
    in_dip = False
    dip_start_index = 0
    min_voltage = 0.0
    peak_currents = {}
    recovery_streak = 0
    recovery_start_index = 0
    recovery_voltage = 0.0

    for rec in records:
        v = rec["voltage"]

        if v <= VOLTAGE_MIN_PLAUSIBLE or v >= VOLTAGE_MAX_PLAUSIBLE:
            continue

        if not in_dip:
            if v < voltage_threshold:
                in_dip = True
                dip_start_index = rec["index"]
                min_voltage = v
                peak_currents = {}
                recovery_streak = 0
                _update_peak_currents(peak_currents, rec)
        else:
            if v >= voltage_threshold:
                if recovery_streak == 0:
                    recovery_start_index = rec["index"]
                    recovery_voltage = v
                recovery_streak += 1

                if recovery_streak >= DEBOUNCE_COUNT:
                    dips.append(_make_dip(
                        dip_start_index, recovery_start_index,
                        min_voltage, peak_currents, recovered=True,
                        recovery_voltage=recovery_voltage,
                    ))
                    in_dip = False
            else:
                recovery_streak = 0
                if v < min_voltage:
                    min_voltage = v
                _update_peak_currents(peak_currents, rec)

    if in_dip:
        dips.append(_make_dip(
            dip_start_index, None, min_voltage, peak_currents, recovered=False,
        ))

    return dips


def _update_peak_currents(peak_currents, rec):
    """Update peak current tracking for a record during a dip."""
    currents = decode_currents(rec["pd_type"], rec["pd_data"])
    if currents is None:
        return
    for ch, amps in currents.items():
        if ch not in peak_currents or amps > peak_currents[ch]:
            peak_currents[ch] = amps


def _make_dip(start_index, end_index, min_voltage, peak_currents, recovered,
              recovery_voltage=None):
    """Construct a dip result dict."""
    start_time = _format_timestamp(start_index)
    end_time = _format_timestamp(end_index) if end_index is not None else None
    duration = None
    if end_index is not None:
        duration = round((end_index - start_index) * RECORD_INTERVAL, 3)

    return {
        "start_index": start_index,
        "start_time": start_time,
        "end_index": end_index,
        "end_time": end_time,
        "min_voltage": min_voltage,
        "duration_s": duration,
        "peak_currents": peak_currents,
        "recovered": recovered,
        "recovery_voltage": recovery_voltage,
    }

"""Tests for dip report and event log formatting."""


def test_format_dip_report_no_dips():
    from report_formatter import format_dip_report
    result = format_dip_report(
        basename="2026_03_28 17_45_53 Sat",
        dips=[],
        profile={},
        voltage_threshold=10.0,
        current_threshold=1.0,
        profile_name="robot.csv",
    )
    assert "No voltage dips below 10.0V detected" in result
    assert "Summary:" in result


def test_format_dip_report_single_dip():
    from report_formatter import format_dip_report
    dip = {
        "start_index": 100,
        "start_time": "002.000",
        "end_index": 115,
        "end_time": "002.300",
        "min_voltage": 8.12,
        "duration_s": 0.3,
        "peak_currents": {0: 53.5, 5: 0.2, 14: 60.1},
        "recovered": True,
        "recovery_voltage": 11.2,
    }
    profile = {
        0: {"can_id": 10, "description": "Front Left Drive NEO"},
        14: {"can_id": 25, "description": "Shooter NEO"},
    }
    result = format_dip_report(
        basename="test",
        dips=[dip],
        profile=profile,
        voltage_threshold=10.0,
        current_threshold=1.0,
        profile_name="robot.csv",
    )
    assert "Dip 1 at 002.000s" in result
    assert "min 8.12V" in result
    assert "Front Left Drive NEO" in result
    assert "Shooter NEO" in result
    assert "Front Right" not in result
    assert "Recovered at 002.300s" in result
    assert "11.2V" in result
    assert "Summary: 1 dip" in result


def test_format_dip_report_unmapped_channel():
    from report_formatter import format_dip_report
    dip = {
        "start_index": 100,
        "start_time": "002.000",
        "end_index": 115,
        "end_time": "002.300",
        "min_voltage": 9.0,
        "duration_s": 0.3,
        "peak_currents": {7: 53.5},
        "recovered": True,
        "recovery_voltage": 10.5,
    }
    result = format_dip_report(
        basename="test", dips=[dip], profile={},
        voltage_threshold=10.0, current_threshold=1.0, profile_name="robot.csv",
    )
    assert "(unmapped)" in result
    assert "\u2014" in result or "—" in result


def test_format_dip_report_no_recovery():
    from report_formatter import format_dip_report
    dip = {
        "start_index": 100,
        "start_time": "002.000",
        "end_index": None,
        "end_time": None,
        "min_voltage": 7.01,
        "duration_s": None,
        "peak_currents": {0: 50.0},
        "recovered": False,
    }
    result = format_dip_report(
        basename="test", dips=[dip], profile={0: {"can_id": 10, "description": "Motor"}},
        voltage_threshold=10.0, current_threshold=1.0, profile_name="robot.csv",
    )
    assert "did not recover" in result


def test_format_event_log_basic():
    from report_formatter import format_event_log
    events = [
        {"time": "000.000", "display": "FMS Connected"},
        {"time": "150.223", "display": "Code Start Notification"},
    ]
    transitions = [
        {"time": "563.360", "display": "***** Transition: Autonomous"},
    ]
    result = format_event_log(
        basename="2026_03_28 17_45_53 Sat",
        events=events,
        transitions=transitions,
    )
    assert "Event Log: 2026_03_28 17_45_53 Sat" in result
    assert "000.000  FMS Connected" in result
    assert "563.360  ***** Transition: Autonomous" in result


def test_format_event_log_sorted():
    from report_formatter import format_event_log
    events = [{"time": "200.000", "display": "Late event"}]
    transitions = [{"time": "100.000", "display": "***** Transition: Teleop"}]
    result = format_event_log(basename="test", events=events, transitions=transitions)
    lines = result.strip().split("\n")
    event_lines = [l for l in lines if l.strip() and not l.startswith("Event Log")]
    assert "100.000" in event_lines[0]
    assert "200.000" in event_lines[1]

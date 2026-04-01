from shared.tests.conftest import make_dslog_file


def test_no_transitions_single_mode():
    from dslog_processor import detect_transitions
    # 10 records, all Disabled (0xFE)
    records_args = [{"voltage_raw": 3072, "status": 0xFE}] * 10
    data = make_dslog_file(records_args)

    from shared.dslog_parser import parse_dslog_records
    records = list(parse_dslog_records(data))
    transitions = detect_transitions(records)
    # Initial mode counts as first transition
    assert len(transitions) == 1
    assert transitions[0]["mode"] == "Disabled"
    assert transitions[0]["time"] == "000.000"


def test_transition_after_debounce():
    from dslog_processor import detect_transitions
    # 5 Disabled, then 5 Autonomous (exactly at debounce threshold)
    records_args = (
        [{"voltage_raw": 3072, "status": 0xFE}] * 5 +
        [{"voltage_raw": 3072, "status": 0xFD}] * 5
    )
    data = make_dslog_file(records_args)

    from shared.dslog_parser import parse_dslog_records
    records = list(parse_dslog_records(data))
    transitions = detect_transitions(records)
    assert len(transitions) == 2
    assert transitions[0]["mode"] == "Disabled"
    assert transitions[1]["mode"] == "Autonomous"
    # Timestamp of transition = first record in new mode = record 5 = 0.100s
    assert transitions[1]["time"] == "000.100"


def test_transition_not_confirmed_under_threshold():
    from dslog_processor import detect_transitions
    # 5 Disabled, 4 Autonomous (not enough), back to Disabled
    records_args = (
        [{"voltage_raw": 3072, "status": 0xFE}] * 5 +
        [{"voltage_raw": 3072, "status": 0xFD}] * 4 +
        [{"voltage_raw": 3072, "status": 0xFE}] * 5
    )
    data = make_dslog_file(records_args)

    from shared.dslog_parser import parse_dslog_records
    records = list(parse_dslog_records(data))
    transitions = detect_transitions(records)
    assert len(transitions) == 1  # Only initial Disabled
    assert transitions[0]["mode"] == "Disabled"


def test_transition_flicker_ignored():
    from dslog_processor import detect_transitions
    # Disabled base with single-record flickers to Autonomous (flickers never reach debounce threshold)
    records_args = (
        [{"voltage_raw": 3072, "status": 0xFE}] * 5 +  # Disabled (stable start)
        # Interleave flickers — never 5 consecutive Autonomous
        [{"voltage_raw": 3072, "status": 0xFD}] * 1 +
        [{"voltage_raw": 3072, "status": 0xFE}] * 3 +
        [{"voltage_raw": 3072, "status": 0xFD}] * 1 +
        [{"voltage_raw": 3072, "status": 0xFE}] * 3 +
        [{"voltage_raw": 3072, "status": 0xFD}] * 1 +
        [{"voltage_raw": 3072, "status": 0xFE}] * 6
    )
    data = make_dslog_file(records_args)

    from shared.dslog_parser import parse_dslog_records
    records = list(parse_dslog_records(data))
    transitions = detect_transitions(records)
    assert len(transitions) == 1
    assert transitions[0]["mode"] == "Disabled"


def test_full_match_sequence():
    from dslog_processor import detect_transitions
    # Disconnected → Disabled → Autonomous → Disabled → Teleop → Disabled
    records_args = (
        [{"voltage_raw": 3072, "status": 0xFF}] * 10 +   # Disconnected
        [{"voltage_raw": 3072, "status": 0xFE}] * 10 +   # Disabled
        [{"voltage_raw": 3072, "status": 0xFD}] * 10 +   # Autonomous
        [{"voltage_raw": 3072, "status": 0xFE}] * 10 +   # Disabled
        [{"voltage_raw": 3072, "status": 0xFB}] * 10 +   # Teleop
        [{"voltage_raw": 3072, "status": 0xFE}] * 10      # Disabled
    )
    data = make_dslog_file(records_args)

    from shared.dslog_parser import parse_dslog_records
    records = list(parse_dslog_records(data))
    transitions = detect_transitions(records)
    modes = [t["mode"] for t in transitions]
    assert modes == ["Disconnected", "Disabled", "Autonomous", "Disabled", "Teleop", "Disabled"]


def test_transition_display_format():
    from dslog_processor import detect_transitions
    records_args = (
        [{"voltage_raw": 3072, "status": 0xFE}] * 5 +
        [{"voltage_raw": 3072, "status": 0xFD}] * 5
    )
    data = make_dslog_file(records_args)

    from shared.dslog_parser import parse_dslog_records
    records = list(parse_dslog_records(data))
    transitions = detect_transitions(records)
    assert transitions[1]["display"] == "***** Transition: Autonomous"


def test_telemetry_summary_basic():
    from dslog_processor import compute_telemetry
    from shared.dslog_parser import parse_dslog_records

    records_args = [
        {"voltage_raw": 2048, "cpu": 50, "can": 100, "trip": 4, "pkt_loss": 10, "status": 0xFE},
        {"voltage_raw": 3200, "cpu": 100, "can": 200, "trip": 20, "pkt_loss": 25, "status": 0xFE},
    ]
    data = make_dslog_file(records_args)
    records = list(parse_dslog_records(data))
    telemetry = compute_telemetry(records)

    assert telemetry is not None
    assert abs(telemetry["voltage_min"] - 8.0) < 0.01    # 2048/256
    assert abs(telemetry["voltage_max"] - 12.5) < 0.01   # 3200/256
    assert abs(telemetry["cpu_min"] - 25.0) < 0.1        # 50 × 0.5 × 0.01 = 0.25 → 25%
    assert abs(telemetry["cpu_max"] - 50.0) < 0.1        # 100 × 0.5 × 0.01 = 0.50 → 50%


def test_telemetry_excludes_garbage_voltage():
    from dslog_processor import compute_telemetry
    from shared.dslog_parser import parse_dslog_records

    records_args = [
        {"voltage_raw": 256, "status": 0xFE},     # 1.0V — garbage, excluded
        {"voltage_raw": 65535, "status": 0xFE},    # 255.99V — garbage, excluded
        {"voltage_raw": 2560, "cpu": 0, "can": 0, "trip": 0, "pkt_loss": 0, "status": 0xFE},  # 10.0V — valid
    ]
    data = make_dslog_file(records_args)
    records = list(parse_dslog_records(data))
    telemetry = compute_telemetry(records)

    assert telemetry is not None
    assert abs(telemetry["voltage_min"] - 10.0) < 0.01
    assert abs(telemetry["voltage_max"] - 10.0) < 0.01


def test_telemetry_none_when_no_valid_records():
    from dslog_processor import compute_telemetry
    from shared.dslog_parser import parse_dslog_records

    # All records have garbage voltage
    records_args = [{"voltage_raw": 65535, "status": 0xFF}] * 5
    data = make_dslog_file(records_args)
    records = list(parse_dslog_records(data))
    telemetry = compute_telemetry(records)

    assert telemetry is None


def test_telemetry_none_when_empty():
    from dslog_processor import compute_telemetry
    telemetry = compute_telemetry([])
    assert telemetry is None

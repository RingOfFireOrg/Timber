from conftest import make_dslog_file


def test_no_transitions_single_mode():
    from dslog_processor import detect_transitions
    # 10 records, all Disabled (0xFE)
    records_args = [{"voltage_raw": 3072, "status": 0xFE}] * 10
    data = make_dslog_file(records_args)

    from dslog_parser import parse_dslog_records
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

    from dslog_parser import parse_dslog_records
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

    from dslog_parser import parse_dslog_records
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

    from dslog_parser import parse_dslog_records
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

    from dslog_parser import parse_dslog_records
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

    from dslog_parser import parse_dslog_records
    records = list(parse_dslog_records(data))
    transitions = detect_transitions(records)
    assert transitions[1]["display"] == "***** Transition: Autonomous"

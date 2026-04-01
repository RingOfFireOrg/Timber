import os

from conftest import make_dsevents_file


def test_format_match_events_header():
    from match_writer import format_match_events_txt
    fms_info = {
        "match_type": "Qualification",
        "match_number": 52,
        "replay": 1,
        "field_time": "26/3/29 13:35:4",
        "ds_version": "FRC Driver Station - Version 26.0",
    }
    match_id = "Q52"
    log_files = [{"seq": 1, "basename": "2026_03_29 09_34_29 Sun"}]
    events_by_log = {1: [
        {"time": "000.000", "display": "FMS Connected"},
        {"time": "001.000", "display": "Code Start Notification"},
    ]}
    joysticks = [{"number": 0, "name": "Controller (Xbox One For Windows)", "axes": 6, "buttons": 16, "povs": 1}]

    txt = format_match_events_txt(fms_info, match_id, "2026ncpem", log_files, events_by_log, joysticks)

    assert "Match: Qualification 52" in txt
    assert "Event: 2026ncpem" in txt
    assert "Field Time: 26/3/29 13:35:4" in txt
    assert "DS Version: FRC Driver Station - Version 26.0" in txt
    assert "Replay: 1" in txt
    assert "The Blue Alliance: https://www.thebluealliance.com/match/2026ncpem_qm52" in txt
    assert "[1] 2026_03_29 09_34_29 Sun (Q52_1_)" in txt
    assert "[1] 000.000  FMS Connected" in txt
    assert "0: Controller (Xbox One For Windows) - 6 axes, 16 buttons, 1 POV" in txt
    assert "NOTE:" not in txt


def test_format_match_events_multi_log():
    from match_writer import format_match_events_txt
    fms_info = {
        "match_type": "Qualification",
        "match_number": 60,
        "replay": 1,
        "field_time": "26/3/29 14:00:0",
        "ds_version": "FRC Driver Station - Version 26.0",
    }
    match_id = "Q60"
    log_files = [
        {"seq": 1, "basename": "2026_03_29 09_34_29 Sun"},
        {"seq": 2, "basename": "2026_03_29 09_40_12 Sun"},
    ]
    events_by_log = {
        1: [{"time": "000.000", "display": "FMS Connected"}],
        2: [
            {"time": "000.000", "display": "FMS Connected"},
            {"time": "001.000", "display": "Code Start Notification"},
        ],
    }
    joysticks = []

    txt = format_match_events_txt(fms_info, match_id, "2026ncpem", log_files, events_by_log, joysticks)

    assert "[1]" in txt
    assert "[2]" in txt
    assert "Q60_1_" in txt
    assert "Q60_2_" in txt
    assert "NOTE:" not in txt


def test_copy_match_files(tmp_dirs):
    src, dst = tmp_dirs

    # Create source files
    dsevents_data = make_dsevents_file(["test event"])
    dsevents_path = src / "2026_03_29 09_34_29 Sun.dsevents"
    dsevents_path.write_bytes(dsevents_data)
    dslog_path = src / "2026_03_29 09_34_29 Sun.dslog"
    dslog_path.write_bytes(b"\x00" * 100)

    from match_writer import copy_match_files
    file_entries = [{"seq": 1, "basename": "2026_03_29 09_34_29 Sun", "dsevents_path": str(dsevents_path)}]
    copy_match_files("Q52", file_entries, str(src), str(dst))

    assert (dst / "Q52_1_2026_03_29 09_34_29 Sun.dsevents").exists()
    assert (dst / "Q52_1_2026_03_29 09_34_29 Sun.dslog").exists()


def test_build_tba_url_qualification():
    from match_writer import build_tba_url
    url = build_tba_url("2026ncpem", "Qualification", 13, 1)
    assert url == "https://www.thebluealliance.com/match/2026ncpem_qm13"


def test_build_tba_url_qualification_ignores_replay():
    from match_writer import build_tba_url
    url = build_tba_url("2026ncpem", "Qualification", 13, 2)
    assert url == "https://www.thebluealliance.com/match/2026ncpem_qm13"


def test_build_tba_url_elimination():
    from match_writer import build_tba_url
    url = build_tba_url("2026ncpem", "Elimination", 4, 1)
    assert url == "https://www.thebluealliance.com/match/2026ncpem_sf4m1"


def test_build_tba_url_elimination_replay_2():
    from match_writer import build_tba_url
    url = build_tba_url("2026ncpem", "Elimination", 6, 2)
    assert url == "https://www.thebluealliance.com/match/2026ncpem_sf6m2"


def test_detect_non_participation_true_no_code_start_no_joysticks():
    from match_writer import detect_non_participation
    events_by_log = {1: [
        {"time": "000.418", "display": "ERROR (44004): FRC: The Driver Station has lost communication with the robot."},
        {"time": "000.619", "display": "FMS Connected"},
    ]}
    joysticks = []
    assert detect_non_participation(events_by_log, joysticks) is True


def test_detect_non_participation_false_has_code_start():
    from match_writer import detect_non_participation
    events_by_log = {1: [
        {"time": "000.000", "display": "FMS Connected"},
        {"time": "001.000", "display": "Code Start Notification"},
    ]}
    joysticks = []
    assert detect_non_participation(events_by_log, joysticks) is False


def test_detect_non_participation_false_has_joysticks():
    from match_writer import detect_non_participation
    events_by_log = {1: [
        {"time": "000.000", "display": "FMS Connected"},
    ]}
    joysticks = [{"number": 0, "name": "Xbox", "axes": 6, "buttons": 16, "povs": 1}]
    assert detect_non_participation(events_by_log, joysticks) is False


def test_detect_non_participation_false_code_start_in_second_log():
    from match_writer import detect_non_participation
    events_by_log = {
        1: [{"time": "000.000", "display": "FMS Connected"}],
        2: [{"time": "000.000", "display": "Code Start Notification"}],
    }
    joysticks = []
    assert detect_non_participation(events_by_log, joysticks) is False


def test_format_match_events_includes_tba_link():
    from match_writer import format_match_events_txt
    fms_info = {
        "match_type": "Qualification",
        "match_number": 13,
        "replay": 1,
        "field_time": "26/3/28 17:29:45",
        "ds_version": "FRC Driver Station - Version 26.0",
    }
    log_files = [{"seq": 1, "basename": "2026_03_28 13_29_12 Sat"}]
    events_by_log = {1: [
        {"time": "000.000", "display": "FMS Connected"},
        {"time": "001.000", "display": "Code Start Notification"},
    ]}
    joysticks = [{"number": 0, "name": "Xbox", "axes": 6, "buttons": 16, "povs": 1}]

    txt = format_match_events_txt(fms_info, "Q13", "2026ncpem", log_files, events_by_log, joysticks)

    assert "The Blue Alliance: https://www.thebluealliance.com/match/2026ncpem_qm13" in txt
    # TBA line should come after Replay and before Log Files
    lines = txt.split("\n")
    tba_idx = next(i for i, l in enumerate(lines) if "The Blue Alliance:" in l)
    replay_idx = next(i for i, l in enumerate(lines) if l.startswith("Replay:"))
    log_idx = next(i for i, l in enumerate(lines) if l == "Log Files:")
    assert replay_idx < tba_idx < log_idx


def test_format_match_events_non_participation_note():
    from match_writer import format_match_events_txt
    fms_info = {
        "match_type": "Elimination",
        "match_number": 3,
        "replay": 1,
        "field_time": "26/3/29 17:42:4",
        "ds_version": "FRC Driver Station - Version 26.0",
    }
    log_files = [{"seq": 1, "basename": "2026_03_29 13_41_30 Sun"}]
    events_by_log = {1: [
        {"time": "000.418", "display": "ERROR (44004): FRC: The Driver Station has lost communication with the robot."},
        {"time": "000.619", "display": "FMS Connected"},
    ]}
    joysticks = []

    txt = format_match_events_txt(fms_info, "E3_R1", "2026ncpem", log_files, events_by_log, joysticks)

    assert "NOTE: The robot does not appear to have participated in this match." in txt
    assert "The Blue Alliance: https://www.thebluealliance.com/match/2026ncpem_sf3m1" in txt
    # NOTE should come after TBA line and before Log Files
    lines = txt.split("\n")
    note_idx = next(i for i, l in enumerate(lines) if l.startswith("NOTE:"))
    tba_idx = next(i for i, l in enumerate(lines) if "The Blue Alliance:" in l)
    log_idx = next(i for i, l in enumerate(lines) if l == "Log Files:")
    assert tba_idx < note_idx < log_idx


def test_format_match_events_no_note_when_participating():
    from match_writer import format_match_events_txt
    fms_info = {
        "match_type": "Qualification",
        "match_number": 52,
        "replay": 1,
        "field_time": "26/3/29 13:35:4",
        "ds_version": "FRC Driver Station - Version 26.0",
    }
    log_files = [{"seq": 1, "basename": "2026_03_29 09_34_29 Sun"}]
    events_by_log = {1: [
        {"time": "000.000", "display": "FMS Connected"},
        {"time": "001.000", "display": "Code Start Notification"},
    ]}
    joysticks = [{"number": 0, "name": "Xbox", "axes": 6, "buttons": 16, "povs": 1}]

    txt = format_match_events_txt(fms_info, "Q52", "2026ncpem", log_files, events_by_log, joysticks)

    assert "NOTE:" not in txt


def test_write_match_events_file(tmp_dirs):
    _, dst = tmp_dirs

    from match_writer import write_match_events_file
    write_match_events_file(str(dst), "Q52", "Match: Qualification 52\n...")

    path = dst / "Q52_match_events.txt"
    assert path.exists()
    assert "Qualification 52" in path.read_text()


def test_section_order_joysticks_telemetry_before_events():
    from match_writer import format_match_events_txt
    fms_info = {
        "match_type": "Qualification", "match_number": 39, "replay": 1,
        "field_time": "26/3/28 21:45:53",
        "ds_version": "FRC Driver Station - Version 26.0",
    }
    log_files = [{"seq": 1, "basename": "2026_03_28 17_45_53 Sat"}]
    events_by_log = {1: [{"time": "000.000", "display": "FMS Connected"}]}
    joysticks = [{"number": 0, "name": "Xbox", "axes": 6, "buttons": 16, "povs": 1}]
    telemetry = {
        "voltage_min": 7.43, "voltage_max": 12.71,
        "cpu_min": 0, "cpu_max": 67,
        "can_min": 0, "can_max": 100,
        "trip_min": 0.0, "trip_max": 11.0,
        "packet_loss_min": 0, "packet_loss_max": 40,
    }

    txt = format_match_events_txt(fms_info, "Q39", "2026ncpem", log_files, events_by_log, joysticks, telemetry=telemetry)
    lines = txt.split("\n")

    joystick_idx = next(i for i, l in enumerate(lines) if l == "Joysticks:")
    telemetry_idx = next(i for i, l in enumerate(lines) if l == "Telemetry:")
    events_idx = next(i for i, l in enumerate(lines) if l == "Events:")

    assert joystick_idx < telemetry_idx < events_idx


def test_telemetry_section_content():
    from match_writer import format_match_events_txt
    fms_info = {
        "match_type": "Qualification", "match_number": 39, "replay": 1,
        "field_time": "26/3/28 21:45:53",
        "ds_version": "FRC Driver Station - Version 26.0",
    }
    log_files = [{"seq": 1, "basename": "2026_03_28 17_45_53 Sat"}]
    events_by_log = {1: []}
    joysticks = []
    telemetry = {
        "voltage_min": 7.43, "voltage_max": 12.71,
        "cpu_min": 0, "cpu_max": 67,
        "can_min": 0, "can_max": 100,
        "trip_min": 0.0, "trip_max": 11.0,
        "packet_loss_min": 0, "packet_loss_max": 40,
    }

    txt = format_match_events_txt(fms_info, "Q39", "2026ncpem", log_files, events_by_log, joysticks, telemetry=telemetry)

    assert "Voltage: 7.43 - 12.71 V" in txt
    assert "CPU: 0 - 67%" in txt
    assert "CAN Utilization: 0 - 100%" in txt
    assert "Trip Time: 0.0 - 11.0 ms" in txt
    assert "Packet Loss: 0 - 40%" in txt


def test_telemetry_section_none():
    from match_writer import format_match_events_txt
    fms_info = {
        "match_type": "Elimination", "match_number": 3, "replay": 1,
        "field_time": "26/3/29 17:42:4",
        "ds_version": "FRC Driver Station - Version 26.0",
    }
    log_files = [{"seq": 1, "basename": "2026_03_29 13_41_30 Sun"}]
    events_by_log = {1: []}
    joysticks = []

    txt = format_match_events_txt(fms_info, "E3_R1", "2026ncpem", log_files, events_by_log, joysticks, telemetry=None)

    assert "No telemetry data available." in txt

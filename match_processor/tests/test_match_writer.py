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
        "event_name": "NCPEM",
    }
    match_id = "Q52"
    log_files = [{"seq": 1, "basename": "2026_03_29 09_34_29 Sun"}]
    events_by_log = {1: [{"time": "00.000", "display": "FMS Connected"}]}
    joysticks = [{"number": 0, "name": "Controller (Xbox One For Windows)", "axes": 6, "buttons": 16, "povs": 1}]

    txt = format_match_events_txt(fms_info, match_id, log_files, events_by_log, joysticks)

    assert "Match: Qualification 52" in txt
    assert "Event: NCPEM" in txt
    assert "Field Time: 26/3/29 13:35:4" in txt
    assert "DS Version: FRC Driver Station - Version 26.0" in txt
    assert "Replay: 1" in txt
    assert "[1] 2026_03_29 09_34_29 Sun (Q52_1_)" in txt
    assert "[1] 00.000  FMS Connected" in txt
    assert "0: Controller (Xbox One For Windows) - 6 axes, 16 buttons, 1 POV" in txt


def test_format_match_events_multi_log():
    from match_writer import format_match_events_txt
    fms_info = {
        "match_type": "Qualification",
        "match_number": 60,
        "replay": 1,
        "field_time": "26/3/29 14:00:0",
        "ds_version": "FRC Driver Station - Version 26.0",
        "event_name": "NCPEM",
    }
    match_id = "Q60"
    log_files = [
        {"seq": 1, "basename": "2026_03_29 09_34_29 Sun"},
        {"seq": 2, "basename": "2026_03_29 09_40_12 Sun"},
    ]
    events_by_log = {
        1: [{"time": "00.000", "display": "FMS Connected"}],
        2: [{"time": "00.000", "display": "FMS Connected"}],
    }
    joysticks = []

    txt = format_match_events_txt(fms_info, match_id, log_files, events_by_log, joysticks)

    assert "[1]" in txt
    assert "[2]" in txt
    assert "Q60_1_" in txt
    assert "Q60_2_" in txt


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


def test_write_match_events_file(tmp_dirs):
    _, dst = tmp_dirs

    from match_writer import write_match_events_file
    write_match_events_file(str(dst), "Q52", "Match: Qualification 52\n...")

    path = dst / "Q52_match_events.txt"
    assert path.exists()
    assert "Qualification 52" in path.read_text()

import os
import struct

from shared.tests.conftest import make_dsevents_file, make_dsevents_header


def test_extract_fms_info_qualification():
    from match_identifier import extract_fms_info
    events = [
        {"text": 'FMS Connected:   Qualification - 52:1, Field Time: 26/3/29 13:35:4\n -- FRC Driver Station - Version 26.0'},
    ]
    info = extract_fms_info(events)
    assert info["match_type"] == "Qualification"
    assert info["match_number"] == 52
    assert info["replay"] == 1
    assert info["field_time"] == "26/3/29 13:35:4"
    assert info["ds_version"] == "FRC Driver Station - Version 26.0"


def test_extract_fms_info_elimination():
    from match_identifier import extract_fms_info
    events = [
        {"text": 'FMS Connected:   Elimination - 6:1, Field Time: 26/3/29 18:11:7\n -- FRC Driver Station - Version 26.0'},
    ]
    info = extract_fms_info(events)
    assert info["match_type"] == "Elimination"
    assert info["match_number"] == 6
    assert info["replay"] == 1


def test_extract_fms_info_none_match():
    from match_identifier import extract_fms_info
    events = [
        {"text": 'FMS Connected:   None - 0:0, Field Time: -100/0/0 0:0:0\n -- FRC Driver Station - Version 26.0'},
    ]
    info = extract_fms_info(events)
    assert info["match_type"] == "None"


def test_extract_fms_info_no_fms():
    from match_identifier import extract_fms_info
    events = [{"text": "Code Start Notification."}]
    info = extract_fms_info(events)
    assert info is None


def test_extract_joystick_info():
    from match_identifier import extract_joystick_info
    events = [
        {"text": "Info Joystick 0: (Controller (Xbox One For Windows))6 axes, 16 buttons, 1 POVs. "
                 "Info Joystick 1: (Controller (Gamepad F310))6 axes, 10 buttons, 1 POVs. "},
    ]
    joysticks = extract_joystick_info(events)
    assert len(joysticks) == 2
    assert joysticks[0]["number"] == 0
    assert joysticks[0]["name"] == "Controller (Xbox One For Windows)"
    assert joysticks[0]["axes"] == 6
    assert joysticks[1]["number"] == 1


def test_extract_joystick_info_dedup():
    from match_identifier import extract_joystick_info
    events = [
        {"text": "Info Joystick 0: (Xbox)6 axes, 16 buttons, 1 POVs. "},
        {"text": "Info Joystick 0: (Xbox)6 axes, 16 buttons, 1 POVs. "},  # duplicate
    ]
    joysticks = extract_joystick_info(events)
    assert len(joysticks) == 1


def test_build_match_id_qualification():
    from match_identifier import build_match_id
    assert build_match_id("Qualification", 52, 1) == "Q52"
    assert build_match_id("Qualification", 52, 2) == "Q52_R2"


def test_build_match_id_elimination():
    from match_identifier import build_match_id
    assert build_match_id("Elimination", 6, 1) == "E6_R1"
    assert build_match_id("Elimination", 6, 2) == "E6_R2"


def test_is_real_match():
    from match_identifier import is_real_match
    assert is_real_match(None) is False
    assert is_real_match({"match_type": "None"}) is False
    assert is_real_match({"match_type": "Qualification"}) is True
    assert is_real_match({"match_type": "Elimination"}) is True


def test_group_files_by_match():
    from match_identifier import group_files_by_match
    file_infos = [
        {"path": "a.dsevents", "fms_info": {"match_type": "Qualification", "match_number": 52, "replay": 1}, "header_timestamp": 2000.0},
        {"path": "b.dsevents", "fms_info": {"match_type": "Qualification", "match_number": 52, "replay": 1}, "header_timestamp": 1000.0},
        {"path": "c.dsevents", "fms_info": {"match_type": "Qualification", "match_number": 60, "replay": 1}, "header_timestamp": 3000.0},
    ]
    groups = group_files_by_match(file_infos)
    assert len(groups) == 2
    # Q52 group should be sorted by timestamp (b before a)
    q52 = groups["Qualification - 52:1"]
    assert q52[0]["path"] == "b.dsevents"
    assert q52[1]["path"] == "a.dsevents"


def test_build_match_key():
    from match_identifier import build_match_key
    assert build_match_key("Qualification", 52, 1) == "Qualification - 52:1"

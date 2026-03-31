import os
import subprocess
import sys

from conftest import make_dsevents_file


def test_scan_finds_match_files(tmp_dirs):
    src, dst = tmp_dirs

    # Create a match dsevents + dslog pair
    match_data = make_dsevents_file([
        "Info Joystick 0: (Controller (Xbox One For Windows))6 axes, 16 buttons, 1 POVs. ",
        "FMS Connected:   Qualification - 52:1, Field Time: 26/3/29 13:35:4\n"
        " -- FRC Driver Station - Version 26.0",
        "Code Start Notification. ",
    ])
    (src / "2026_03_29 09_34_29 Sun.dsevents").write_bytes(match_data)
    (src / "2026_03_29 09_34_29 Sun.dslog").write_bytes(b"\x00" * 100)

    # Create a non-match dsevents + dslog pair
    nonmatch_data = make_dsevents_file([
        "FMS Connected:   None - 0:0, Field Time: -100/0/0 0:0:0\n"
        " -- FRC Driver Station - Version 26.0",
    ])
    (src / "2026_03_29 10_00_00 Sun.dsevents").write_bytes(nonmatch_data)
    (src / "2026_03_29 10_00_00 Sun.dslog").write_bytes(b"\x00" * 100)

    from process_matches import find_dsevents_files, scan_and_identify
    matches = scan_and_identify(find_dsevents_files(str(src)), str(dst))
    assert len(matches) == 1
    key = list(matches.keys())[0]
    assert "Qualification" in key


def test_skip_existing_matches(tmp_dirs):
    src, dst = tmp_dirs

    match_data = make_dsevents_file([
        "FMS Connected:   Qualification - 52:1, Field Time: 26/3/29 13:35:4\n"
        " -- FRC Driver Station - Version 26.0",
    ])
    (src / "2026_03_29 09_34_29 Sun.dsevents").write_bytes(match_data)
    (src / "2026_03_29 09_34_29 Sun.dslog").write_bytes(b"\x00" * 100)

    # Pre-populate destination with Q52_ files
    (dst / "Q52_match_events.txt").write_text("existing")

    from process_matches import find_dsevents_files, scan_and_identify
    matches = scan_and_identify(find_dsevents_files(str(src)), str(dst))
    assert len(matches) == 0


def test_date_filter(tmp_dirs):
    src, dst = tmp_dirs

    match_data = make_dsevents_file([
        "FMS Connected:   Qualification - 52:1, Field Time: 26/3/29 13:35:4\n"
        " -- FRC Driver Station - Version 26.0",
    ])
    (src / "2026_03_29 09_34_29 Sun.dsevents").write_bytes(match_data)
    (src / "2026_03_29 09_34_29 Sun.dslog").write_bytes(b"\x00" * 100)

    (src / "2026_03_28 09_34_29 Sat.dsevents").write_bytes(match_data)
    (src / "2026_03_28 09_34_29 Sat.dslog").write_bytes(b"\x00" * 100)

    from process_matches import find_dsevents_files, scan_and_identify
    matches = scan_and_identify(find_dsevents_files(str(src), date_filter="2026_03_29"), str(dst))
    assert len(matches) == 1


def test_cli_help():
    result = subprocess.run(
        [sys.executable, "match_processor/process_matches.py", "--help"],
        capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))) or "."
    )
    assert result.returncode == 0
    assert "source_dir" in result.stdout
    assert "dest_dir" in result.stdout


def test_end_to_end_with_real_files(tmp_path):
    """Integration test using real .dsevents files from the repo."""
    dst = tmp_path / "dest"
    dst.mkdir()

    from process_matches import find_dsevents_files, scan_and_identify
    matches = scan_and_identify(find_dsevents_files("2026/03"), str(dst))

    # Should find multiple real matches
    assert len(matches) > 0
    # All keys should be real match types
    for key in matches:
        assert "Qualification" in key or "Elimination" in key


def test_missing_dslog_warns(tmp_dirs, capsys):
    src, dst = tmp_dirs

    match_data = make_dsevents_file([
        "FMS Connected:   Qualification - 99:1, Field Time: 26/3/29 13:35:4\n"
        " -- FRC Driver Station - Version 26.0",
    ])
    (src / "2026_03_29 12_00_00 Sun.dsevents").write_bytes(match_data)
    # Intentionally no .dslog file

    from process_matches import find_dsevents_files, scan_and_identify
    matches = scan_and_identify(find_dsevents_files(str(src)), str(dst))
    assert len(matches) == 0

    captured = capsys.readouterr()
    assert "Warning" in captured.out
    assert "No .dslog pair" in captured.out


def test_restart_detection(tmp_dirs):
    src, dst = tmp_dirs

    # Two files for the same match (robot restart)
    match_data_1 = make_dsevents_file([
        "FMS Connected:   Qualification - 60:1, Field Time: 26/3/29 14:00:0\n"
        " -- FRC Driver Station - Version 26.0",
    ], unix_timestamp=1000.0)
    match_data_2 = make_dsevents_file([
        "FMS Connected:   Qualification - 60:1, Field Time: 26/3/29 14:00:0\n"
        " -- FRC Driver Station - Version 26.0",
    ], unix_timestamp=2000.0)

    (src / "2026_03_29 09_34_29 Sun.dsevents").write_bytes(match_data_1)
    (src / "2026_03_29 09_34_29 Sun.dslog").write_bytes(b"\x00" * 100)
    (src / "2026_03_29 09_40_12 Sun.dsevents").write_bytes(match_data_2)
    (src / "2026_03_29 09_40_12 Sun.dslog").write_bytes(b"\x00" * 100)

    from process_matches import find_dsevents_files, scan_and_identify
    matches = scan_and_identify(find_dsevents_files(str(src)), str(dst))
    assert len(matches) == 1
    key = list(matches.keys())[0]
    assert len(matches[key]) == 2  # Two files grouped together


def test_nonstandard_filename_skipped_with_date_filter(tmp_dirs):
    src, dst = tmp_dirs

    match_data = make_dsevents_file([
        "FMS Connected:   Qualification - 10:1, Field Time: 26/3/29 10:00:0\n"
        " -- FRC Driver Station - Version 26.0",
    ])
    (src / "weird_name.dsevents").write_bytes(match_data)
    (src / "weird_name.dslog").write_bytes(b"\x00" * 100)

    from process_matches import find_dsevents_files, scan_and_identify
    matches = scan_and_identify(find_dsevents_files(str(src), date_filter="2026_03_29"), str(dst))
    assert len(matches) == 0


def test_non_participation_match_note(tmp_dirs):
    src, dst = tmp_dirs

    # FMS Connected but no Code Start Notification, no joysticks
    match_data = make_dsevents_file([
        "FMS Connected:   Elimination - 3:1, Field Time: 26/3/29 17:42:4\n"
        " -- FRC Driver Station - Version 26.0",
    ])
    (src / "2026_03_29 13_41_30 Sun.dsevents").write_bytes(match_data)
    (src / "2026_03_29 13_41_30 Sun.dslog").write_bytes(b"\x00" * 100)

    from process_matches import find_dsevents_files, scan_and_identify, process_match
    matches = scan_and_identify(find_dsevents_files(str(src)), str(dst))
    assert len(matches) == 1
    key = list(matches.keys())[0]
    files = matches[key]
    fms = files[0]["fms_info"]
    from match_identifier import build_match_id
    match_id = build_match_id(fms["match_type"], fms["match_number"], fms["replay"])

    process_match(key, files, match_id, "2026ncpem", str(src), str(dst))

    txt = (dst / f"{match_id}_match_events.txt").read_text()
    assert "NOTE: The robot does not appear to have participated in this match." in txt
    assert "The Blue Alliance: https://www.thebluealliance.com/match/2026ncpem_sf3m1" in txt


def test_participation_match_has_tba_link_no_note(tmp_dirs):
    src, dst = tmp_dirs

    match_data = make_dsevents_file([
        "Info Joystick 0: (Controller (Xbox One For Windows))6 axes, 16 buttons, 1 POVs. ",
        "FMS Connected:   Qualification - 13:1, Field Time: 26/3/28 17:29:45\n"
        " -- FRC Driver Station - Version 26.0",
        "Code Start Notification. ",
    ])
    (src / "2026_03_28 13_29_12 Sat.dsevents").write_bytes(match_data)
    (src / "2026_03_28 13_29_12 Sat.dslog").write_bytes(b"\x00" * 100)

    from process_matches import find_dsevents_files, scan_and_identify, process_match
    matches = scan_and_identify(find_dsevents_files(str(src)), str(dst))
    assert len(matches) == 1
    key = list(matches.keys())[0]
    files = matches[key]
    fms = files[0]["fms_info"]
    from match_identifier import build_match_id
    match_id = build_match_id(fms["match_type"], fms["match_number"], fms["replay"])

    process_match(key, files, match_id, "2026ncpem", str(src), str(dst))

    txt = (dst / f"{match_id}_match_events.txt").read_text()
    assert "The Blue Alliance: https://www.thebluealliance.com/match/2026ncpem_qm13" in txt
    assert "NOTE:" not in txt

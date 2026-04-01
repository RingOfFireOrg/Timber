"""Tests for robot profile CSV parsing."""

import os
from conftest import make_profile_csv


def test_parse_profile_basic(tmp_path):
    from profile_parser import parse_profile
    path = tmp_path / "robot.csv"
    make_profile_csv([
        (0, 10, "Front Left Drive NEO"),
        (5, 15, "Front Right Drive NEO"),
        (9, 20, "Climber NEO"),
    ], str(path))
    profile = parse_profile(str(path))
    assert profile[0] == {"can_id": 10, "description": "Front Left Drive NEO"}
    assert profile[5] == {"can_id": 15, "description": "Front Right Drive NEO"}
    assert profile[9] == {"can_id": 20, "description": "Climber NEO"}
    assert 1 not in profile


def test_parse_profile_duplicate_uses_last(tmp_path):
    from profile_parser import parse_profile
    path = tmp_path / "robot.csv"
    make_profile_csv([
        (0, 10, "First"),
        (0, 11, "Second"),
    ], str(path))
    profile = parse_profile(str(path))
    assert profile[0]["can_id"] == 11


def test_parse_profile_skips_bad_rows(tmp_path):
    from profile_parser import parse_profile
    path = tmp_path / "robot.csv"
    with open(str(path), "w") as f:
        f.write("channel,can_id,description\n")
        f.write("0,10,Good Row\n")
        f.write("bad,10,Non-numeric channel\n")
        f.write("1\n")
        f.write("5,15,Another Good Row\n")
    profile = parse_profile(str(path))
    assert 0 in profile
    assert 5 in profile
    assert len(profile) == 2

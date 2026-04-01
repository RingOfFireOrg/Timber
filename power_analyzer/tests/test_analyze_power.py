"""Integration tests for power analyzer CLI."""

import os
import struct
from conftest import (
    make_rev_pd_data,
    make_dslog_record_with_pd,
    make_profile_csv,
    make_dsevents_file,
    LABVIEW_EPOCH_OFFSET,
)
from conftest import make_dslog_header


def _make_test_dslog(records_data, unix_timestamp=1774752353.0):
    """Build a dslog file with explicit record bytes."""
    header = make_dslog_header(unix_timestamp)
    return header + b"".join(records_data)


def _make_test_files(tmp_path, dslog_bytes, dsevents_bytes=None):
    """Write test dslog and optional dsevents files, return paths."""
    basename = "2026_03_28 17_45_53 Sat"
    dslog_path = tmp_path / f"{basename}.dslog"
    dslog_path.write_bytes(dslog_bytes)

    dsevents_path = None
    if dsevents_bytes is not None:
        dsevents_path = tmp_path / f"{basename}.dsevents"
        dsevents_path.write_bytes(dsevents_bytes)

    return str(dslog_path), str(dsevents_path) if dsevents_path else None


def test_cli_produces_dip_report(tmp_path):
    from analyze_power import run_analysis

    pd_normal = make_rev_pd_data()
    pd_dip = make_rev_pd_data(channel_currents={0: 50.0, 14: 60.0})

    records = []
    for _ in range(20):
        records.append(make_dslog_record_with_pd(voltage_raw=3072, pd_data=pd_normal))
    for _ in range(10):
        records.append(make_dslog_record_with_pd(voltage_raw=2048, pd_data=pd_dip))
    for _ in range(20):
        records.append(make_dslog_record_with_pd(voltage_raw=3072, pd_data=pd_normal))

    dslog_data = _make_test_dslog(records)
    dslog_path, _ = _make_test_files(tmp_path, dslog_data)

    profile_path = tmp_path / "robot.csv"
    make_profile_csv([
        (0, 10, "Front Left Drive NEO"),
        (14, 25, "Shooter NEO"),
    ], str(profile_path))

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    run_analysis(
        log_file=dslog_path,
        profile_path=str(profile_path),
        voltage_threshold=10.0,
        current_threshold=1.0,
        output_dir=str(output_dir),
    )

    dip_file = output_dir / "2026_03_28 17_45_53 Sat_dips.txt"
    assert dip_file.exists()
    content = dip_file.read_text()
    assert "Dip 1" in content
    assert "Front Left Drive NEO" in content
    assert "Shooter NEO" in content


def test_cli_produces_event_log_when_dsevents_exists(tmp_path):
    from analyze_power import run_analysis

    pd_data = make_rev_pd_data()
    records = [make_dslog_record_with_pd(voltage_raw=3072, pd_data=pd_data) for _ in range(10)]
    dslog_data = _make_test_dslog(records)
    dsevents_data = make_dsevents_file(["Code Start Notification"])

    dslog_path, dsevents_path = _make_test_files(tmp_path, dslog_data, dsevents_data)

    profile_path = tmp_path / "robot.csv"
    make_profile_csv([], str(profile_path))

    run_analysis(
        log_file=dslog_path,
        profile_path=str(profile_path),
        voltage_threshold=10.0,
        current_threshold=1.0,
        output_dir=str(tmp_path),
    )

    event_file = tmp_path / "2026_03_28 17_45_53 Sat_events.txt"
    assert event_file.exists()
    content = event_file.read_text()
    assert "Event Log:" in content


def test_cli_no_event_log_without_dsevents(tmp_path):
    from analyze_power import run_analysis

    pd_data = make_rev_pd_data()
    records = [make_dslog_record_with_pd(voltage_raw=3072, pd_data=pd_data) for _ in range(10)]
    dslog_data = _make_test_dslog(records)
    dslog_path, _ = _make_test_files(tmp_path, dslog_data)

    profile_path = tmp_path / "robot.csv"
    make_profile_csv([], str(profile_path))

    run_analysis(
        log_file=dslog_path,
        profile_path=str(profile_path),
        voltage_threshold=10.0,
        current_threshold=1.0,
        output_dir=str(tmp_path),
    )

    event_file = tmp_path / "2026_03_28 17_45_53 Sat_events.txt"
    assert not event_file.exists()


def test_cli_no_dips_report(tmp_path):
    from analyze_power import run_analysis

    pd_data = make_rev_pd_data()
    records = [make_dslog_record_with_pd(voltage_raw=3072, pd_data=pd_data) for _ in range(50)]
    dslog_data = _make_test_dslog(records)
    dslog_path, _ = _make_test_files(tmp_path, dslog_data)

    profile_path = tmp_path / "robot.csv"
    make_profile_csv([], str(profile_path))

    run_analysis(
        log_file=dslog_path,
        profile_path=str(profile_path),
        voltage_threshold=10.0,
        current_threshold=1.0,
        output_dir=str(tmp_path),
    )

    dip_file = tmp_path / "2026_03_28 17_45_53 Sat_dips.txt"
    assert dip_file.exists()
    content = dip_file.read_text()
    assert "No voltage dips" in content

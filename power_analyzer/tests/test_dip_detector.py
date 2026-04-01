"""Tests for voltage dip detection with debounced recovery."""

from dip_detector import detect_dips

RECORD_INTERVAL = 0.020  # 20ms per record


def _make_record(index, voltage, mode="Teleop", pd_type=0x21, pd_data=None):
    """Build a minimal record dict for dip detection."""
    return {
        "index": index,
        "voltage": voltage,
        "mode": mode,
        "pd_type": pd_type,
        "pd_data": pd_data or b"\x00" * 33,
        "cpu": 0.5,
        "can": 0.5,
        "trip_ms": 5.0,
        "packet_loss": 0.0,
    }


def test_no_dips():
    records = [_make_record(i, 12.0) for i in range(100)]
    dips = detect_dips(records, voltage_threshold=10.0)
    assert dips == []


def test_single_dip_with_recovery():
    records = []
    for i in range(10):
        records.append(_make_record(i, 12.0))
    for i in range(10, 15):
        records.append(_make_record(i, 8.0))
    for i in range(15, 25):
        records.append(_make_record(i, 12.0))

    dips = detect_dips(records, voltage_threshold=10.0)
    assert len(dips) == 1
    assert dips[0]["start_index"] == 10
    assert abs(dips[0]["min_voltage"] - 8.0) < 0.01
    assert dips[0]["recovered"] is True
    assert abs(dips[0]["recovery_voltage"] - 12.0) < 0.01


def test_dip_no_recovery():
    records = []
    for i in range(10):
        records.append(_make_record(i, 12.0))
    for i in range(10, 20):
        records.append(_make_record(i, 8.0))

    dips = detect_dips(records, voltage_threshold=10.0)
    assert len(dips) == 1
    assert dips[0]["recovered"] is False


def test_debounced_recovery():
    """Brief voltage bounce above threshold should not end the dip."""
    records = []
    for i in range(5):
        records.append(_make_record(i, 12.0))
    for i in range(5, 15):
        records.append(_make_record(i, 8.0))
    # Brief bounce above (4 records = below debounce threshold of 5)
    for i in range(15, 19):
        records.append(_make_record(i, 11.0))
    # Back below
    for i in range(19, 25):
        records.append(_make_record(i, 8.0))
    # Real recovery (5+ records above)
    for i in range(25, 35):
        records.append(_make_record(i, 12.0))

    dips = detect_dips(records, voltage_threshold=10.0)
    assert len(dips) == 1


def test_multiple_dips():
    records = []
    for i in range(10):
        records.append(_make_record(i, 12.0))
    for i in range(10, 15):
        records.append(_make_record(i, 8.0))
    for i in range(15, 25):
        records.append(_make_record(i, 12.0))
    for i in range(25, 30):
        records.append(_make_record(i, 9.0))
    for i in range(30, 40):
        records.append(_make_record(i, 12.0))

    dips = detect_dips(records, voltage_threshold=10.0)
    assert len(dips) == 2
    assert abs(dips[0]["min_voltage"] - 8.0) < 0.01
    assert abs(dips[1]["min_voltage"] - 9.0) < 0.01


def test_implausible_voltage_filtered():
    """Records with voltage <= 1V or >= 16V should be skipped."""
    records = [_make_record(i, 0.5) for i in range(20)]
    dips = detect_dips(records, voltage_threshold=10.0)
    assert dips == []


def test_dip_tracks_peak_currents():
    """Peak per-channel currents should be tracked during a dip."""
    from conftest import make_rev_pd_data
    records = []
    for i in range(5):
        records.append(_make_record(i, 12.0))
    pd1 = make_rev_pd_data(channel_currents={0: 30.0, 5: 10.0})
    pd2 = make_rev_pd_data(channel_currents={0: 50.0, 5: 20.0})
    records.append(_make_record(5, 8.0, pd_data=pd1))
    records.append(_make_record(6, 7.5, pd_data=pd2))
    for i in range(7, 15):
        records.append(_make_record(i, 12.0))

    dips = detect_dips(records, voltage_threshold=10.0)
    assert len(dips) == 1
    assert abs(dips[0]["peak_currents"][0] - 50.0) < 0.5
    assert abs(dips[0]["peak_currents"][5] - 20.0) < 0.5

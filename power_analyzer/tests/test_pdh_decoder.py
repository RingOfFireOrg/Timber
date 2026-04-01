"""Tests for REV PDH and CTRE PDP current decoding."""

from conftest import make_rev_pd_data, make_ctre_pd_data


def test_decode_rev_single_channel():
    from pdh_decoder import decode_currents
    pd_data = make_rev_pd_data(channel_currents={0: 10.0})
    result = decode_currents(0x21, pd_data)
    assert abs(result[0] - 10.0) < 0.2
    assert result[1] == 0.0


def test_decode_rev_multiple_channels():
    from pdh_decoder import decode_currents
    pd_data = make_rev_pd_data(channel_currents={0: 50.0, 5: 25.0, 14: 60.0})
    result = decode_currents(0x21, pd_data)
    assert abs(result[0] - 50.0) < 0.2
    assert abs(result[5] - 25.0) < 0.2
    assert abs(result[14] - 60.0) < 0.2


def test_decode_rev_extra_channels():
    from pdh_decoder import decode_currents
    pd_data = make_rev_pd_data(extra_currents={20: 5.0, 23: 2.0})
    result = decode_currents(0x21, pd_data)
    assert abs(result[20] - 5.0) < 0.1
    assert abs(result[23] - 2.0) < 0.1


def test_decode_rev_all_zeros():
    from pdh_decoder import decode_currents
    pd_data = make_rev_pd_data()
    result = decode_currents(0x21, pd_data)
    assert len(result) == 24
    assert all(v == 0.0 for v in result.values())


def test_decode_ctre_single_channel():
    from pdh_decoder import decode_currents
    pd_data = make_ctre_pd_data(channel_currents={0: 10.0})
    result = decode_currents(0x19, pd_data)
    assert abs(result[0] - 10.0) < 0.2
    assert len(result) == 16


def test_decode_ctre_multiple_channels():
    from pdh_decoder import decode_currents
    pd_data = make_ctre_pd_data(channel_currents={0: 30.0, 8: 15.0, 15: 42.0})
    result = decode_currents(0x19, pd_data)
    assert abs(result[0] - 30.0) < 0.2
    assert abs(result[8] - 15.0) < 0.2
    assert abs(result[15] - 42.0) < 0.2


def test_decode_unknown_pd_type():
    from pdh_decoder import decode_currents
    result = decode_currents(0x00, b"")
    assert result is None


def test_decode_rev_truncated_data():
    from pdh_decoder import decode_currents
    result = decode_currents(0x21, b"\x00" * 10)
    assert result is None

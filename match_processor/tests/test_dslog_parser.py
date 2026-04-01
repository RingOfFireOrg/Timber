import struct

from conftest import make_dslog_header, LABVIEW_EPOCH_OFFSET


def test_parse_header_valid():
    from dslog_parser import parse_dslog_header
    data = make_dslog_header(unix_timestamp=1774752353.0)
    result = parse_dslog_header(data)
    assert result["version"] == 4
    assert abs(result["timestamp"] - 1774752353.0) < 1.0


def test_parse_header_version_check():
    from dslog_parser import parse_dslog_header
    data = make_dslog_header(version=99)
    result = parse_dslog_header(data)
    assert result is None


def test_parse_header_truncated():
    from dslog_parser import parse_dslog_header
    result = parse_dslog_header(b"\x00" * 10)
    assert result is None

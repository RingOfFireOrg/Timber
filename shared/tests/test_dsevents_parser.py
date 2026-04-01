import struct

from shared.tests.conftest import make_dsevents_header, make_dsevents_file, make_event_record, LABVIEW_EPOCH_OFFSET


def test_parse_header_version():
    from shared.dsevents_parser import parse_header
    data = make_dsevents_header(unix_timestamp=1000000.0, version=4)
    header = parse_header(data)
    assert header["version"] == 4


def test_parse_header_timestamp():
    from shared.dsevents_parser import parse_header
    data = make_dsevents_header(unix_timestamp=1000000.0, version=4)
    header = parse_header(data)
    assert abs(header["timestamp"] - 1000000.0) < 1.0


def test_parse_events_single_record():
    from shared.dsevents_parser import parse_dsevents_file
    file_bytes = make_dsevents_file(["Hello world"])
    result = parse_dsevents_file(file_bytes)
    assert len(result["events"]) == 1
    assert result["events"][0]["text"] == "Hello world"


def test_parse_events_multiple_records():
    from shared.dsevents_parser import parse_dsevents_file
    file_bytes = make_dsevents_file(["First", "Second", "Third"])
    result = parse_dsevents_file(file_bytes)
    assert len(result["events"]) == 3
    assert result["events"][0]["text"] == "First"
    assert result["events"][2]["text"] == "Third"


def test_parse_events_empty_file():
    from shared.dsevents_parser import parse_dsevents_file
    file_bytes = make_dsevents_header()  # header only, no events
    result = parse_dsevents_file(file_bytes)
    assert len(result["events"]) == 0


def test_parse_truncated_file():
    from shared.dsevents_parser import parse_dsevents_file
    file_bytes = make_dsevents_file(["Hello world"])
    # Truncate mid-record
    truncated = file_bytes[:30]
    result = parse_dsevents_file(truncated)
    assert len(result["events"]) == 0  # should not crash


def test_parse_header_too_short():
    from shared.dsevents_parser import parse_header
    import pytest
    with pytest.raises(ValueError):
        parse_header(b"\x00" * 10)


def test_parse_real_fms_event(sample_match_dsevents):
    from shared.dsevents_parser import parse_dsevents_file
    result = parse_dsevents_file(sample_match_dsevents)
    assert result["header"]["version"] == 4
    assert len(result["events"]) == 5
    texts = [e["text"] for e in result["events"]]
    assert any("FMS Connected" in t for t in texts)
    assert any("Warning <Code>" in t for t in texts)

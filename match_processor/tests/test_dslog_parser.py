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


from conftest import make_dslog_file


def test_parse_records_single_rev():
    from dslog_parser import parse_dslog_records
    # 12.0V, Disabled (status bit 0 = 0 → 0xFE), REV PDH
    data = make_dslog_file([{"voltage_raw": 3072, "status": 0xFE}])
    records = list(parse_dslog_records(data))
    assert len(records) == 1
    r = records[0]
    assert abs(r["voltage"] - 12.0) < 0.01
    assert r["mode"] == "Disabled"


def test_parse_records_autonomous():
    from dslog_parser import parse_dslog_records
    # Autonomous: bit 1 = 0 → 0xFD
    data = make_dslog_file([{"voltage_raw": 3200, "status": 0xFD}])
    records = list(parse_dslog_records(data))
    assert records[0]["mode"] == "Autonomous"


def test_parse_records_teleop():
    from dslog_parser import parse_dslog_records
    # Teleop: bit 2 = 0 → 0xFB
    data = make_dslog_file([{"voltage_raw": 3200, "status": 0xFB}])
    records = list(parse_dslog_records(data))
    assert records[0]["mode"] == "Teleop"


def test_parse_records_disconnected():
    from dslog_parser import parse_dslog_records
    # All bits set → Disconnected
    data = make_dslog_file([{"voltage_raw": 3200, "status": 0xFF}])
    records = list(parse_dslog_records(data))
    assert records[0]["mode"] == "Disconnected"


def test_parse_records_mode_priority():
    from dslog_parser import parse_dslog_records
    # Both Autonomous (bit 1=0) and Teleop (bit 2=0) clear → Autonomous wins
    data = make_dslog_file([{"voltage_raw": 3200, "status": 0xF9}])
    records = list(parse_dslog_records(data))
    assert records[0]["mode"] == "Autonomous"


def test_parse_records_ctre_pdp():
    from dslog_parser import parse_dslog_records
    data = make_dslog_file([{"voltage_raw": 3072, "status": 0xFE, "pd_type": 0x19}])
    records = list(parse_dslog_records(data))
    assert len(records) == 1


def test_parse_records_no_pd():
    from dslog_parser import parse_dslog_records
    data = make_dslog_file([{"voltage_raw": 3072, "status": 0xFE, "pd_type": 0x00}])
    records = list(parse_dslog_records(data))
    assert len(records) == 1


def test_parse_records_telemetry_fields():
    from dslog_parser import parse_dslog_records
    data = make_dslog_file([{
        "trip": 8,         # 8 × 0.5 = 4.0 ms
        "pkt_loss": 10,    # 10 × 4 × 0.01 = 0.40
        "voltage_raw": 3200,  # 3200 / 256 = 12.5 V
        "cpu": 100,        # 100 × 0.5 × 0.01 = 0.50
        "can": 74,         # 74 × 0.5 × 0.01 = 0.37
        "status": 0xFE,
    }])
    records = list(parse_dslog_records(data))
    r = records[0]
    assert abs(r["trip_ms"] - 4.0) < 0.01
    assert abs(r["packet_loss"] - 0.40) < 0.01
    assert abs(r["voltage"] - 12.5) < 0.01
    assert abs(r["cpu"] - 0.50) < 0.01
    assert abs(r["can"] - 0.37) < 0.01


def test_parse_records_truncated_mid_record():
    from dslog_parser import parse_dslog_records
    data = make_dslog_file([{"voltage_raw": 3072, "status": 0xFE}])
    # Truncate in the middle of the record
    truncated = data[:30]
    records = list(parse_dslog_records(truncated))
    assert len(records) == 0


def test_parse_records_unsupported_version():
    from dslog_parser import parse_dslog_records
    import struct
    data = struct.pack(">iqQ", 99, 0, 0)  # bad version
    records = list(parse_dslog_records(data))
    assert len(records) == 0


def test_parse_dslog_path(tmp_path):
    from dslog_parser import parse_dslog_path
    data = make_dslog_file([
        {"voltage_raw": 3072, "status": 0xFE},
        {"voltage_raw": 3200, "status": 0xFD},
    ])
    path = tmp_path / "test.dslog"
    path.write_bytes(data)
    result = parse_dslog_path(str(path))
    assert result["header"]["version"] == 4
    assert len(result["records"]) == 2
    assert result["records"][0]["mode"] == "Disabled"
    assert result["records"][1]["mode"] == "Autonomous"

"""Parse .dslog binary files: header and variable-length records."""

import struct

LABVIEW_EPOCH_OFFSET = -2082826800

HEADER_SIZE = 20
HEADER_FORMAT = ">iqQ"  # version (int32), timestamp_sec (int64), timestamp_frac (uint64)

# 10-byte fixed section per record
FIXED_SIZE = 10
FIXED_FORMAT = ">BbHBBBBH"  # trip, pkt_loss, voltage, cpu, status, can, wifi_sig, wifi_bw

PD_HEADER_SIZE = 4
PD_SIZES = {0x21: 33, 0x19: 25}  # REV PDH, CTRE PDP

EXPECTED_VERSION = 4


def labview_to_unix(seconds, fractional):
    """Convert LabVIEW timestamp to Unix timestamp."""
    return LABVIEW_EPOCH_OFFSET + seconds + fractional / (2**64)


def parse_dslog_header(data):
    """Parse the 20-byte dslog header.

    Returns dict with version, timestamp, timestamp_sec, timestamp_frac.
    Returns None if data is truncated or version is unsupported (with a warning printed).
    """
    if len(data) < HEADER_SIZE:
        print(f"  Warning: dslog file too short for header ({len(data)} bytes), skipping.")
        return None

    version, ts_sec, ts_frac = struct.unpack_from(HEADER_FORMAT, data, 0)

    if version != EXPECTED_VERSION:
        print(f"  Warning: dslog version {version} (expected {EXPECTED_VERSION}), skipping.")
        return None

    return {
        "version": version,
        "timestamp": labview_to_unix(ts_sec, ts_frac),
        "timestamp_sec": ts_sec,
        "timestamp_frac": ts_frac,
    }


def _decode_mode(status):
    """Determine robot mode from inverted status mask.

    Priority: Autonomous > Teleop > Disabled > Disconnected.
    Bits are inverted: 0 = active.
    """
    if not (status & 0x02):  # bit 1 — Robot Autonomous
        return "Autonomous"
    if not (status & 0x04):  # bit 2 — Robot Teleop
        return "Teleop"
    if not (status & 0x01):  # bit 0 — Robot Disabled
        return "Disabled"
    return "Disconnected"


def parse_dslog_records(data):
    """Parse dslog file and yield record dicts.

    Each record dict contains: index, voltage, cpu, can, trip_ms, packet_loss, mode.
    Yields nothing if header is invalid. Stops on truncated or unknown-PD records.
    """
    header = parse_dslog_header(data)
    if header is None:
        return

    offset = HEADER_SIZE
    index = 0

    while offset + FIXED_SIZE + PD_HEADER_SIZE <= len(data):
        trip, pkt_loss, voltage_raw, cpu, status, can, wifi_sig, wifi_bw = (
            struct.unpack_from(FIXED_FORMAT, data, offset)
        )

        pd_type = data[offset + FIXED_SIZE + 3]
        pd_extra = PD_SIZES.get(pd_type, None)

        # Unknown PD type: can't determine record size, stop
        if pd_extra is None and pd_type not in (0x00,):
            print(f"  Warning: unknown dslog PD type 0x{pd_type:02x} at record {index}, stopping.")
            return
        if pd_extra is None:
            pd_extra = 0

        record_size = FIXED_SIZE + PD_HEADER_SIZE + pd_extra
        if offset + record_size > len(data):
            break  # truncated final record

        # Extract raw PD data for downstream consumers (e.g., PDH current decoding)
        pd_data_offset = offset + FIXED_SIZE + PD_HEADER_SIZE
        pd_data_bytes = data[pd_data_offset : pd_data_offset + pd_extra]

        yield {
            "index": index,
            "voltage": voltage_raw / 256,
            "cpu": cpu * 0.5 * 0.01,
            "can": can * 0.5 * 0.01,
            "trip_ms": trip * 0.5,
            "packet_loss": max(0.0, min(1.0, pkt_loss * 4 * 0.01)),
            "mode": _decode_mode(status),
            "pd_type": pd_type,
            "pd_data": pd_data_bytes,
        }

        offset += record_size
        index += 1


def parse_dslog_path(filepath):
    """Parse a .dslog file from a file path.

    Returns dict with 'header' and 'records' keys.
    Returns dict with None header and empty records if file is invalid.
    """
    with open(filepath, "rb") as f:
        data = f.read()

    header = parse_dslog_header(data)
    records = list(parse_dslog_records(data))

    return {"header": header, "records": records}

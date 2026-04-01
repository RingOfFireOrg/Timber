"""Test fixtures for power analyzer tests."""

import struct
import os
import tempfile

from shared.tests.conftest import (
    make_dslog_header,
    make_dslog_file,
    make_dsevents_file,
    LABVIEW_EPOCH_OFFSET,
    PD_SIZES,
)


def make_rev_pd_data(channel_currents=None, extra_currents=None):
    """Build a 33-byte REV PDH data section with specified channel currents.

    Args:
        channel_currents: dict mapping channel (0-19) to current in amps.
            Each value is multiplied by 8 to get the 10-bit raw value.
        extra_currents: dict mapping channel (20-23) to current in amps.
            Each value is multiplied by 16 to get the raw byte value.

    Returns:
        33 bytes: 1 CAN ID + 27 boolean array + 4 extra channels + 1 temp.
    """
    if channel_currents is None:
        channel_currents = {}
    if extra_currents is None:
        extra_currents = {}

    can_id = 1
    bits = [0] * 216
    for ch, amps in channel_currents.items():
        if ch < 0 or ch > 19:
            continue
        raw = int(amps * 8)
        read_pos = (ch // 3) * 32 + (ch % 3) * 10
        for bit_i in range(10):
            if raw & (1 << bit_i):
                bits[read_pos + bit_i] = 1

    bool_bytes = bytearray(27)
    for i, bit in enumerate(bits):
        if bit:
            bool_bytes[i // 8] |= (1 << (i % 8))

    extra_bytes = bytearray(4)
    for ch, amps in extra_currents.items():
        idx = ch - 20
        if 0 <= idx <= 3:
            extra_bytes[idx] = min(255, int(amps * 16))

    temp = 0
    return bytes([can_id]) + bytes(bool_bytes) + bytes(extra_bytes) + bytes([temp])


def make_ctre_pd_data(channel_currents=None):
    """Build a 25-byte CTRE PDP data section with specified channel currents.

    Args:
        channel_currents: dict mapping channel (0-15) to current in amps.
            Each value is multiplied by 8 to get the 10-bit raw value.

    Returns:
        25 bytes: 1 CAN ID + 21 boolean array + 3 metadata.
    """
    if channel_currents is None:
        channel_currents = {}

    can_id = 1
    bits = [0] * 168
    for ch, amps in channel_currents.items():
        if ch < 0 or ch > 15:
            continue
        raw = int(amps * 8)
        read_pos = (ch // 6) * 64 + (ch % 6) * 10
        for bit_i in range(10):
            if raw & (1 << bit_i):
                bits[read_pos + bit_i] = 1

    bool_bytes = bytearray(21)
    for i, bit in enumerate(bits):
        if bit:
            bool_bytes[i // 8] |= (1 << (i % 8))

    metadata = b"\x00" * 3
    return bytes([can_id]) + bytes(bool_bytes) + metadata


def make_dslog_record_with_pd(status=0xFE, voltage_raw=3072, trip=0,
                               pkt_loss=0, cpu=0, can=0, pd_type=0x21,
                               pd_data=None):
    """Build a single dslog record with explicit PD data bytes."""
    fixed = struct.pack(">BbHBBBBH", trip, pkt_loss, voltage_raw, cpu, status, can, 0, 0)
    pd_header = struct.pack("4B", 0, 0, 0, pd_type)
    if pd_data is None:
        pd_extra_size = PD_SIZES.get(pd_type, 0)
        pd_data = b"\x00" * pd_extra_size
    return fixed + pd_header + pd_data


def make_profile_csv(channel_map, path):
    """Write a robot profile CSV file."""
    with open(path, "w") as f:
        f.write("channel,can_id,description\n")
        for ch, can_id, desc in channel_map:
            f.write(f"{ch},{can_id},{desc}\n")

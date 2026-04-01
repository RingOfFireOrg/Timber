"""Decode per-channel currents from REV PDH and CTRE PDP data sections."""

# PD type constants
PD_TYPE_REV = 0x21
PD_TYPE_CTRE = 0x19

# Expected PD data sizes (including CAN ID byte)
REV_PD_DATA_SIZE = 33
CTRE_PD_DATA_SIZE = 25

# REV PDH: 20 main channels (10-bit packed) + 4 extra channels (1 byte each)
REV_MAIN_CHANNELS = 20
REV_EXTRA_CHANNELS = 4
REV_TOTAL_CHANNELS = REV_MAIN_CHANNELS + REV_EXTRA_CHANNELS
REV_BOOL_ARRAY_OFFSET = 1    # skip CAN ID byte
REV_BOOL_ARRAY_SIZE = 27     # 216 bits for 20 x 10-bit channels + padding
REV_EXTRA_OFFSET = 28        # bytes 28-31: extra channel currents
REV_BITS_PER_CHANNEL = 10
REV_CURRENT_DIVISOR = 8.0    # raw 10-bit value / 8 = amps
REV_EXTRA_DIVISOR = 16.0     # raw byte / 16 = amps

# CTRE PDP: 16 channels (10-bit packed)
CTRE_CHANNELS = 16
CTRE_BOOL_ARRAY_OFFSET = 1   # skip CAN ID byte
CTRE_BOOL_ARRAY_SIZE = 21    # 168 bits for 16 x 10-bit channels + padding
CTRE_BITS_PER_CHANNEL = 10
CTRE_CURRENT_DIVISOR = 8.0


def _read_bits_lsb(data_bytes, start_bit, count):
    """Read `count` bits starting at `start_bit`, assembled LSB-first."""
    value = 0
    for i in range(count):
        bit_index = start_bit + i
        byte_index = bit_index // 8
        bit_offset = bit_index % 8
        if byte_index < len(data_bytes):
            if data_bytes[byte_index] & (1 << bit_offset):
                value |= (1 << i)
    return value


def _decode_rev(pd_data):
    """Decode REV PDH channel currents from 33-byte PD data section."""
    bool_array = pd_data[REV_BOOL_ARRAY_OFFSET : REV_BOOL_ARRAY_OFFSET + REV_BOOL_ARRAY_SIZE]
    currents = {}

    for ch in range(REV_MAIN_CHANNELS):
        read_pos = (ch // 3) * 32 + (ch % 3) * REV_BITS_PER_CHANNEL
        raw = _read_bits_lsb(bool_array, read_pos, REV_BITS_PER_CHANNEL)
        currents[ch] = raw / REV_CURRENT_DIVISOR

    for i in range(REV_EXTRA_CHANNELS):
        ch = REV_MAIN_CHANNELS + i
        raw = pd_data[REV_EXTRA_OFFSET + i]
        currents[ch] = raw / REV_EXTRA_DIVISOR

    return currents


def _decode_ctre(pd_data):
    """Decode CTRE PDP channel currents from 25-byte PD data section."""
    bool_array = pd_data[CTRE_BOOL_ARRAY_OFFSET : CTRE_BOOL_ARRAY_OFFSET + CTRE_BOOL_ARRAY_SIZE]
    currents = {}

    for ch in range(CTRE_CHANNELS):
        read_pos = (ch // 6) * 64 + (ch % 6) * CTRE_BITS_PER_CHANNEL
        raw = _read_bits_lsb(bool_array, read_pos, CTRE_BITS_PER_CHANNEL)
        currents[ch] = raw / CTRE_CURRENT_DIVISOR

    return currents


def decode_currents(pd_type, pd_data):
    """Decode per-channel currents from PD data.

    Returns dict mapping channel number -> current in amps, or None if
    pd_type is unknown or pd_data is too short.
    """
    if pd_type == PD_TYPE_REV:
        if len(pd_data) < REV_PD_DATA_SIZE:
            return None
        return _decode_rev(pd_data)
    elif pd_type == PD_TYPE_CTRE:
        if len(pd_data) < CTRE_PD_DATA_SIZE:
            return None
        return _decode_ctre(pd_data)
    return None

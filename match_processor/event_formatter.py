"""Filter, format, and collapse .dsevents event records for display."""

import re

# Pattern to split multiple <TagVersion> entries in one text payload
TAG_SPLIT_PATTERN = re.compile(r"(?=<TagVersion>)")

# Parse a tagged message event
TAG_MESSAGE_PATTERN = re.compile(
    r"<TagVersion>\d+\s+<time>\s*([-\d.]+)\s+<message>\s*(.*)"
)

# Parse a tagged coded event
TAG_CODED_PATTERN = re.compile(
    r"<TagVersion>\d+\s+<time>\s*([-\d.]+)\s+"
    r"<count>\s*(\d+)\s+<flags>\s*(\d+)\s+<Code>\s*(\d+)\s+"
    r"<details>\s*(.*?)\s*<location>\s*(.*?)\s*<stack>\s*(.*)"
)

# Parse a Warning record (distinct from TagVersion events)
WARNING_RECORD_PATTERN = re.compile(
    r"Warning <Code> (\d+) <secondsSinceReboot> ([\d.]+)(?:\r)?<Description>(.+?)(?=<TagVersion>|$)"
)

# Patterns for events to exclude
EXCLUDE_PATTERNS = [
    re.compile(r"disabledPeriodic\(\):"),
    re.compile(r"robotPeriodic\(\):"),
    re.compile(r"Shuffleboard\.update\(\):"),
    re.compile(r"LiveWindow\.updateValues\(\):"),
    re.compile(r"SmartDashboard\.updateValues\(\):"),
    re.compile(r"autonomousPeriodic\(\):"),
    re.compile(r"teleopPeriodic\(\):"),
]

# Plain text events we want to include
PLAIN_EVENTS = {
    "FMS Connected": re.compile(r"^FMS Connected:"),
    "FMS Disconnected": re.compile(r"^FMS Disconnected"),
    "Code Start Notification": re.compile(r"^Code Start Notification"),
}


def should_exclude(display_text):
    """Return True if the event display text matches an exclude pattern."""
    for pattern in EXCLUDE_PATTERNS:
        if pattern.search(display_text):
            return True
    return False


def should_include_tagged(flags, code, details, message):
    """Return True if a tagged event should be included in output."""
    # Warnings (flags=1) and errors (flags=2)
    if flags >= 1:
        return True
    # Non-zero code
    if code != 0:
        return True
    # Phoenix Signal Logger
    if details and details.strip().startswith("[phoenix] Signal Logger"):
        return True
    # PhotonVision
    text = (details or "") + (message or "")
    if "PhotonVision" in text or "org.photonvision" in text:
        return True
    # Robot mode transitions
    if message and ("Robot is now" in message):
        return True
    # Warning/Error messages from WPILib (e.g., "Warning at ...", "Error at ...")
    if message and (message.startswith("Warning at") or message.startswith("Error at")):
        return True
    return False


def format_plain_event(text, relative_time="00.000"):
    """Try to format a plain text event. Returns dict or None if not a known plain event."""
    for display_name, pattern in PLAIN_EVENTS.items():
        if pattern.search(text):
            return {"time": relative_time, "display": display_name}
    return None


def parse_warning_event(text, relative_time="00.000"):
    """Try to parse a Warning record. Returns dict or None if not a Warning record.

    Warning records have the format:
        Warning <Code> NNNNN <secondsSinceReboot> SSS.SSS\r<Description>Message text.
    """
    m = WARNING_RECORD_PATTERN.match(text)
    if not m:
        return None
    code = int(m.group(1))
    description = m.group(3).strip().rstrip(".")
    return {"time": relative_time, "display": f"WARNING ({code}): {description}", "code": code}


def parse_tagged_events(text, relative_time="00.000"):
    """Parse tagged events from a text payload.

    A single payload may contain multiple <TagVersion> entries.
    Returns a list of formatted event dicts using the record-level timestamp.
    """
    parts = TAG_SPLIT_PATTERN.split(text)
    results = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Try coded event first (more specific)
        m = TAG_CODED_PATTERN.match(part)
        if m:
            flags = int(m.group(3))
            code = int(m.group(4))
            details = m.group(5).strip()
            location = m.group(6).strip()

            if not should_include_tagged(flags, code, details, None):
                continue
            if should_exclude(details):
                continue

            if flags == 2:
                prefix = "ERROR"
            elif flags == 1:
                prefix = "WARNING"
            else:
                prefix = "INFO"

            if code != 0:
                display = f"{prefix} ({code}): {details}"
            else:
                display = details

            results.append({"time": relative_time, "display": display, "flags": flags, "code": code})
            continue

        # Try message event
        m = TAG_MESSAGE_PATTERN.match(part)
        if m:
            message = m.group(2).strip()

            if not should_include_tagged(0, 0, None, message):
                continue
            if should_exclude(message):
                continue

            results.append({"time": relative_time, "display": message})

    return results


def format_events(parsed_data):
    """Process all events from a parsed .dsevents file into display-ready list.

    Returns list of dicts with 'time' and 'display' keys.
    """
    formatted = []
    header_ts = parsed_data["header"]["timestamp"]

    for event in parsed_data["events"]:
        text = event["text"]

        # Compute relative time from file start
        rel_seconds = event["timestamp"] - header_ts
        rel_time = f"{abs(rel_seconds):07.3f}"
        if rel_seconds < 0:
            rel_time = f"-{rel_time}"

        # Try plain text events
        plain = format_plain_event(text, rel_time)
        if plain is not None:
            formatted.append(plain)
            continue

        # Try Warning records (may coexist with TagVersion entries in same payload)
        warning = parse_warning_event(text, rel_time)
        if warning is not None:
            formatted.append(warning)

        # Try tagged events
        if "<TagVersion>" in text:
            tagged = parse_tagged_events(text, rel_time)
            formatted.extend(tagged)
            continue

        if warning is not None:
            continue

    return formatted


def collapse_repeats(events):
    """Collapse consecutive identical display messages.

    If N consecutive events have the same display text (N >= 2):
    - Show the 1st normally
    - Suppress 2nd through (N-1)th
    - Show the Nth with '(repeated {N-1}x)' appended
    """
    if not events:
        return []

    result = []
    i = 0

    while i < len(events):
        # Find end of consecutive run
        j = i + 1
        while j < len(events) and events[j]["display"] == events[i]["display"]:
            j += 1

        count = j - i

        if count == 1:
            result.append(events[i])
        else:
            # First occurrence
            result.append(events[i])
            # Last occurrence with repeat count
            last = dict(events[j - 1])  # copy
            last["display"] = f"{last['display']} (repeated {count - 1}x)"
            result.append(last)

        i = j

    return result

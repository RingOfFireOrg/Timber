def test_parse_tagged_event_message_included():
    from event_formatter import parse_tagged_events
    text = "<TagVersion>1 <time> 00.169 <message> Warning at org.photonvision.PhotonCamera: PhotonVision coprocessor error "
    events = parse_tagged_events(text)
    assert len(events) == 1
    assert events[0]["time"] == "00.169"
    assert "PhotonVision" in events[0]["display"]


def test_parse_tagged_event_message_excluded():
    from event_formatter import parse_tagged_events
    text = "<TagVersion>1 <time> 00.169 <message> CS: USB Camera 0: Attempting to connect to USB camera on /dev/video0 "
    events = parse_tagged_events(text)
    assert len(events) == 0  # USB camera messages are filtered out


def test_parse_tagged_event_coded():
    from event_formatter import parse_tagged_events
    text = ("<TagVersion>1 <time> 00.000 <count> 1 <flags> 2 <Code> 44000 "
            "<details> Driver Station not keeping up with protocol rates "
            "<location> Driver Station <stack> ")
    events = parse_tagged_events(text)
    assert len(events) == 1
    assert events[0]["flags"] == 2
    assert events[0]["code"] == 44000
    assert "ERROR (44000)" in events[0]["display"]


def test_parse_tagged_event_multiple_in_one_record():
    from event_formatter import parse_tagged_events
    text = ("<TagVersion>1 <time> 00.100 <message> Robot is now in Autonomous "
            "<TagVersion>1 <time> 00.200 <message> Robot is now in Teleop ")
    events = parse_tagged_events(text)
    assert len(events) == 2
    assert "Robot is now in Autonomous" in events[0]["display"]
    assert "Robot is now in Teleop" in events[1]["display"]


def test_format_plain_event_fms_connected():
    from event_formatter import format_plain_event
    text = "FMS Connected:   Qualification - 52:1, Field Time: 26/3/29 13:35:4\n -- FRC Driver Station - Version 26.0"
    result = format_plain_event(text)
    assert result is not None
    assert result["display"] == "FMS Connected"


def test_format_plain_event_code_start():
    from event_formatter import format_plain_event
    text = "Code Start Notification. "
    result = format_plain_event(text)
    assert result is not None
    assert result["display"] == "Code Start Notification"


def test_should_exclude_periodic_trace():
    from event_formatter import should_exclude
    assert should_exclude("disabledPeriodic(): 0.000075s") is True
    assert should_exclude("robotPeriodic(): 0.017270s") is True
    assert should_exclude("Shuffleboard.update(): 0.006733s") is True
    assert should_exclude("LiveWindow.updateValues(): 0.000000s") is True
    assert should_exclude("SmartDashboard.updateValues(): 0.000816s") is True


def test_should_not_exclude_real_events():
    from event_formatter import should_exclude
    assert should_exclude("FMS Connected") is False
    assert should_exclude("WARNING (44000): Driver Station not keeping up") is False


def test_parse_warning_event():
    from event_formatter import parse_warning_event
    text = "Warning <Code> 44007 <secondsSinceReboot> 116.460\r<Description>FRC: Time since robot boot."
    result = parse_warning_event(text, "116.460")
    assert result is not None
    assert result["code"] == 44007
    assert "WARNING (44007)" in result["display"]
    assert "FRC: Time since robot boot" in result["display"]


def test_parse_warning_event_not_warning():
    from event_formatter import parse_warning_event
    text = "FMS Connected:   Qualification - 52:1, Field Time: 26/3/29 13:35:4"
    result = parse_warning_event(text)
    assert result is None


def test_collapse_repeats_no_repeats():
    from event_formatter import collapse_repeats
    events = [
        {"time": "00.000", "display": "Event A"},
        {"time": "01.000", "display": "Event B"},
    ]
    result = collapse_repeats(events)
    assert len(result) == 2


def test_collapse_repeats_two_consecutive():
    from event_formatter import collapse_repeats
    events = [
        {"time": "00.000", "display": "Same event"},
        {"time": "01.000", "display": "Same event"},
    ]
    result = collapse_repeats(events)
    assert len(result) == 2
    assert "(repeated 1x)" not in result[0]["display"]
    assert "(repeated 1x)" in result[1]["display"]


def test_collapse_repeats_six_consecutive():
    from event_formatter import collapse_repeats
    events = [{"time": f"0{i}.000", "display": "Repeated msg"} for i in range(6)]
    result = collapse_repeats(events)
    assert len(result) == 2  # first + last
    assert "(repeated 5x)" in result[1]["display"]


def test_collapse_repeats_mixed():
    from event_formatter import collapse_repeats
    events = [
        {"time": "00.000", "display": "A"},
        {"time": "01.000", "display": "B"},
        {"time": "02.000", "display": "B"},
        {"time": "03.000", "display": "B"},
        {"time": "04.000", "display": "C"},
    ]
    result = collapse_repeats(events)
    assert len(result) == 4  # A, B (first), B (repeated 2x), C
    assert result[0]["display"] == "A"
    assert "(repeated" not in result[1]["display"]
    assert "(repeated 2x)" in result[2]["display"]
    assert result[3]["display"] == "C"

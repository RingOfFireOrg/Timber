"""Parse robot profile CSV mapping PDH channels to motor descriptions."""

import csv


def parse_profile(filepath):
    """Parse a robot profile CSV file.

    Expected columns: channel, can_id, description.
    Rows with non-numeric channel or missing columns are skipped with a warning.
    Duplicate channel entries use the last one.

    Returns:
        dict mapping channel number (int) -> {"can_id": int, "description": str}
    """
    profile = {}
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                channel = int(row["channel"])
                can_id = int(row["can_id"])
                description = row["description"].strip()
            except (KeyError, ValueError, TypeError):
                print(f"  Warning: skipping invalid profile row: {row}")
                continue
            profile[channel] = {"can_id": can_id, "description": description}
    return profile

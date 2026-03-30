# Code Review: FRC Match Log Processor (Implementation Plan)

**Date:** 2026-03-30
**Reviewed:** `docs/superpowers/plans/2026-03-30-match-log-processor.md`
**Validated against:** Real `.dsevents` file at `2026/UNCPembroke/2026_03_29 09_34_29 Sun.dsevents` (520 records, version 4)

---

## 1. Correctness (binary parsing)

### HIGH: Test fixtures have fake prefixes that don't match real data

The `sample_match_dsevents` fixture in `conftest.py` prefixes records with characters that don't exist in real files:

```python
"\x00#Info 26.0Info FMS Event Name: NCPEM",       # real data: "Info 26.0Info FMS Event Name: NCPEM"
"nInfo Joystick 0: (Controller (Xbox One ...))...",  # real data: "Info Joystick 0: ..."
"hFMS Connected:   Qualification - 52:1, ...",       # real data: "FMS Connected:   Qualification - 52:1, ..."
```

The `dsevents_parser.py` has a `lstrip` of control characters `\x00`-`\x1f` to compensate, but:

- `\x00#` — the `\x00` is stripped, but `#` remains, so `Info FMS Event Name:` regex won't match `#Info 26.0Info FMS Event Name: NCPEM`
- `n` and `h` are printable ASCII (not control characters) — they are **not** stripped by `lstrip`, so `FMS Connected:` regex won't match `hFMS Connected:...` and `Info Joystick` regex won't match `nInfo Joystick...`

Real files have **no leading junk bytes** on records. All records start directly with their content (`Info`, `FMS Connected:`, `<TagVersion>`, `Warning`, etc.).

**Fix:** Remove all leading prefixes from fixture strings. Use exactly what real files contain. If there are real files with leading control bytes, find one and base a separate test on it.

### HIGH: `Warning` record format is completely unhandled

Real data contains a distinct warning format:

```
Warning <Code> 44007 <secondsSinceReboot> 116.460\r<Description>FRC: Time since robot boot.
```

This is **not** a `<TagVersion>` event and **not** a plain text event. The `event_formatter.py` has no code path to parse it. The tags are `<Code>`, `<secondsSinceReboot>`, `<Description>` — completely different from the `<TagVersion>` structure (`<time>`, `<count>`, `<flags>`, `<Code>`, `<details>`, `<location>`, `<stack>`).

The spec's include list says to include warnings (flags=1) and errors (flags=2), but this record has no `<flags>` field at all. Real warnings like "FRC: Time since robot boot" will be **silently dropped** from `match_events.txt`.

**Fix:** Add a parser for `Warning <Code> ... <Description> ...` records in `event_formatter.py`, or acknowledge this as a known gap.

### Verified correct

- **Header format** `>iqQ` (int32 version, int64 seconds, uint64 fractional) — confirmed against real file. Value `3857636069` converts to `2026-03-29 18:34:29 UTC`, matching filename `09_34_29` in EDT (UTC-4).
- **Record header format** `>qQi` (int64 seconds, uint64 fractional, int32 text_length) — confirmed at 20 bytes per record header.
- **`labview_to_unix`** — `LABVIEW_EPOCH_OFFSET + seconds + fractional / 2^64` matches spec.
- **`collapse_repeats`** — boundary handling for N=1, N=2, and N>2 all produce correct output per spec.
- **`match_identifier.py`** — FMS regex, match ID construction, grouping logic all look correct.
- **`match_writer.py`** — file naming, section formatting match the spec.

---

## 2. Error handling & robustness

**Truncated file handling is good.** The `while offset + RECORD_HEADER_SIZE <= len(data)` guard and `offset + text_len > len(data)` check both break cleanly.

**`text_len < 0` check is correct** — since it's a signed int32, a corrupt value could be negative.

**`lstrip` control-character stripping solves a problem that doesn't exist.** Real data has clean record starts. The double-stripping (`lstrip` then `while ord < 32`) is redundant and could theoretically eat legitimate leading bytes. Low risk, but unnecessary complexity.

**`scan_and_identify` calls `find_dsevents_files` twice** in the CLI path — once in `main()` to check for the "No .dsevents files found" message, and once inside `scan_and_identify`. Wasteful but not incorrect.

---

## 3. Readability & maintainability

**Good function decomposition.** The separation across `dsevents_parser`, `match_identifier`, `event_formatter`, and `match_writer` is clean and each module has a clear responsibility.

**`event_formatter.py` is well-structured.** `should_exclude`, `should_include_tagged`, `parse_tagged_events`, `format_events`, and `collapse_repeats` are all well-scoped.

**`process_matches.py` `main()` flow is clear:** validate -> scan -> display -> confirm -> process.

**`should_include_tagged` uses `flags >= 1`** which includes any future flag value beyond 2. Probably fine, but worth a brief comment explaining the intent.

**Time formatting misaligns past 99 seconds:**
```python
rel_time = f"{abs(rel_seconds):06.3f}"
```
This produces 6-char output for times < 100s (`05.123`) but 7+ chars at 100s+ (`125.400`). Matches run ~150s so the Events column will misalign in the second half. Minor cosmetic issue.

---

## 4. Quick wins

- **`struct.Struct` objects** for repeated unpacking in the record loop:
  ```python
  RECORD_HEADER = struct.Struct(">qQi")
  # then: ts_sec, ts_frac, text_len = RECORD_HEADER.unpack_from(data, offset)
  ```

- **`namedtuple` or dataclass** for parsed records instead of plain dicts — prevents typo-based key errors and gives attribute access. Not critical at this scale.

- **Deduplicate `find_dsevents_files` call** — pass the file list into `scan_and_identify` rather than re-scanning.

---

## Summary

| Priority | Issue | Location |
|----------|-------|----------|
| **High** | Test fixtures have fake prefixes (`\x00#`, `n`, `h`) that don't match real data — will cause regex mismatches or false confidence | `conftest.py` |
| **High** | `Warning <Code> ... <Description> ...` record format unhandled — real warnings silently dropped | `event_formatter.py` |
| Low | `lstrip` control-character stripping solves a non-existent problem | `dsevents_parser.py` |
| Low | `find_dsevents_files` called twice in CLI path | `process_matches.py` |
| Low | Time formatting misaligns past 99 seconds | `event_formatter.py` |

The binary parser core is solid. Match identifier and match writer logic are correct. The main risks are the test fixtures misleading development and the unhandled `Warning` record format.

"""Strict readers for datasets stored as consecutive JSON records.

Several public datasets call their files ``*.jsonl`` even when a JSON object
may legally span multiple physical lines.  Splitting on ``str.splitlines()``
therefore conflates the transport format with the JSON grammar.  This module
uses :meth:`json.JSONDecoder.raw_decode` to read consecutive JSON values and,
just as importantly, makes a trailing partial record an explicit error.

It deliberately does *not* repair malformed JSON or return a silent prefix to
training code.  ``inspect_json_records`` exists for forensic/audit tooling
only; production consumers should use ``load_json_records``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence


class JsonRecordError(ValueError):
    """An invalid or incomplete JSON record sequence with precise location."""

    def __init__(self, path: Path, record_number: int,
                 error: json.JSONDecodeError):
        self.path = path
        self.record_number = int(record_number)
        self.line = int(error.lineno)
        self.column = int(error.colno)
        self.offset = int(error.pos)
        self.message = str(error.msg)
        super().__init__(
            f"{path}: record {record_number} is not valid complete JSON "
            f"({error.msg}, line {error.lineno}, column {error.colno})")

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "record_number": self.record_number,
            "message": self.message,
            "line": self.line,
            "column": self.column,
            "offset": self.offset,
        }


@dataclass(frozen=True)
class JsonRecordInspection:
    """Complete prefix plus an optional parse failure for read-only audits."""

    records: Sequence[Mapping[str, Any]]
    error: JsonRecordError | None

    @property
    def complete(self) -> bool:
        return self.error is None


def _decode_prefix(path: str | Path) -> Iterator[tuple[Mapping[str, Any] | None,
                                                       JsonRecordError | None]]:
    """Yield parsed objects and at most one terminal error.

    JSON whitespace is permitted between records, so this accepts ordinary
    JSONL as well as valid multiline JSON records.  A record must be an object;
    arrays/scalars are programming errors for all current dataset consumers.
    """
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    decoder = json.JSONDecoder()
    cursor, ordinal, size = 0, 0, len(text)
    while True:
        while cursor < size and text[cursor].isspace():
            cursor += 1
        if cursor >= size:
            return
        try:
            value, cursor = decoder.raw_decode(text, cursor)
        except json.JSONDecodeError as exc:
            yield None, JsonRecordError(source, ordinal + 1, exc)
            return
        ordinal += 1
        if not isinstance(value, Mapping):
            raise ValueError(f"{source}: record {ordinal} must be a JSON object")
        yield value, None


def inspect_json_records(path: str | Path) -> JsonRecordInspection:
    """Read the complete prefix for an audit and expose a terminal error.

    This is intentionally unsuitable for model training: callers must inspect
    ``complete`` explicitly before they use ``records``.
    """
    rows: list[Mapping[str, Any]] = []
    terminal: JsonRecordError | None = None
    for row, error in _decode_prefix(path):
        if error is not None:
            terminal = error
            break
        if row is not None:
            rows.append(row)
    return JsonRecordInspection(records=tuple(rows), error=terminal)


def iter_json_records(path: str | Path) -> Iterator[Mapping[str, Any]]:
    """Yield every record, raising if even one trailing record is incomplete."""
    for row, error in _decode_prefix(path):
        if error is not None:
            raise error
        if row is not None:
            yield row


def load_json_records(path: str | Path) -> list[Mapping[str, Any]]:
    """Materialize a complete JSON-record file; partial datasets are rejected."""
    return list(iter_json_records(path))

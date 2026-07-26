"""FIT file decoding adapter for Garmin health parsing.

This module owns the direct dependency on ``garmin_fit_sdk``.  Higher parser
layers receive decoded message dictionaries so extractor and day-composition
policy can be tested without opening real FIT files.
"""

from pathlib import Path

from garmin_fit_sdk import Decoder, Stream


def decode_fit_file(file_path: Path) -> dict[str, list[dict]]:
    """Decode a FIT file and return messages as dictionaries grouped by type.

    Raises ``ValueError`` when the SDK reports a decode error. ``Decoder.read``
    never raises: it swallows the failure and hands back whatever it managed to
    read before giving up, so a truncated or corrupt file otherwise looks like a
    thin but valid one. Callers get all-or-nothing instead, and decide for
    themselves whether to skip the file or fail.
    """
    stream = Stream.from_file(str(file_path))
    decoder = Decoder(stream)
    messages, errors = decoder.read()
    if errors:
        raise ValueError(f"FIT decode errors in {file_path.name}: {errors}")
    return messages

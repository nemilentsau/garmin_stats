"""FIT file decoding adapter for Garmin health parsing.

This module owns the direct dependency on ``garmin_fit_sdk``.  Higher parser
layers receive decoded message dictionaries so extractor and day-composition
policy can be tested without opening real FIT files.
"""

from pathlib import Path

from garmin_fit_sdk import Decoder, Stream


def decode_fit_file(file_path: Path) -> dict[str, list[dict]]:
    """Decode a FIT file and return messages as dictionaries grouped by type."""
    stream = Stream.from_file(str(file_path))
    decoder = Decoder(stream)
    messages, errors = decoder.read()
    return messages

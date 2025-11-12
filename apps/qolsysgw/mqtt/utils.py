"""MQTT utility functions for name normalization."""

import logging
import re
import unicodedata


LOGGER = logging.getLogger(__name__)


def rm_diacritics(char: str) -> str:
    """Return the base character of char by removing diacritics.

    Remove any diacritics like accents or curls and strokes and the like.

    Args:
        char: Character to process

    Returns:
        Base character without diacritics

    Note:
        Taken from https://stackoverflow.com/a/15547803
    """
    desc = unicodedata.name(char)
    cutoff = desc.find(' WITH ')
    if cutoff != -1:
        desc = desc[:cutoff]
        try:
            char = unicodedata.lookup(desc)
        except KeyError:
            pass  # removing "WITH ..." produced an invalid name
    return char


def normalize_name_to_id(name: str) -> str:
    """Normalize a name to a valid ID string.

    Converts name to lowercase ASCII-only string with underscores replacing
    special characters.

    Args:
        name: Name to normalize

    Returns:
        Normalized ID string (lowercase, alphanumeric with underscores)
    """
    ascii_name = ''.join([rm_diacritics(c) for c in name])
    clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', ascii_name)
    return clean_name.lower()

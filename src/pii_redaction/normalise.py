import re
import unicodedata


def normalise(text: str) -> str:
    """Stage 1 — Unicode and whitespace normalisation.

    NFKC folds compatibility characters (e.g. full-width digits, ligatures)
    to their canonical forms, so downstream format detectors see consistent
    input. The structured regex detectors deliberately use explicit ASCII
    character classes (`[2-9]`, `[6-9]`) rather than `\\d`, specifically so
    they don't silently accept a full-width digit as if it were a real
    checksum-bearing ASCII one — which means a full-width Aadhaar or PAN
    number is invisible to them without this step running first.

    Whitespace is collapsed and zero-width characters stripped, because
    both can silently break span-based regex matching (a zero-width space
    inside what looks like a 10-digit phone number splits it into two
    non-matching halves).

    Character offsets downstream (detection, resolution, the audit log)
    are offsets into the string *this function returns*, not the original
    input — see README.
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("​", "").replace("﻿", "")  # zero-width space, BOM
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

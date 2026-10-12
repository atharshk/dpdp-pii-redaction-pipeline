from pii_redaction.detectors.aadhaar import AadhaarDetector, AadhaarNaiveDetector
from pii_redaction.detectors.email import EmailDetector
from pii_redaction.detectors.pan import PANDetector
from pii_redaction.detectors.phone import PhoneDetector

__all__ = [
    "AadhaarDetector",
    "AadhaarNaiveDetector",
    "EmailDetector",
    "PANDetector",
    "PhoneDetector",
    "PresidioNERDetector",
]


def __getattr__(name: str):
    """Import PresidioNERDetector lazily (PEP 562).

    Importing it eagerly here pulled `presidio_analyzer` -- and through it
    spaCy and the ~560 MB `en_core_web_lg` model -- into *every* import of
    this package. Because importing a submodule first executes its parent
    package's `__init__`, that meant

        from pii_redaction.detectors.pan import PANDetector

    which needs none of the NER stack, still failed with
    `ModuleNotFoundError: No module named 'presidio_analyzer'` when that
    stack was not installed. The practical consequence: the `ner` pytest
    marker did not do the one job it exists for, because
    `pytest -m "not ner"` errored during collection instead of running the
    deterministic detector tests.

    CI never caught this, because CI installs every dependency before
    running pytest, so the skip path was never exercised there.
    """
    if name == "PresidioNERDetector":
        from pii_redaction.detectors.ner import PresidioNERDetector

        return PresidioNERDetector
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

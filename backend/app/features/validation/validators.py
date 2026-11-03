import re
from dataclasses import dataclass

from app.features.i18n.translations import validation_text

_VEHICLE_NUMBER_RE = re.compile(r"^[A-Z]{2}\d{1,2}[A-Z]{1,2}\d{4}$")
_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


@dataclass
class ValidationResult:
    valid: bool
    error: str | None = None
    value: str | int | float | None = None  # normalized value, set when valid


def validate_text(
    value, field_label: str, language: str = "en", required: bool = True, max_length: int = 200,
    allowed_values: list[str] | None = None,
) -> ValidationResult:
    if value is None:
        stripped = ""
    else:
        stripped = str(value).strip()

    if required and not stripped:
        return ValidationResult(valid=False, error=validation_text("required", language, label=field_label))

    if len(stripped) > max_length:
        return ValidationResult(
            valid=False, error=validation_text("max_length", language, label=field_label, max=max_length)
        )

    # Defense in depth for closed-set fields (e.g. company_name, brand): the extraction
    # prompt already instructs the LLM to only return one of these exact values or mark the
    # answer ambiguous, but this catches it here too in case that instruction is ever not
    # followed, rather than silently storing a value outside the known set.
    if allowed_values and stripped not in allowed_values:
        return ValidationResult(
            valid=False,
            error=validation_text("must_be_one_of", language, label=field_label, options=", ".join(allowed_values)),
        )

    return ValidationResult(valid=True, value=stripped)


def validate_number(
    value, field_label: str, language: str = "en", min_value: float = 0, max_value: float | None = None
) -> ValidationResult:
    if value is None:
        return ValidationResult(valid=False, error=validation_text("required", language, label=field_label))

    try:
        num = float(value)
    except (TypeError, ValueError):
        return ValidationResult(valid=False, error=validation_text("must_be_number", language, label=field_label))

    if num < min_value:
        return ValidationResult(
            valid=False, error=validation_text("must_be_at_least", language, label=field_label, min=min_value)
        )

    if max_value is not None and num > max_value:
        return ValidationResult(
            valid=False, error=validation_text("must_be_at_most", language, label=field_label, max=max_value)
        )

    normalized = int(num) if num.is_integer() else num
    return ValidationResult(valid=True, value=normalized)


def validate_vehicle_number(value, field_label: str = "Vehicle Number", language: str = "en") -> ValidationResult:
    if not value:
        return ValidationResult(valid=False, error=validation_text("required", language, label=field_label))

    normalized = str(value).strip().upper().replace(" ", "").replace("-", "")

    if not _VEHICLE_NUMBER_RE.match(normalized):
        return ValidationResult(
            valid=False, error=validation_text("vehicle_format", language, label=field_label)
        )

    return ValidationResult(valid=True, value=normalized)


def validate_time(value, field_label: str, language: str = "en") -> ValidationResult:
    if not value:
        return ValidationResult(valid=False, error=validation_text("required", language, label=field_label))

    stripped = str(value).strip()
    if not _TIME_RE.match(stripped):
        return ValidationResult(valid=False, error=validation_text("time_format", language, label=field_label))

    hour, minute = stripped.split(":")
    normalized = f"{int(hour):02d}:{int(minute):02d}"
    return ValidationResult(valid=True, value=normalized)


def validate_time_sequence(
    earlier_time: str, later_time: str, earlier_label: str, later_label: str, language: str = "en"
) -> ValidationResult:
    """Confirms later_time comes after earlier_time (both already in HH:MM 24h format).
    Used for the In/Out vehicle time ordering rule."""
    if later_time <= earlier_time:
        return ValidationResult(
            valid=False,
            error=validation_text(
                "time_after", language,
                later=later_label, later_time=later_time, earlier=earlier_label, earlier_time=earlier_time,
            ),
        )
    return ValidationResult(valid=True)

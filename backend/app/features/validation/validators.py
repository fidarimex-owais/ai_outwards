import re
from dataclasses import dataclass

_VEHICLE_NUMBER_RE = re.compile(r"^[A-Z]{2}\d{1,2}[A-Z]{1,2}\d{4}$")
_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


@dataclass
class ValidationResult:
    valid: bool
    error: str | None = None
    value: str | int | float | None = None  # normalized value, set when valid


def validate_text(value, field_label: str, required: bool = True, max_length: int = 200) -> ValidationResult:
    if value is None:
        stripped = ""
    else:
        stripped = str(value).strip()

    if required and not stripped:
        return ValidationResult(valid=False, error=f"{field_label} is required")

    if len(stripped) > max_length:
        return ValidationResult(valid=False, error=f"{field_label} must be {max_length} characters or fewer")

    return ValidationResult(valid=True, value=stripped)


def validate_number(
    value, field_label: str, min_value: float = 0, max_value: float | None = None
) -> ValidationResult:
    if value is None:
        return ValidationResult(valid=False, error=f"{field_label} is required")

    try:
        num = float(value)
    except (TypeError, ValueError):
        return ValidationResult(valid=False, error=f"{field_label} must be a number")

    if num < min_value:
        return ValidationResult(valid=False, error=f"{field_label} must be at least {min_value}")

    if max_value is not None and num > max_value:
        return ValidationResult(valid=False, error=f"{field_label} must be at most {max_value}")

    normalized = int(num) if num.is_integer() else num
    return ValidationResult(valid=True, value=normalized)


def validate_vehicle_number(value, field_label: str = "Vehicle Number") -> ValidationResult:
    if not value:
        return ValidationResult(valid=False, error=f"{field_label} is required")

    normalized = str(value).strip().upper().replace(" ", "").replace("-", "")

    if not _VEHICLE_NUMBER_RE.match(normalized):
        return ValidationResult(
            valid=False,
            error=f"{field_label} doesn't match a valid plate format (e.g. MH12AB1234)",
        )

    return ValidationResult(valid=True, value=normalized)


def validate_time(value, field_label: str) -> ValidationResult:
    if not value:
        return ValidationResult(valid=False, error=f"{field_label} is required")

    stripped = str(value).strip()
    if not _TIME_RE.match(stripped):
        return ValidationResult(valid=False, error=f"{field_label} must be in HH:MM 24-hour format")

    hour, minute = stripped.split(":")
    normalized = f"{int(hour):02d}:{int(minute):02d}"
    return ValidationResult(valid=True, value=normalized)


def validate_time_sequence(
    earlier_time: str, later_time: str, earlier_label: str, later_label: str
) -> ValidationResult:
    """Confirms later_time comes after earlier_time (both already in HH:MM 24h format).
    Used for the In/Out vehicle time ordering rule."""
    if later_time <= earlier_time:
        return ValidationResult(
            valid=False,
            error=f"{later_label} ({later_time}) must be after {earlier_label} ({earlier_time})",
        )
    return ValidationResult(valid=True)

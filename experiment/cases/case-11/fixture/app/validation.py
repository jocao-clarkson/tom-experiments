from decimal import Decimal, InvalidOperation

from app.errors import ValidationError


def require_positive_amount(raw, field: str = "amount") -> Decimal:
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError):
        raise ValidationError(f"{field} must be a number", details={"field": field})
    if value <= 0:
        raise ValidationError(f"{field} must be greater than zero", details={"field": field})
    if value.as_tuple().exponent < -2:
        raise ValidationError(f"{field} supports at most 2 decimal places", details={"field": field})
    return value

from flask import Blueprint, current_app, jsonify

from .errors import NotFoundError, ValidationError
from .service import OrderService

bp = Blueprint("orders", __name__)


def require_json_fields(body, spec):
    """spec maps field name -> expected type. Raises ValidationError listing all problems."""
    if not isinstance(body, dict):
        raise ValidationError("request body must be a JSON object")
    problems = {}
    for field, expected in spec.items():
        if field not in body:
            problems[field] = "required"
            continue
        value = body[field]
        if expected is int and isinstance(value, bool):
            problems[field] = "must be int"
        elif not isinstance(value, expected):
            problems[field] = f"must be {expected.__name__}"
    if problems:
        raise ValidationError("invalid request body", details=problems)
    return body


def positive_int(value, field):
    if value <= 0:
        raise ValidationError("invalid request body", details={field: "must be positive"})
    return value


def _service():
    return OrderService(
        current_app.extensions["orders.repo"],
        current_app.extensions["orders.payments"],
    )


@bp.get("/orders/<order_id>")
def get_order(order_id):
    order = _service().get_order(order_id)
    if order is None:
        raise NotFoundError(f"order {order_id} not found")
    return jsonify(order)


@bp.post("/orders/<order_id>/capture")
def capture(order_id):
    order = _service().capture(order_id)
    return jsonify(order), 200

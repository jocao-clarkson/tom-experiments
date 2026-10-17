from flask import Blueprint, current_app, jsonify

from .errors import NotFoundError
from .service import OrderService

bp = Blueprint("orders", __name__)


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

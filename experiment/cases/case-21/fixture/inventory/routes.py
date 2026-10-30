from flask import Blueprint, current_app, jsonify, request

from .validation import validate_payload

bp = Blueprint("inventory", __name__)

ADJUST_SCHEMA = {"delta": {"type": int, "required": True, "min": -10000, "max": 10000}}


def _service():
    return current_app.extensions["inventory_service"]


@bp.get("/items")
def list_items():
    return jsonify({"items": _service().list_items()})


@bp.get("/items/<sku>")
def get_item(sku: str):
    return jsonify(_service().get_item(sku))


@bp.post("/items/<sku>/adjust")
def adjust(sku: str):
    body = validate_payload(request.get_json(silent=True), ADJUST_SCHEMA)
    return jsonify(_service().adjust(sku, body["delta"]))


@bp.get("/items/<sku>/supplier-price")
def supplier_price(sku: str):
    return jsonify(_service().supplier_price(sku))

from .errors import ConflictError, NotFoundError, UpstreamError
from .logging_utils import get_logger

log = get_logger(__name__)


class OrderService:
    def __init__(self, repo, payments):
        self.repo = repo
        self.payments = payments

    def get_order(self, order_id):
        return self.repo.get_order(order_id)

    def capture(self, order_id):
        order = self.repo.get_order(order_id)
        if order is None:
            raise NotFoundError(f"order {order_id} not found")
        if order["status"] != "authorized":
            raise ConflictError("order is not in authorized state", code="invalid_state")
        resp = self.payments.get(f"/v1/charges/{order['charge_id']}")
        if resp.status_code >= 400:
            raise UpstreamError("payment provider rejected the request", code="payment_provider_error")
        charge = resp.json()
        with self.repo.transaction():
            self.repo.conn.execute(
                "UPDATE orders SET status = 'captured', captured_cents = ? WHERE id = ?",
                (charge["amount_captured"], order_id),
            )
        log.info("order captured", extra={"order_id": order_id})
        return self.repo.get_order(order_id)

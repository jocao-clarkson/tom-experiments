from .errors import NotFound, UpstreamError, ValidationFailed
from .repository import StockRepository
from .supplier_client import SupplierClient, SupplierError


class InventoryService:
    def __init__(self, repo: StockRepository, supplier: SupplierClient):
        self.repo = repo
        self.supplier = supplier

    def get_item(self, sku: str) -> dict:
        item = self.repo.get_item(sku)
        if item is None:
            raise NotFound(f"item {sku} not found")
        return item

    def list_items(self) -> list[dict]:
        return self.repo.list_items()

    def adjust(self, sku: str, delta: int) -> dict:
        item = self.get_item(sku)
        if item["on_hand"] + delta < 0:
            raise ValidationFailed("on_hand cannot go negative", field="delta")
        self.repo.adjust_on_hand(sku, delta)
        return self.get_item(sku)

    def supplier_price(self, sku: str) -> dict:
        self.get_item(sku)
        try:
            return self.supplier.get(f"/catalog/{sku}/price")
        except SupplierError as exc:
            raise UpstreamError("supplier price lookup failed", supplier_status=exc.status) from exc

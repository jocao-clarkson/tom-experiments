from flask import Flask

from .errors import register_error_handlers
from .repository import StockRepository
from .routes import bp
from .service import InventoryService
from .supplier_client import SupplierClient


def create_app(db_path: str = "inventory.db", supplier: SupplierClient | None = None) -> Flask:
    app = Flask(__name__)
    repo = StockRepository(db_path)
    repo.init_schema()
    supplier = supplier or SupplierClient.from_env()
    app.extensions["inventory_service"] = InventoryService(repo, supplier)
    app.register_blueprint(bp)
    register_error_handlers(app)
    return app

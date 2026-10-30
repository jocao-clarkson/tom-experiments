CREATE TABLE orders (
    order_id     TEXT PRIMARY KEY,
    amount_minor BIGINT NOT NULL,
    currency     CHAR(3) NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL
);

CREATE INDEX orders_created_at_idx ON orders (created_at, currency);

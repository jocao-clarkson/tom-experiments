CREATE TABLE customers (
    id          text PRIMARY KEY,
    tenant_id   text NOT NULL,
    name        text NOT NULL,
    email       text NOT NULL,
    created_at  timestamptz(3) NOT NULL DEFAULT now()
);

CREATE INDEX customers_tenant_created_idx ON customers (tenant_id, created_at DESC, id DESC);

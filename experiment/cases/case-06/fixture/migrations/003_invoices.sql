CREATE TABLE invoices (
    id            text PRIMARY KEY,
    tenant_id     text NOT NULL,
    customer_id   text NOT NULL REFERENCES customers(id),
    status        text NOT NULL CHECK (status IN ('draft', 'open', 'paid', 'void')),
    amount_cents  bigint NOT NULL,
    currency      char(3) NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX invoices_tenant_created_idx ON invoices (tenant_id, created_at DESC, id DESC);
CREATE INDEX invoices_tenant_customer_idx ON invoices (tenant_id, customer_id);

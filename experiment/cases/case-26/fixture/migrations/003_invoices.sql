CREATE TABLE invoices (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    uuid NOT NULL,
    customer_id  uuid NOT NULL,
    number       text NOT NULL,
    status       text NOT NULL CHECK (status IN ('draft', 'open', 'paid', 'void')),
    total_cents  bigint NOT NULL,
    currency     char(3) NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, number)
);

CREATE INDEX invoices_tenant_created_idx ON invoices (tenant_id, created_at DESC, id DESC);

CREATE TABLE refunds (
    id           BIGSERIAL PRIMARY KEY,
    order_id     TEXT NOT NULL REFERENCES orders (id),
    amount       NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    status       TEXT NOT NULL CHECK (status IN ('succeeded', 'failed', 'pending_review')),
    provider_ref TEXT,
    reason       TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX refunds_order_id_idx ON refunds (order_id);

CREATE TABLE products (
    sku         text PRIMARY KEY,
    name        text NOT NULL,
    price_cents bigint NOT NULL CHECK (price_cents BETWEEN 1 AND 10000000),
    currency    char(3) NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE outbox (
    id           bigserial PRIMARY KEY,
    event_type   text NOT NULL,
    event_key    text NOT NULL,
    payload      jsonb NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz
);

CREATE INDEX outbox_unpublished ON outbox (id) WHERE published_at IS NULL;

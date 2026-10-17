CREATE TABLE audit_events (
    id        bigserial PRIMARY KEY,
    at        timestamptz NOT NULL,
    actor     text NOT NULL,
    action    text NOT NULL,
    org_id    text NOT NULL,
    target    text NOT NULL,
    metadata  jsonb NOT NULL DEFAULT '{}'
);

CREATE INDEX audit_events_org_at_idx ON audit_events (org_id, at DESC);

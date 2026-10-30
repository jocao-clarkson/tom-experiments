CREATE TABLE sessions (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES users (id),
    token_hash text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz
);

CREATE INDEX sessions_user_id_idx ON sessions (user_id) WHERE revoked_at IS NULL;

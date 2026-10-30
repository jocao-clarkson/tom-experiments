CREATE TABLE one_time_tokens (
    token_hash  text PRIMARY KEY,
    user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose     text NOT NULL,
    expires_at  timestamptz NOT NULL,
    used_at     timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX one_time_tokens_user_purpose_idx ON one_time_tokens (user_id, purpose);

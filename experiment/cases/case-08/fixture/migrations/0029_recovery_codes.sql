CREATE TABLE recovery_codes (
    user_id    text NOT NULL,
    code_hash  text NOT NULL,
    used_at    timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX recovery_codes_user_idx ON recovery_codes (user_id);

CREATE TABLE devices (
    token       text PRIMARY KEY,
    user_id     text NOT NULL,
    platform    text NOT NULL CHECK (platform IN ('ios', 'android')),
    app_version text NOT NULL DEFAULT '',
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX devices_user_id_idx ON devices (user_id);

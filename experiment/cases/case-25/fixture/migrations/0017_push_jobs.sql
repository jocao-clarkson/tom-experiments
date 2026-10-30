CREATE TABLE push_jobs (
    id         bigserial PRIMARY KEY,
    user_id    text NOT NULL,
    category   text NOT NULL,
    title      text NOT NULL,
    body       text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

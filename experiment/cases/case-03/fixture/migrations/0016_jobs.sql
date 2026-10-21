CREATE TABLE jobs (
    id          bigserial PRIMARY KEY,
    kind        text NOT NULL,
    payload     jsonb NOT NULL,
    attempts    integer NOT NULL DEFAULT 0,
    run_at      timestamptz NOT NULL DEFAULT now(),
    locked_at   timestamptz,
    done_at     timestamptz,
    last_error  text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX jobs_due_idx ON jobs (run_at) WHERE done_at IS NULL;

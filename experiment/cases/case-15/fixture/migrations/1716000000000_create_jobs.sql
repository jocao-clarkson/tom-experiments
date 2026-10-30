-- Up Migration
CREATE TABLE jobs (
  id bigserial PRIMARY KEY,
  kind text NOT NULL,
  payload jsonb NOT NULL,
  run_after timestamptz NOT NULL DEFAULT now(),
  attempts integer NOT NULL DEFAULT 0,
  locked_at timestamptz
);

CREATE INDEX jobs_ready_idx ON jobs (run_after) WHERE locked_at IS NULL;

-- Down Migration
DROP TABLE jobs;

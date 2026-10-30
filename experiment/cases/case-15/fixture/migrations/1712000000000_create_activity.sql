-- Up Migration
CREATE TABLE activity (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  kind text NOT NULL,
  summary text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX activity_user_created_idx ON activity (user_id, created_at DESC, id DESC);

ALTER TABLE activity ENABLE ROW LEVEL SECURITY;
ALTER TABLE activity FORCE ROW LEVEL SECURITY;
CREATE POLICY activity_owner ON activity
  USING (user_id = current_setting('app.user_id', true)::uuid);

-- Down Migration
DROP TABLE activity;

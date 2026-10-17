CREATE TABLE sessions_daily (
    day       DATE NOT NULL,
    platform  TEXT NOT NULL,
    sessions  INTEGER NOT NULL,
    users     INTEGER NOT NULL,
    PRIMARY KEY (day, platform)
);

CREATE TABLE daily_revenue (
    day         DATE NOT NULL,
    currency    CHAR(3) NOT NULL,
    gross_minor BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (day, currency)
);

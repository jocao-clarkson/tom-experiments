import os
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class JobConfig:
    events_bucket: str
    warehouse_dsn: str
    lookback_days: int
    run_date: date

    def days(self) -> list[date]:
        """Days to (re)process, oldest first, ending yesterday relative to run_date."""
        end = self.run_date - timedelta(days=1)
        return [end - timedelta(days=n) for n in range(self.lookback_days - 1, -1, -1)]


def load(run_date: date | None = None) -> JobConfig:
    return JobConfig(
        events_bucket=os.environ.get("ETL_EVENTS_BUCKET", "telemetry-events"),
        warehouse_dsn=os.environ["ETL_WAREHOUSE_DSN"],
        lookback_days=int(os.environ.get("ETL_LOOKBACK_DAYS", "3")),
        run_date=run_date or date.today(),
    )

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class JobConfig:
    input_dir: Path
    output_dir: Path
    session_gap_minutes: int = 30
    statsd_host: str = "127.0.0.1"
    statsd_port: int = 8125
    sections: dict = field(default_factory=dict)

    def section(self, name: str) -> dict:
        """Optional feature sections, e.g. [bot_filter] in job.toml."""
        return dict(self.sections.get(name, {}))


def load(path: str | Path) -> JobConfig:
    raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    job = raw.pop("job")
    return JobConfig(
        input_dir=Path(job["input_dir"]),
        output_dir=Path(job["output_dir"]),
        session_gap_minutes=int(job.get("session_gap_minutes", 30)),
        statsd_host=job.get("statsd_host", "127.0.0.1"),
        statsd_port=int(job.get("statsd_port", 8125)),
        sections=raw,
    )

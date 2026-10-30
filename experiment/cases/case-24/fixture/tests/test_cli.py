import io
import json
from datetime import datetime, timezone

import pytest

from logship import cli
from logship.bundles import bundle_name, list_bundles
from logship.output import Output


@pytest.fixture
def bundle_dir(tmp_path, monkeypatch):
    d = tmp_path / "bundles"
    d.mkdir()
    monkeypatch.setenv("LOGSHIP_BUNDLE_DIR", str(d))
    monkeypatch.setenv("LOGSHIP_CONFIG", str(tmp_path / "missing.toml"))
    return d


def make_bundle(d, at: datetime, uploaded=False, size=10):
    p = d / bundle_name(at)
    p.write_bytes(b"x" * size)
    if uploaded:
        (d / (p.name + ".uploaded")).touch()
    return p


def test_list_json(bundle_dir, capsys):
    make_bundle(bundle_dir, datetime(2024, 3, 1, tzinfo=timezone.utc), uploaded=True)
    make_bundle(bundle_dir, datetime(2024, 3, 2, tzinfo=timezone.utc))
    (bundle_dir / "notes.txt").write_text("ignore me")
    assert cli.main(["--json", "list"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert [b["uploaded"] for b in data["bundles"]] == [True, False]


def test_list_bundles_oldest_first(bundle_dir):
    make_bundle(bundle_dir, datetime(2024, 3, 5, tzinfo=timezone.utc))
    make_bundle(bundle_dir, datetime(2024, 3, 1, tzinfo=timezone.utc))
    names = [b.path.name for b in list_bundles(bundle_dir)]
    assert names == sorted(names)


def test_errors_go_to_stderr_in_json_mode():
    out, err = io.StringIO(), io.StringIO()
    Output(json_mode=True, out=out, err=err).error("boom")
    assert out.getvalue() == ""
    assert json.loads(err.getvalue()) == {"error": "boom"}


def test_bundle_missing_file_is_usage_error(bundle_dir, tmp_path):
    assert cli.main(["bundle", str(tmp_path / "nope.log")]) == cli.EXIT_USAGE

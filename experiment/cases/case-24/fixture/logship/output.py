import json
import sys


class Output:
    """All user-facing output goes through here so --json and --quiet behave
    the same in every command. Errors always go to stderr."""

    def __init__(self, json_mode: bool = False, quiet: bool = False, out=None, err=None):
        self.json_mode = json_mode
        self.quiet = quiet
        self.out = out or sys.stdout
        self.err = err or sys.stderr

    def info(self, message: str) -> None:
        if not self.json_mode and not self.quiet:
            print(message, file=self.out)

    def result(self, data: dict, summary: str) -> None:
        if self.json_mode:
            print(json.dumps(data, default=str, sort_keys=True), file=self.out)
        elif not self.quiet:
            print(summary, file=self.out)

    def error(self, message: str) -> None:
        if self.json_mode:
            print(json.dumps({"error": message}), file=self.err)
        else:
            print(f"logship: error: {message}", file=self.err)

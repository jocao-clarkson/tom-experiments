package commands

import (
	"bytes"
	"flag"
	"os"
	"path/filepath"
	"testing"

	"github.com/larchworks/kit/internal/cli"
)

var update = flag.Bool("update", false, "rewrite golden files")

func run(t *testing.T, home string, args ...string) (stdout, stderr string, code int) {
	t.Helper()
	var out, errb bytes.Buffer
	app := cli.App{Name: "kit", Commands: []cli.Command{List()}}
	io := cli.IO{Out: &out, Err: &errb, Getenv: func(k string) string {
		if k == "KIT_HOME" {
			return home
		}
		return ""
	}}
	code = app.Run(args, io)
	return out.String(), errb.String(), code
}

func golden(t *testing.T, name, got string) {
	t.Helper()
	p := filepath.Join("testdata", name+".golden")
	if *update {
		if err := os.WriteFile(p, []byte(got), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	want, err := os.ReadFile(p)
	if err != nil {
		t.Fatal(err)
	}
	if got != string(want) {
		t.Fatalf("output mismatch for %s\n--- got ---\n%s\n--- want ---\n%s", name, got, want)
	}
}

func TestListTable(t *testing.T) {
	out, _, code := run(t, "testdata", "list")
	if code != cli.ExitOK {
		t.Fatalf("exit = %d", code)
	}
	golden(t, "list_table", out)
}

func TestListJSONFilteredByTag(t *testing.T) {
	out, _, code := run(t, "testdata", "list", "--format", "json", "--tag", "infra")
	if code != cli.ExitOK {
		t.Fatalf("exit = %d", code)
	}
	golden(t, "list_json_infra", out)
}

func TestListUnknownFormat(t *testing.T) {
	_, stderr, code := run(t, "testdata", "list", "--format", "xml")
	if code != cli.ExitUsage {
		t.Fatalf("exit = %d, want %d", code, cli.ExitUsage)
	}
	if stderr == "" {
		t.Fatal("expected an error message")
	}
}

func TestListEmptyStore(t *testing.T) {
	out, _, code := run(t, t.TempDir(), "list", "--format", "json")
	if code != cli.ExitOK || out != "[]\n" {
		t.Fatalf("code=%d out=%q", code, out)
	}
}

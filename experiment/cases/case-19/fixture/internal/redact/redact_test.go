package redact

import (
	"strings"
	"testing"
)

func TestLineMasksSecrets(t *testing.T) {
	cases := map[string]string{
		"user=jo@example.com logged in":       "user=[REDACTED] logged in",
		"Authorization: Bearer abc.def.ghi":   "Authorization: [REDACTED]",
		"key AKIAABCDEFGHIJKLMNOP used":       "key [REDACTED] used",
		"db password=hunter2 ok":              "db [REDACTED] ok",
		"conn from 10.1.2.3 closed":           "conn from [REDACTED] closed",
	}
	for in, want := range cases {
		if got, _ := Line(in); got != want {
			t.Errorf("Line(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestLinesCountsHits(t *testing.T) {
	_, hits, err := Lines(strings.NewReader("a@b.io\nnothing here\npassword: x\n"))
	if err != nil || hits != 2 {
		t.Fatalf("hits=%d err=%v", hits, err)
	}
}

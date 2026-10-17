package redact

import (
	"bufio"
	"io"
	"regexp"
)

var patterns = []*regexp.Regexp{
	regexp.MustCompile(`[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}`),
	regexp.MustCompile(`(?i)bearer\s+[A-Za-z0-9._~+/=-]+`),
	regexp.MustCompile(`AKIA[0-9A-Z]{16}`),
	regexp.MustCompile(`(?i)(password|passwd|secret|api[_-]?key)\s*[=:]\s*\S+`),
	regexp.MustCompile(`\b(?:\d{1,3}\.){3}\d{1,3}\b`),
}

const mask = "[REDACTED]"

// Line scrubs a single line and reports how many substitutions were made.
func Line(s string) (string, int) {
	hits := 0
	for _, p := range patterns {
		s = p.ReplaceAllStringFunc(s, func(string) string { hits++; return mask })
	}
	return s, hits
}

// Lines reads r fully and returns the scrubbed lines with the total hit count.
func Lines(r io.Reader) ([]string, int, error) {
	sc := bufio.NewScanner(r)
	sc.Buffer(make([]byte, 64*1024), 1024*1024)
	var out []string
	total := 0
	for sc.Scan() {
		line, n := Line(sc.Text())
		out = append(out, line)
		total += n
	}
	return out, total, sc.Err()
}

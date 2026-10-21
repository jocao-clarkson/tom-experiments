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

// Copy scrubs src line by line into dst and returns the total hit count.
// Each output line is terminated with "\n".
func Copy(dst io.Writer, src io.Reader) (int, error) {
	sc := bufio.NewScanner(src)
	sc.Buffer(make([]byte, 64*1024), 1024*1024)
	w := bufio.NewWriter(dst)
	total := 0
	for sc.Scan() {
		line, n := Line(sc.Text())
		total += n
		if _, err := w.WriteString(line); err != nil {
			return total, err
		}
		if err := w.WriteByte('\n'); err != nil {
			return total, err
		}
	}
	if err := sc.Err(); err != nil {
		return total, err
	}
	return total, w.Flush()
}

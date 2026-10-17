package metrics

import (
	"sort"
	"strings"
	"sync"
)

var (
	mu       sync.Mutex
	counters = map[string]int64{}
)

func key(name string, labels map[string]string) string {
	parts := make([]string, 0, len(labels))
	for k, v := range labels {
		parts = append(parts, k+"="+v)
	}
	sort.Strings(parts)
	return name + "{" + strings.Join(parts, ",") + "}"
}

// Inc increments a labelled counter. Exported via the /metrics handler.
func Inc(name string, labels map[string]string) {
	mu.Lock()
	counters[key(name, labels)]++
	mu.Unlock()
}

func Value(name string, labels map[string]string) int64 {
	mu.Lock()
	defer mu.Unlock()
	return counters[key(name, labels)]
}

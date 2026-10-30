package metrics

import (
	"sync"
)

// Counter is a monotonically increasing value labelled by stream.
type Counter struct {
	mu   sync.Mutex
	name string
	vals map[string]int64
}

var (
	registryMu sync.Mutex
	registry   = map[string]*Counter{}
)

// NewCounter returns the counter with the given name, creating it once.
func NewCounter(name string) *Counter {
	registryMu.Lock()
	defer registryMu.Unlock()
	if c, ok := registry[name]; ok {
		return c
	}
	c := &Counter{name: name, vals: map[string]int64{}}
	registry[name] = c
	return c
}

func (c *Counter) Add(stream string, n int) {
	c.mu.Lock()
	c.vals[stream] += int64(n)
	c.mu.Unlock()
}

func (c *Counter) Value(stream string) int64 {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.vals[stream]
}

var (
	rowsIngested     = NewCounter("rows_ingested")
	rowsDeadLettered = NewCounter("rows_dead_lettered")
)

// RecordBatch counts the rows written and dead-lettered for one committed
// batch of a stream.
func RecordBatch(stream string, written, deadLettered int) {
	rowsIngested.Add(stream, written)
	rowsDeadLettered.Add(stream, deadLettered)
}

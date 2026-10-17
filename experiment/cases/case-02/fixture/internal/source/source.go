package source

import (
	"context"
	"os"
	"strings"

	"github.com/twmb/franz-go/pkg/kgo"
)

// Message is one record read from a topic partition.
type Message struct {
	Partition int32
	Offset    int64
	Key       []byte
	Value     []byte
	record    *kgo.Record
}

// Source is a partitioned, at-least-once message source. Messages after the
// last committed offset are redelivered after a restart.
type Source interface {
	Poll(ctx context.Context, max int) ([]Message, error)
	Commit(ctx context.Context, msgs []Message) error
	Close() error
}

type kafkaSource struct {
	cl *kgo.Client
}

// NewKafka returns a consumer-group source with auto-commit disabled.
func NewKafka(topic, group string) (Source, error) {
	cl, err := kgo.NewClient(
		kgo.SeedBrokers(strings.Split(os.Getenv("KAFKA_BROKERS"), ",")...),
		kgo.ConsumerGroup(group),
		kgo.ConsumeTopics(topic),
		kgo.DisableAutoCommit(),
	)
	if err != nil {
		return nil, err
	}
	return &kafkaSource{cl: cl}, nil
}

func (k *kafkaSource) Poll(ctx context.Context, max int) ([]Message, error) {
	fetches := k.cl.PollRecords(ctx, max)
	if err := fetches.Err0(); err != nil {
		return nil, err
	}
	var out []Message
	fetches.EachRecord(func(r *kgo.Record) {
		out = append(out, Message{Partition: r.Partition, Offset: r.Offset, Key: r.Key, Value: r.Value, record: r})
	})
	return out, nil
}

func (k *kafkaSource) Commit(ctx context.Context, msgs []Message) error {
	recs := make([]*kgo.Record, 0, len(msgs))
	for _, m := range msgs {
		if m.record != nil {
			recs = append(recs, m.record)
		}
	}
	return k.cl.CommitRecords(ctx, recs...)
}

func (k *kafkaSource) Close() error {
	k.cl.Close()
	return nil
}

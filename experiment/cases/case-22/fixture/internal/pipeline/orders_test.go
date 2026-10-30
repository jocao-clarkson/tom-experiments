package pipeline

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"github.com/northwind/revpipe/internal/config"
	"github.com/northwind/revpipe/internal/load"
)

type fakeStore struct {
	orders     map[string]load.Order
	recomputed []load.DayKey
}

func (f *fakeStore) UpsertOrders(_ context.Context, orders []load.Order) error {
	for _, o := range orders {
		f.orders[o.OrderID] = o
	}
	return nil
}

func (f *fakeStore) RecomputeDailyRevenue(_ context.Context, keys []load.DayKey) error {
	f.recomputed = append(f.recomputed, keys...)
	return nil
}

func TestRunOrdersIsRerunnable(t *testing.T) {
	dir := t.TempDir()
	csv := "order_id,amount,currency,created_at\n" +
		"o1,10.00,USD,2024-03-01T10:00:00Z\n" +
		"o2,5.25,USD,2024-03-01T23:59:00Z\n" +
		"o3,bad,USD,2024-03-02T01:00:00Z\n"
	if err := os.WriteFile(filepath.Join(dir, "orders_1.csv"), []byte(csv), 0o644); err != nil {
		t.Fatal(err)
	}
	store := &fakeStore{orders: map[string]load.Order{}}
	cfg := config.Config{InputDir: dir, BatchSize: 1}
	for i := 0; i < 2; i++ {
		if err := RunOrders(context.Background(), cfg, store); err != nil {
			t.Fatal(err)
		}
	}
	if len(store.orders) != 2 {
		t.Fatalf("want 2 orders, got %d", len(store.orders))
	}
	if store.orders["o2"].Amount != 525 {
		t.Fatalf("o2 amount = %d", store.orders["o2"].Amount)
	}
}

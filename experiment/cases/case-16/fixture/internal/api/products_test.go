package api

import (
	"testing"
)

func TestPriceRequestValidate(t *testing.T) {
	cases := []struct {
		name string
		req  priceRequest
		ok   bool
	}{
		{"valid", priceRequest{PriceCents: 1999, Currency: "USD"}, true},
		{"zero price", priceRequest{PriceCents: 0, Currency: "USD"}, false},
		{"lowercase currency", priceRequest{PriceCents: 100, Currency: "usd"}, false},
		{"too large", priceRequest{PriceCents: 10_000_001, Currency: "EUR"}, false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := tc.req.validate() == ""; got != tc.ok {
				t.Fatalf("validate() ok=%v, want %v", got, tc.ok)
			}
		})
	}
}

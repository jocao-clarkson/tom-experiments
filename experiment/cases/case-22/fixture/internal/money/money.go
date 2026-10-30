// Package money holds amounts as integer minor units. All amounts that
// enter the warehouse are parsed here.
package money

import (
	"fmt"
	"strconv"
	"strings"
)

type Minor int64

var exponents = map[string]int{
	"USD": 2, "EUR": 2, "GBP": 2, "CAD": 2, "JPY": 0, "KWD": 3,
}

// Parse converts a decimal string such as "12.50" into minor units for the
// given ISO currency. It rejects more fractional digits than the currency
// allows and never goes through floating point.
func Parse(amount, currency string) (Minor, error) {
	exp, ok := exponents[strings.ToUpper(currency)]
	if !ok {
		return 0, fmt.Errorf("unsupported currency %q", currency)
	}
	s := strings.TrimSpace(amount)
	neg := strings.HasPrefix(s, "-")
	s = strings.TrimPrefix(s, "-")
	whole, frac, _ := strings.Cut(s, ".")
	if len(frac) > exp {
		return 0, fmt.Errorf("amount %q has more than %d decimal places", amount, exp)
	}
	frac += strings.Repeat("0", exp-len(frac))
	n, err := strconv.ParseInt(whole+frac, 10, 64)
	if err != nil {
		return 0, fmt.Errorf("invalid amount %q", amount)
	}
	if neg {
		n = -n
	}
	return Minor(n), nil
}

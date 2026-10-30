// Package pii masks customer data before it leaves the warehouse
// (log lines, files handed to other teams, error messages).
package pii

import "strings"

// Columns that must never appear unmasked outside the warehouse.
var Columns = map[string]bool{
	"customer_email": true,
	"customer_name":  true,
	"customer_phone": true,
}

func MaskEmail(email string) string {
	user, domain, ok := strings.Cut(email, "@")
	if !ok || user == "" {
		return "***"
	}
	return user[:1] + "***@" + domain
}

// RedactRow returns a copy of row with PII columns masked.
func RedactRow(row map[string]string) map[string]string {
	out := make(map[string]string, len(row))
	for k, v := range row {
		switch {
		case k == "customer_email":
			out[k] = MaskEmail(v)
		case Columns[k]:
			out[k] = "***"
		default:
			out[k] = v
		}
	}
	return out
}

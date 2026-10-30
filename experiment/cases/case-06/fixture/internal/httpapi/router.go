package httpapi

import (
	"net/http"

	"github.com/quillpay/billing-api/internal/auth"
)

type Deps struct {
	Keys      auth.KeyResolver
	Customers CustomerLister
}

func NewRouter(d Deps) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]bool{"ok": true})
	})

	api := http.NewServeMux()
	api.Handle("GET /v1/customers", listCustomers(d.Customers))

	mux.Handle("/v1/", auth.Tenant(d.Keys, writeError)(api))
	return mux
}

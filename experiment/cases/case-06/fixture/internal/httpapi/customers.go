package httpapi

import (
	"context"
	"net/http"

	"github.com/quillpay/billing-api/internal/auth"
	"github.com/quillpay/billing-api/internal/store"
)

type CustomerLister interface {
	List(ctx context.Context, tenantID string, after *store.After, limit int) ([]store.Customer, error)
}

func listCustomers(s CustomerLister) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		limit, err := parseLimit(r)
		if err != nil {
			writeError(w, http.StatusBadRequest, "invalid_parameter", err.Error())
			return
		}
		cur, err := decodeCursor(r.URL.Query().Get("cursor"))
		if err != nil {
			writeError(w, http.StatusBadRequest, "invalid_parameter", "cursor is invalid")
			return
		}
		var after *store.After
		if cur != nil {
			after = &store.After{CreatedAt: cur.CreatedAt, ID: cur.ID}
		}

		items, err := s.List(r.Context(), auth.TenantID(r.Context()), after, limit)
		if err != nil {
			writeError(w, http.StatusInternalServerError, "internal_error", "could not list customers")
			return
		}
		resp := listResponse[store.Customer]{Data: items}
		if len(items) > limit {
			last := items[limit-1]
			resp.Data = items[:limit]
			resp.NextCursor = encodeCursor(Cursor{CreatedAt: last.CreatedAt, ID: last.ID})
		}
		if resp.Data == nil {
			resp.Data = []store.Customer{}
		}
		writeJSON(w, http.StatusOK, resp)
	}
}

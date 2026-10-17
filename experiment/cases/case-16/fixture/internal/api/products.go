package api

import (
	"encoding/json"
	"errors"
	"net/http"
	"regexp"

	"github.com/lumenmart/catalog/internal/apierr"
	"github.com/lumenmart/catalog/internal/cache"
	"github.com/lumenmart/catalog/internal/store"
)

var currencyRe = regexp.MustCompile(`^[A-Z]{3}$`)

type ProductsHandler struct {
	Store *store.Store
	Cache *cache.TTL[store.Product]
}

func (h *ProductsHandler) Get(w http.ResponseWriter, r *http.Request) {
	sku := r.PathValue("sku")
	if p, ok := h.Cache.Get(sku); ok {
		writeJSON(w, http.StatusOK, p)
		return
	}
	p, err := h.Store.GetProduct(r.Context(), sku)
	if errors.Is(err, store.ErrNotFound) {
		apierr.Write(w, http.StatusNotFound, "not_found", "product not found", nil)
		return
	}
	if err != nil {
		apierr.Write(w, http.StatusInternalServerError, "internal", "internal error", nil)
		return
	}
	h.Cache.Set(sku, p)
	writeJSON(w, http.StatusOK, p)
}

type priceRequest struct {
	PriceCents int64  `json:"price_cents"`
	Currency   string `json:"currency"`
}

func (r priceRequest) validate() string {
	if r.PriceCents <= 0 || r.PriceCents > 10_000_000 {
		return "price_cents must be between 1 and 10000000"
	}
	if !currencyRe.MatchString(r.Currency) {
		return "currency must be an ISO 4217 code"
	}
	return ""
}

func (h *ProductsHandler) UpdatePrice(w http.ResponseWriter, r *http.Request) {
	sku := r.PathValue("sku")
	var req priceRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		apierr.Write(w, http.StatusBadRequest, "bad_request", "invalid JSON", nil)
		return
	}
	if msg := req.validate(); msg != "" {
		apierr.Write(w, http.StatusUnprocessableEntity, "validation_failed", msg, nil)
		return
	}
	err := h.Store.UpdatePrice(r.Context(), sku, req.PriceCents, req.Currency)
	if errors.Is(err, store.ErrNotFound) {
		apierr.Write(w, http.StatusNotFound, "not_found", "product not found", nil)
		return
	}
	if err != nil {
		apierr.Write(w, http.StatusInternalServerError, "internal", "internal error", nil)
		return
	}
	h.Cache.Delete(sku)
	w.WriteHeader(http.StatusNoContent)
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

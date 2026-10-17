package api

import (
	"net/http"

	"github.com/lumenmart/catalog/internal/auth"
)

func NewRouter(products *ProductsHandler, authenticate func(http.Handler) http.Handler) http.Handler {
	mux := http.NewServeMux()
	mux.Handle("GET /v1/products/{sku}", http.HandlerFunc(products.Get))
	mux.Handle("PATCH /v1/products/{sku}/price", auth.RequireScope("catalog:write", http.HandlerFunc(products.UpdatePrice)))
	return authenticate(mux)
}

package main

import (
	"database/sql"
	"log"
	"net/http"
	"os"

	_ "github.com/lib/pq"

	"github.com/pebbleapp/api/internal/devices"
	"github.com/pebbleapp/api/internal/httpx"
)

func main() {
	db, err := sql.Open("postgres", os.Getenv("DATABASE_URL"))
	if err != nil {
		log.Fatal(err)
	}
	devRepo := devices.NewSQLRepo(db)

	mux := http.NewServeMux()
	mux.Handle("POST /v1/devices", devices.RegisterHandler(devRepo))
	mux.Handle("DELETE /v1/devices/{token}", devices.UnregisterHandler(devRepo))

	handler := httpx.RequestID(httpx.AppVersion(httpx.RequireUser(mux)))
	log.Fatal(http.ListenAndServe(":8080", handler))
}

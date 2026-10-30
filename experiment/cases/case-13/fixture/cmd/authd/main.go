package main

import (
	"database/sql"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/redis/go-redis/v9"

	"github.com/northwind/authd/internal/httpx"
	"github.com/northwind/authd/internal/notify"
	"github.com/northwind/authd/internal/session"
	"github.com/northwind/authd/internal/user"
)

func main() {
	db, err := sql.Open("pgx", os.Getenv("DATABASE_URL"))
	if err != nil {
		log.Fatal(err)
	}
	rdb := redis.NewClient(&redis.Options{Addr: os.Getenv("REDIS_ADDR")})

	users := user.NewRepo(db)
	sessions := session.NewRedisStore(rdb)
	mail := notify.NewQueue(newSESSender(), 1000)

	mux := http.NewServeMux()
	mux.Handle("POST /login", httpx.RateLimit(httpx.ClientIP, 30, time.Minute, loginHandler(users, sessions, mail)))
	mux.Handle("GET /me", httpx.RequireAuth(sessions, users, meHandler()))

	log.Fatal(http.ListenAndServe(":8080", mux))
}

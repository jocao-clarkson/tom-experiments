package main

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"net/http"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/northwind/authd/internal/audit"
	"github.com/northwind/authd/internal/httpx"
	"github.com/northwind/authd/internal/notify"
	"github.com/northwind/authd/internal/session"
	"github.com/northwind/authd/internal/user"
)

const sessionTTL = 24 * time.Hour

func randomID() string {
	b := make([]byte, 32)
	_, _ = rand.Read(b)
	return base64.RawURLEncoding.EncodeToString(b)
}

func loginHandler(users *user.Repo, sessions session.Store) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var body struct{ Email, Password string }
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			http.Error(w, "bad request", http.StatusBadRequest)
			return
		}
		u, err := users.ByEmail(r.Context(), body.Email)
		if err != nil || u.Disabled || bcrypt.CompareHashAndPassword(u.PasswordHash, []byte(body.Password)) != nil {
			audit.Emit(r.Context(), audit.Event{Type: "login.failed", IP: httpx.ClientIP(r)})
			http.Error(w, "invalid credentials", http.StatusUnauthorized)
			return
		}
		now := time.Now()
		s := session.Session{ID: randomID(), UserID: u.ID, IssuedAt: now, ExpiresAt: now.Add(sessionTTL), UserAgent: r.UserAgent()}
		if err := sessions.Create(r.Context(), s); err != nil {
			http.Error(w, "internal error", http.StatusInternalServerError)
			return
		}
		audit.Emit(r.Context(), audit.Event{Type: "login.succeeded", UserID: u.ID, IP: httpx.ClientIP(r)})
		http.SetCookie(w, &http.Cookie{Name: "sid", Value: s.ID, HttpOnly: true, Secure: true, SameSite: http.SameSiteLaxMode, Expires: s.ExpiresAt})
		w.WriteHeader(http.StatusNoContent)
	})
}

func meHandler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		u, _ := httpx.CurrentUser(r.Context())
		_ = json.NewEncoder(w).Encode(map[string]string{"id": u.ID, "email": u.Email})
	})
}

// relaySender posts messages to the internal mail relay, which renders templates and sends via SES.
type relaySender struct {
	url    string
	client *http.Client
}

func newSESSender() notify.Sender {
	return relaySender{url: os.Getenv("MAIL_RELAY_URL"), client: &http.Client{Timeout: 5 * time.Second}}
}

func (s relaySender) Send(ctx context.Context, m notify.Message) error {
	b, err := json.Marshal(m)
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, s.url, bytes.NewReader(b))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := s.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		return fmt.Errorf("mail relay returned %d", resp.StatusCode)
	}
	return nil
}

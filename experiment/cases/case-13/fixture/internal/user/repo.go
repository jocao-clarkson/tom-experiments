package user

import (
	"context"
	"database/sql"
	"errors"
	"time"
	"unicode"

	"golang.org/x/crypto/bcrypt"
)

var (
	ErrNotFound     = errors.New("user not found")
	ErrWeakPassword = errors.New("password does not meet policy")
)

type User struct {
	ID                string
	Email             string
	PasswordHash      []byte
	Disabled          bool
	PasswordChangedAt time.Time
}

type Repo struct{ db *sql.DB }

func NewRepo(db *sql.DB) *Repo { return &Repo{db: db} }

func (r *Repo) ByEmail(ctx context.Context, email string) (User, error) {
	return r.one(ctx, `SELECT id, email, password_hash, disabled, password_changed_at FROM users WHERE lower(email) = lower($1)`, email)
}

func (r *Repo) ByID(ctx context.Context, id string) (User, error) {
	return r.one(ctx, `SELECT id, email, password_hash, disabled, password_changed_at FROM users WHERE id = $1`, id)
}

func (r *Repo) one(ctx context.Context, q string, arg string) (User, error) {
	var u User
	err := r.db.QueryRowContext(ctx, q, arg).Scan(&u.ID, &u.Email, &u.PasswordHash, &u.Disabled, &u.PasswordChangedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return User{}, ErrNotFound
	}
	return u, err
}

// SetPassword validates, hashes and stores a new password.
func (r *Repo) SetPassword(ctx context.Context, id, plain string) error {
	if err := ValidatePassword(plain); err != nil {
		return err
	}
	hash, err := bcrypt.GenerateFromPassword([]byte(plain), 12)
	if err != nil {
		return err
	}
	_, err = r.db.ExecContext(ctx, `UPDATE users SET password_hash = $1, password_changed_at = now() WHERE id = $2`, hash, id)
	return err
}

func ValidatePassword(p string) error {
	if len(p) < 12 {
		return ErrWeakPassword
	}
	var letter, digit bool
	for _, c := range p {
		letter = letter || unicode.IsLetter(c)
		digit = digit || unicode.IsDigit(c)
	}
	if !letter || !digit {
		return ErrWeakPassword
	}
	return nil
}

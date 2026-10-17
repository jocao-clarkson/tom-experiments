package users

import (
	"context"
	"database/sql"
	"errors"
)

var ErrConflict = errors.New("concurrent update")

type User struct {
	ID            string
	DisplayName   string
	Email         string
	AvatarVersion int // 0 means no avatar
}

type Repo struct {
	DB *sql.DB
}

func (r *Repo) Get(ctx context.Context, id string) (User, error) {
	var u User
	err := r.DB.QueryRowContext(ctx,
		`SELECT id, display_name, email, avatar_version FROM users WHERE id = $1`, id,
	).Scan(&u.ID, &u.DisplayName, &u.Email, &u.AvatarVersion)
	return u, err
}

// SetAvatarVersion moves the user from version `from` to `to` atomically.
// It returns ErrConflict if another update got there first.
func (r *Repo) SetAvatarVersion(ctx context.Context, id string, from, to int) error {
	res, err := r.DB.ExecContext(ctx,
		`UPDATE users SET avatar_version = $3, updated_at = now() WHERE id = $1 AND avatar_version = $2`,
		id, from, to)
	if err != nil {
		return err
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return ErrConflict
	}
	return nil
}

package store

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
)

type Project struct {
	ID    string   `json:"id"`
	Name  string   `json:"name"`
	Owner string   `json:"owner"`
	Tags  []string `json:"tags"`
}

type Store struct {
	path string
}

// DefaultPath is $KIT_HOME/projects.json, falling back to ~/.kit/projects.json.
func DefaultPath(getenv func(string) string) (string, error) {
	if home := getenv("KIT_HOME"); home != "" {
		return filepath.Join(home, "projects.json"), nil
	}
	h, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(h, ".kit", "projects.json"), nil
}

func Open(path string) *Store { return &Store{path: path} }

// List returns projects sorted by ID. If tag is non-empty, only projects
// carrying that tag are returned. A missing store file is an empty list.
func (s *Store) List(tag string) ([]Project, error) {
	b, err := os.ReadFile(s.path)
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("read store: %w", err)
	}
	var all []Project
	if err := json.Unmarshal(b, &all); err != nil {
		return nil, fmt.Errorf("parse store %s: %w", s.path, err)
	}
	out := all[:0]
	for _, p := range all {
		if tag == "" || hasTag(p, tag) {
			out = append(out, p)
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i].ID < out[j].ID })
	return out, nil
}

func hasTag(p Project, tag string) bool {
	for _, t := range p.Tags {
		if t == tag {
			return true
		}
	}
	return false
}

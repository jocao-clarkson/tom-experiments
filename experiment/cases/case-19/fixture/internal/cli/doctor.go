package cli

import (
	"fmt"
	"os"
	"strings"
)

func init() {
	register(Command{Name: "doctor", Short: "check configuration and log access", Run: runDoctor})
}

type doctorCheck struct {
	Name   string `json:"name"`
	Target string `json:"target,omitempty"`
	OK     bool   `json:"ok"`
	Detail string `json:"detail,omitempty"`
}

func runDoctor(env *Env, args []string) int {
	if len(args) != 0 {
		fmt.Fprintln(env.Stderr, "usage: logship doctor")
		return ExitUsage
	}
	checks := []doctorCheck{
		{Name: "endpoint", Target: env.Cfg.Endpoint, OK: env.Cfg.Endpoint != ""},
		{Name: "token", OK: env.Cfg.Token != ""},
	}
	for _, dir := range env.Cfg.LogDirs {
		checks = append(checks, readable("log_dir", dir))
	}
	if env.Cfg.SystemLog != "" {
		checks = append(checks, readable("system_log", env.Cfg.SystemLog))
	}

	var b strings.Builder
	failed := 0
	for _, c := range checks {
		status := "ok"
		if !c.OK {
			status = "FAIL"
			failed++
		}
		fmt.Fprintf(&b, "%-10s %-4s %s %s\n", c.Name, status, c.Target, c.Detail)
	}
	env.Out.Result(checks, strings.TrimRight(b.String(), "\n"))
	if failed > 0 {
		return ExitError
	}
	return ExitOK
}

func readable(name, path string) doctorCheck {
	c := doctorCheck{Name: name, Target: path}
	f, err := os.Open(path)
	if err != nil {
		c.Detail = err.Error()
		return c
	}
	f.Close()
	c.OK = true
	return c
}

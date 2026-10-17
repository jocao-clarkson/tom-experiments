package cli

import (
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
)

// Exit codes shared by every kit command.
const (
	ExitOK      = 0
	ExitFailure = 1
	ExitUsage   = 2
)

// IO bundles the streams a command may use, so tests can capture output.
type IO struct {
	In     io.Reader
	Out    io.Writer
	Err    io.Writer
	Getenv func(string) string
}

func StdIO() IO {
	return IO{In: os.Stdin, Out: os.Stdout, Err: os.Stderr, Getenv: os.Getenv}
}

// UsageError marks bad flags or arguments; it maps to ExitUsage.
type UsageError struct{ Msg string }

func (e *UsageError) Error() string { return e.Msg }

func Usagef(format string, args ...any) error {
	return &UsageError{Msg: fmt.Sprintf(format, args...)}
}

// Command is one kit subcommand. Flags registers flags on fs; Run executes
// with the remaining positional arguments.
type Command struct {
	Name    string
	Summary string
	Flags   func(fs *flag.FlagSet)
	Run     func(args []string, io IO) error
}

type App struct {
	Name     string
	Commands []Command
}

func (a App) Run(argv []string, io IO) int {
	if len(argv) == 0 {
		a.usage(io.Err)
		return ExitUsage
	}
	for _, c := range a.Commands {
		if c.Name != argv[0] {
			continue
		}
		fs := flag.NewFlagSet(a.Name+" "+c.Name, flag.ContinueOnError)
		fs.SetOutput(io.Err)
		if c.Flags != nil {
			c.Flags(fs)
		}
		if err := fs.Parse(argv[1:]); err != nil {
			return ExitUsage
		}
		err := c.Run(fs.Args(), io)
		return exitCode(err, io.Err)
	}
	fmt.Fprintf(io.Err, "%s: unknown command %q\n", a.Name, argv[0])
	a.usage(io.Err)
	return ExitUsage
}

func exitCode(err error, stderr io.Writer) int {
	if err == nil {
		return ExitOK
	}
	fmt.Fprintf(stderr, "error: %s\n", err)
	var ue *UsageError
	if errors.As(err, &ue) {
		return ExitUsage
	}
	return ExitFailure
}

func (a App) usage(w io.Writer) {
	fmt.Fprintf(w, "usage: %s <command> [flags]\n\ncommands:\n", a.Name)
	for _, c := range a.Commands {
		fmt.Fprintf(w, "  %-10s %s\n", c.Name, c.Summary)
	}
}

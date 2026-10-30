package cli

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"

	"github.com/quayside/logship/internal/config"
)

// Exit codes are part of the CLI contract; scripts depend on them.
const (
	ExitOK      = 0
	ExitError   = 1
	ExitUsage   = 2
	ExitPartial = 3
	ExitUpload  = 4
)

type Env struct {
	Cfg    config.Config
	Out    Printer
	Stderr io.Writer
}

type Command struct {
	Name  string
	Short string
	Run   func(env *Env, args []string) int
}

var commands = map[string]Command{}

func register(c Command) { commands[c.Name] = c }

// Printer renders a command's result according to the global --output flag.
type Printer interface {
	Result(v any, text string)
}

type textPrinter struct{ w io.Writer }

func (p textPrinter) Result(_ any, text string) { fmt.Fprintln(p.w, text) }

type jsonPrinter struct{ w io.Writer }

func (p jsonPrinter) Result(v any, _ string) { _ = json.NewEncoder(p.w).Encode(v) }

func Run(args []string, stdout, stderr io.Writer) int {
	global := flag.NewFlagSet("logship", flag.ContinueOnError)
	global.SetOutput(stderr)
	cfgPath := global.String("config", config.DefaultPath(), "path to config file")
	output := global.String("output", "text", "output format: text or json")
	if err := global.Parse(args); err != nil {
		return ExitUsage
	}
	rest := global.Args()
	if len(rest) == 0 {
		fmt.Fprintln(stderr, "usage: logship [--config path] [--output text|json] <command> [flags]")
		return ExitUsage
	}
	cmd, ok := commands[rest[0]]
	if !ok {
		fmt.Fprintf(stderr, "unknown command %q\n", rest[0])
		return ExitUsage
	}
	cfg, err := config.Load(*cfgPath)
	if err != nil {
		fmt.Fprintf(stderr, "config: %v\n", err)
		return ExitError
	}
	var p Printer = textPrinter{stdout}
	switch *output {
	case "text":
	case "json":
		p = jsonPrinter{stdout}
	default:
		fmt.Fprintf(stderr, "invalid --output %q\n", *output)
		return ExitUsage
	}
	return cmd.Run(&Env{Cfg: cfg, Out: p, Stderr: stderr}, rest[1:])
}

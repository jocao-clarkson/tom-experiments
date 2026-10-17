package cli

import (
	"context"
	"flag"
	"fmt"
	"os"
	"time"

	"github.com/quayside/logship/internal/transport"
)

func init() {
	register(Command{Name: "upload", Short: "upload an existing bundle to support", Run: runUpload})
}

type uploadResult struct {
	Bundle   string `json:"bundle"`
	TicketID string `json:"ticket_id"`
	Bytes    int64  `json:"bytes"`
}

func runUpload(env *Env, args []string) int {
	fs := flag.NewFlagSet("upload", flag.ContinueOnError)
	fs.SetOutput(env.Stderr)
	ticket := fs.String("ticket", "", "support ticket ID")
	if err := fs.Parse(args); err != nil || fs.NArg() != 1 || *ticket == "" {
		fmt.Fprintln(env.Stderr, "usage: logship upload --ticket ID <bundle.tar.gz>")
		return ExitUsage
	}
	return uploadBundle(env, fs.Arg(0), *ticket)
}

func uploadBundle(env *Env, path, ticket string) int {
	f, err := os.Open(path)
	if err != nil {
		fmt.Fprintf(env.Stderr, "open bundle: %v\n", err)
		return ExitError
	}
	defer f.Close()
	info, _ := f.Stat()

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Minute)
	defer cancel()
	client := transport.New(env.Cfg.Endpoint, env.Cfg.Token)
	if err := client.Upload(ctx, ticket, f, info.Size()); err != nil {
		fmt.Fprintf(env.Stderr, "upload failed: %v\n", err)
		return ExitUpload
	}
	env.Out.Result(uploadResult{Bundle: path, TicketID: ticket, Bytes: info.Size()},
		fmt.Sprintf("uploaded %s (%d bytes) to ticket %s", path, info.Size(), ticket))
	return ExitOK
}

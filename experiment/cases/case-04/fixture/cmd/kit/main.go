package main

import (
	"os"

	"github.com/larchworks/kit/internal/cli"
	"github.com/larchworks/kit/internal/commands"
)

func main() {
	app := cli.App{
		Name: "kit",
		Commands: []cli.Command{
			commands.List(),
		},
	}
	os.Exit(app.Run(os.Args[1:], cli.StdIO()))
}

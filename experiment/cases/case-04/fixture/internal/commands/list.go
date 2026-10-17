package commands

import (
	"flag"
	"strings"

	"github.com/larchworks/kit/internal/cli"
	"github.com/larchworks/kit/internal/store"
)

func List() cli.Command {
	var format, tag string
	return cli.Command{
		Name:    "list",
		Summary: "List projects",
		Flags: func(fs *flag.FlagSet) {
			fs.StringVar(&format, "format", cli.FormatTable, "output format: table or json")
			fs.StringVar(&tag, "tag", "", "only projects with this tag")
		},
		Run: func(args []string, io cli.IO) error {
			if len(args) > 0 {
				return cli.Usagef("list takes no arguments")
			}
			if err := cli.CheckFormat(format, cli.FormatTable, cli.FormatJSON); err != nil {
				return err
			}
			path, err := store.DefaultPath(io.Getenv)
			if err != nil {
				return err
			}
			projects, err := store.Open(path).List(tag)
			if err != nil {
				return err
			}
			if format == cli.FormatJSON {
				if projects == nil {
					projects = []store.Project{}
				}
				return cli.WriteJSON(io.Out, projects)
			}
			t := cli.Table{Header: []string{"ID", "NAME", "OWNER", "TAGS"}}
			for _, p := range projects {
				t.Rows = append(t.Rows, []string{p.ID, p.Name, p.Owner, strings.Join(p.Tags, ",")})
			}
			return cli.WriteTable(io.Out, t)
		},
	}
}

# deployctl

Command-line client for the internal deploy service.

```
deployctl deploy web --release r42          # asks for confirmation
deployctl deploy web --release r42 --yes --wait
deployctl deploy web --release r42 --yes --json
```

Configuration comes from `~/.deployctl/config.json` (`apiUrl`, `token`) or the
`DEPLOYCTL_API` / `DEPLOYCTL_TOKEN` environment variables.

Exit codes: `0` success, `1` failure or aborted, `2` usage error.

## Development

```
npm install
npm test
```

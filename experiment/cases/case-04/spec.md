# Spec: `kit export`

**Owner:** Developer Tooling
**Requested by:** Platform ops, Finance engineering

## Goal

Teams keep copying `kit list` output into spreadsheets by hand to run ownership audits. Add an `export` command that writes the project inventory to a file in a format spreadsheets and scripts can read directly.

## Functional requirements

- **R1.** `kit export` exports every project in the local store. `--tag <tag>` limits the export to projects with that tag, with the same matching rules as `kit list --tag`.
- **R2.** `--format` accepts `json` (default) or `csv`. The JSON output is identical in shape and ordering to `kit list --format json`.
- **R3.** `--output <path>` writes the export to that file. Without `--output`, the export goes to stdout.
- **R4.** If the `--output` file already exists, the command refuses to overwrite it, prints an error containing `already exists`, and exits with code 1, unless `--force` is given.
- **R5.** CSV output has a header row `id,name,owner,tags`, one row per project ordered by id, tags joined with `;`, and standard RFC 4180 quoting for fields containing commas, quotes or newlines.
- **R6.** An unknown `--format` value is a usage error (exit code 2) and writes nothing.
- **R7.** Writing to `--output` is atomic: if the export fails part-way, no partial file is left behind and any existing file is unchanged.

## Acceptance criteria

- **AC1.** `kit export --format csv --tag infra` prints a header plus only the infra projects, ordered by id.
- **AC2.** `kit export --output out.json` with no existing `out.json` creates it with the same content `kit list --format json` prints.
- **AC3.** Running AC2 again exits 1 with an `already exists` error and leaves the file unchanged. Adding `--force` replaces it.
- **AC4.** A project named `notes, drafts` is quoted correctly in CSV.
- **AC5.** `kit export --format xml` exits 2 and creates no output file.
- **AC6.** Exporting an empty store gives `[]` for JSON and a header-only CSV.

## Non-functional constraints

- No new third-party dependencies; the standard library is enough.
- Must behave the same on Linux, macOS and Windows.
- Output files are created with mode 0644 where the OS supports it.
- Follow the existing command, exit-code and output conventions in `internal/cli`.

## Out of scope

- An `import` command.
- YAML or XLSX output.
- Exporting stores larger than fit in memory; current stores have a few hundred projects.

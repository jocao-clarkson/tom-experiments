#!/usr/bin/env node
import { parseArgs } from "node:util";
import { ApiClient } from "./api/client.js";
import { deploy } from "./commands/deploy.js";
import { loadConfig } from "./config.js";
import { CliError, UsageError } from "./errors.js";
import { Output } from "./ui/output.js";

export async function main(argv: string[], env = process.env): Promise<number> {
  const { values, positionals } = parseArgs({
    args: argv,
    allowPositionals: true,
    options: {
      json: { type: "boolean", default: false },
      yes: { type: "boolean", short: "y", default: false },
      wait: { type: "boolean", default: false },
      release: { type: "string" },
    },
  });
  const isTTY = Boolean(process.stdin.isTTY && process.stdout.isTTY);
  const out = new Output({ json: values.json!, isTTY });
  try {
    const [command, service] = positionals;
    if (!command) throw new UsageError("usage: deployctl <command> <service> [flags]");
    const cfg = loadConfig(env);
    const api = new ApiClient(cfg.apiUrl, cfg.token);
    switch (command) {
      case "deploy":
        if (!service) throw new UsageError("usage: deployctl deploy <service> --release <id>");
        return await deploy(api, out, { service, release: values.release, yes: values.yes!, wait: values.wait!, isTTY });
      default:
        throw new UsageError(`unknown command ${command}`);
    }
  } catch (err) {
    if (err instanceof CliError) {
      out.warn(`deployctl: ${err.message}`);
      return err.exitCode;
    }
    out.warn(`deployctl: unexpected error: ${String(err)}`);
    return 1;
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main(process.argv.slice(2)).then((code) => process.exit(code));
}

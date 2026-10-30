#!/usr/bin/env node
import { parseArgs } from "node:util";
import { ApiClient } from "./api/client.js";
import { loadProfile } from "./config.js";
import { CliError } from "./errors.js";
import type { OutputContext } from "./output.js";
import { statusCommand } from "./commands/status.js";
import { deployCommand } from "./commands/deploy.js";

export async function main(argv: string[]): Promise<number> {
  const { values, positionals } = parseArgs({
    args: argv,
    allowPositionals: true,
    options: {
      json: { type: "boolean", default: false },
      profile: { type: "string", default: "default" },
      yes: { type: "boolean", short: "y", default: false },
      version: { type: "string" },
    },
  });
  const [command, ...rest] = positionals;
  const out: OutputContext = { json: values.json!, stdout: process.stdout, stdin: process.stdin };
  try {
    const profile = loadProfile(values.profile);
    const api = new ApiClient(profile.apiUrl, profile.token);
    switch (command) {
      case "status":
        return await statusCommand(api, out, rest);
      case "deploy":
        return await deployCommand(api, out, rest, { version: values.version, yes: values.yes! });
      default:
        process.stderr.write(`unknown command: ${command ?? "(none)"}\n`);
        return 2;
    }
  } catch (err) {
    if (err instanceof CliError) {
      process.stderr.write(`error: ${err.message}\n`);
      return err.exitCode;
    }
    throw err;
  }
}

main(process.argv.slice(2)).then((code) => process.exit(code));

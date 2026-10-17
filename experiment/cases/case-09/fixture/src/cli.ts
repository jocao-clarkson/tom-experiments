#!/usr/bin/env node
import { Command } from "commander";
import { makeDeployCommand } from "./commands/deploy.js";
import { ApiClient } from "./lib/apiClient.js";
import { loadConfig } from "./lib/config.js";
import { setVerbose } from "./lib/log.js";
import { ExitCode } from "./lib/output.js";
import { confirm } from "./lib/prompt.js";

const program = new Command("deployer")
  .description("Deploy and manage Harborline services")
  .option("-v, --verbose", "print debug output to stderr")
  .hook("preAction", (cmd) => setVerbose(Boolean(cmd.opts().verbose)));

const deps = () => {
  const config = loadConfig();
  return { api: new ApiClient(config.apiUrl, config.token), confirm, stdout: process.stdout, stderr: process.stderr };
};

program.addCommand(makeDeployCommand(deps));

program.exitOverride((err) => {
  process.exit(err.exitCode === 0 ? ExitCode.OK : ExitCode.USAGE);
});

program.parseAsync(process.argv);

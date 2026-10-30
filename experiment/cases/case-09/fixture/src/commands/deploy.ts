import { Command } from "commander";
import type { ApiClient } from "../lib/apiClient.js";
import { ExitCode, handleAbort, printError, printResult } from "../lib/output.js";

export interface Deps {
  api: Pick<ApiClient, "get" | "post">;
  confirm: (question: string) => Promise<boolean>;
  stdout: NodeJS.WritableStream;
  stderr: NodeJS.WritableStream;
}

interface Release {
  id: string;
  service: string;
  env: string;
  version: string;
}

export function makeDeployCommand(deps: () => Deps): Command {
  return new Command("deploy")
    .argument("<service>", "service name")
    .requiredOption("--version <version>", "version to deploy")
    .option("--env <env>", "target environment", "staging")
    .option("-y, --yes", "skip confirmation")
    .option("--json", "machine-readable output")
    .action(async (service: string, opts) => {
      const d = deps();
      if (opts.env === "production" && !opts.yes) {
        const ok = await d.confirm(`Deploy ${service}@${opts.version} to production?`);
        if (!ok) {
          process.exitCode = handleAbort(d);
          return;
        }
      }
      try {
        const rel = await d.api.post<Release>(`/services/${encodeURIComponent(service)}/releases`, {
          env: opts.env,
          version: opts.version,
        });
        printResult(d, Boolean(opts.json), { releaseId: rel.id, service, env: rel.env, version: rel.version },
          `Deployed ${service}@${rel.version} to ${rel.env} (release ${rel.id})`);
        process.exitCode = ExitCode.OK;
      } catch (err) {
        printError(d, (err as Error).message);
        process.exitCode = ExitCode.FAILURE;
      }
    });
}

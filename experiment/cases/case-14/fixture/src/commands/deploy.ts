import { randomUUID } from "node:crypto";
import type { ApiClient } from "../api/client.js";
import { confirm, printResult, type OutputContext } from "../output.js";
import { UsageError } from "../errors.js";

export interface DeployFlags {
  version?: string;
  yes: boolean;
}

export async function deployCommand(api: ApiClient, out: OutputContext, args: string[], flags: DeployFlags): Promise<number> {
  const [service] = args;
  if (!service || !flags.version) throw new UsageError("usage: deployctl deploy <service> --version <v>");
  const ok = await confirm(out, `Deploy ${service}@${flags.version}?`, flags.yes);
  if (!ok) {
    out.stdout.write("aborted\n");
    return 1;
  }
  const release = await api.post<{ id: string; status: string }>(`/services/${encodeURIComponent(service)}/releases`, {
    body: { version: flags.version },
    idempotencyKey: randomUUID(),
  });
  printResult(out, { service, release: release.id, status: release.status });
  return 0;
}

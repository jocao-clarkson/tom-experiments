import type { ApiClient } from "../api/client.js";
import type { OutputContext } from "../output.js";
import { printResult } from "../output.js";
import { UsageError } from "../errors.js";

export interface Release {
  id: string;
  version: string;
  status: "pending" | "running" | "succeeded" | "failed" | "rolled_back";
  createdAt: string;
}

export async function statusCommand(api: ApiClient, out: OutputContext, args: string[]): Promise<number> {
  const [service] = args;
  if (!service) throw new UsageError("usage: deployctl status <service>");
  const releases = await api.get<Release[]>(`/services/${encodeURIComponent(service)}/releases?limit=5`);
  printResult(
    out,
    { service, releases },
    releases.map((r) => [r.id, r.version, r.status, r.createdAt]),
  );
  return 0;
}

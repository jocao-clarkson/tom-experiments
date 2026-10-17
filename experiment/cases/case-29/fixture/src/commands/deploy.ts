import type { ApiClient } from "../api/client.js";
import { CliError, UsageError } from "../errors.js";
import type { Output } from "../ui/output.js";
import { confirm } from "../ui/prompt.js";

export interface DeployArgs {
  service: string;
  release?: string;
  yes: boolean;
  wait: boolean;
  isTTY: boolean;
}

interface Deploy {
  id: string;
  state: "pending" | "running" | "succeeded" | "failed";
}

const POLL_MS = 5_000;
const WAIT_LIMIT_MS = 15 * 60_000;

export async function deploy(api: ApiClient, out: Output, args: DeployArgs, sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))): Promise<number> {
  if (!args.release) throw new UsageError("--release is required");
  await confirm(`Deploy ${args.release} to ${args.service}?`, { yes: args.yes, isTTY: args.isTTY });

  const created = await api.request<Deploy>("POST", `/services/${encodeURIComponent(args.service)}/deploys`, {
    release: args.release,
  });
  out.line(`Started deploy ${created.id}`);
  if (!args.wait) {
    out.result({ id: created.id, state: created.state }, `deploy ${created.id} ${created.state}`);
    return 0;
  }

  const deadline = Date.now() + WAIT_LIMIT_MS;
  let last = created.state;
  while (Date.now() < deadline) {
    const d = await api.request<Deploy>("GET", `/deploys/${created.id}`);
    if (d.state !== last) {
      out.line(`  ${d.state}`);
      last = d.state;
    }
    if (d.state === "succeeded" || d.state === "failed") {
      out.result({ id: d.id, state: d.state }, `deploy ${d.id} ${d.state}`);
      return d.state === "succeeded" ? 0 : 1;
    }
    await sleep(POLL_MS);
  }
  throw new CliError(`gave up waiting for deploy ${created.id}`, 1);
}

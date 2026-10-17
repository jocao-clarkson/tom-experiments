import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { UsageError } from "./errors.js";

export interface Config {
  apiUrl: string;
  token: string;
}

export function loadConfig(env = process.env): Config {
  let file: Partial<Config> = {};
  try {
    file = JSON.parse(readFileSync(join(homedir(), ".deployctl", "config.json"), "utf8"));
  } catch {
    // no config file is fine if env vars are set
  }
  const apiUrl = env.DEPLOYCTL_API ?? file.apiUrl ?? "https://deploy.internal";
  const token = env.DEPLOYCTL_TOKEN ?? file.token;
  if (!token) throw new UsageError("no API token: run `deployctl login` or set DEPLOYCTL_TOKEN");
  return { apiUrl, token };
}

import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { UsageError } from "./errors.js";

export interface Profile {
  apiUrl: string;
  token: string;
}

export function loadProfile(name = "default"): Profile {
  const path = process.env.DEPLOYCTL_CONFIG ?? join(homedir(), ".deployctl", "config.json");
  let file: Record<string, Partial<Profile>> = {};
  try {
    file = JSON.parse(readFileSync(path, "utf8"));
  } catch {
    // A missing config file is fine when everything comes from the environment.
  }
  const p = file[name] ?? {};
  const apiUrl = process.env.DEPLOYCTL_API_URL ?? p.apiUrl;
  const token = process.env.DEPLOYCTL_TOKEN ?? p.token;
  if (!apiUrl || !token) {
    throw new UsageError(`profile "${name}" is missing apiUrl or token; run "deployctl login"`);
  }
  return { apiUrl, token };
}

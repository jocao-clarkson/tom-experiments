import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

export interface Config {
  apiUrl: string;
  token: string;
}

/**
 * Precedence: environment (DEPLOYER_API_URL, DEPLOYER_TOKEN) over
 * ~/.deployerrc (JSON). CI should use the environment variables.
 */
export function loadConfig(env = process.env, rcPath = join(homedir(), ".deployerrc")): Config {
  let file: Partial<Config> = {};
  try {
    file = JSON.parse(readFileSync(rcPath, "utf8"));
  } catch {
    // missing or unreadable rc file is fine if env provides everything
  }
  const apiUrl = env.DEPLOYER_API_URL ?? file.apiUrl ?? "https://deploy.harborline.dev";
  const token = env.DEPLOYER_TOKEN ?? file.token;
  if (!token) {
    throw new Error("No API token found. Set DEPLOYER_TOKEN or run `deployer login`.");
  }
  return { apiUrl, token };
}

export interface AppConfig {
  port: number;
  databaseUrl: string;
  publicBaseUrl: string;
  mailEndpoint: string;
  mailApiKey: string;
  mailFrom: string;
  passwordMinLength: number;
  linkTtlMinutes: number;
  jobPollMs: number;
}

function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable ${name}`);
  }
  return value;
}

export function loadConfig(): AppConfig {
  return {
    port: Number(process.env.PORT ?? 8080),
    databaseUrl: required("DATABASE_URL"),
    publicBaseUrl: required("PUBLIC_BASE_URL"),
    mailEndpoint: required("MAIL_ENDPOINT"),
    mailApiKey: required("MAIL_API_KEY"),
    mailFrom: process.env.MAIL_FROM ?? "no-reply@example.com",
    passwordMinLength: Number(process.env.PASSWORD_MIN_LENGTH ?? 12),
    linkTtlMinutes: Number(process.env.LINK_TTL_MINUTES ?? 24 * 60),
    jobPollMs: Number(process.env.JOB_POLL_MS ?? 1000),
  };
}

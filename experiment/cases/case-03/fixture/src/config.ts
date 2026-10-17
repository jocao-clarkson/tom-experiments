export interface AppConfig {
  databaseUrl: string;
  publicBaseUrl: string;
  mailFrom: string;
  passwordMinLength: number;
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
    databaseUrl: required("DATABASE_URL"),
    publicBaseUrl: required("PUBLIC_BASE_URL"),
    mailFrom: process.env.MAIL_FROM ?? "no-reply@example.com",
    passwordMinLength: Number(process.env.PASSWORD_MIN_LENGTH ?? 12),
  };
}

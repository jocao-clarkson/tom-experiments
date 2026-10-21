export interface Config {
  databaseUrl: string;
  http: { timeoutMs: number };
  push: { gatewayUrl: string; apiKey: string };
  shipping: { trackingApiUrl: string; apiKey: string };
}

function required(env: NodeJS.ProcessEnv, name: string): string {
  const v = env[name];
  if (!v) throw new Error(`missing required env var ${name}`);
  return v;
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config {
  return {
    databaseUrl: required(env, "DATABASE_URL"),
    http: { timeoutMs: Number(env.HTTP_TIMEOUT_MS ?? 20000) },
    push: {
      gatewayUrl: required(env, "PUSH_GATEWAY_URL"),
      apiKey: required(env, "PUSH_API_KEY"),
    },
    shipping: {
      trackingApiUrl: required(env, "SHIPPING_TRACKING_URL"),
      apiKey: required(env, "SHIPPING_API_KEY"),
    },
  };
}

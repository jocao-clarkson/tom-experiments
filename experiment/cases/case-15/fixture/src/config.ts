const num = (raw: string | undefined, fallback: number) => (raw === undefined || raw === "" ? fallback : Number(raw));

export const config = {
  db: {
    url: process.env.DATABASE_URL,
    poolSize: num(process.env.DB_POOL_SIZE, 20),
    statementTimeoutMs: num(process.env.DB_STATEMENT_TIMEOUT_MS, 2000),
  },
  paging: {
    defaultLimit: num(process.env.PAGE_DEFAULT_LIMIT, 20),
    maxLimit: num(process.env.PAGE_MAX_LIMIT, 100),
  },
  auth: {
    jwtPublicKey: process.env.JWT_PUBLIC_KEY ?? "",
  },
};

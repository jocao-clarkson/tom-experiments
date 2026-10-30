import { createCipheriv, createDecipheriv, createHash, randomBytes, timingSafeEqual } from "crypto";

const ENC_KEY = Buffer.from(process.env.KEYS_ENCRYPTION_KEY ?? "", "base64");

/** Returns a new API key secret: "rk_" + 32 random bytes, base64url. */
export function randomSecret(): string {
  return "rk_" + randomBytes(32).toString("base64url");
}

export function hashSecret(secret: string): string {
  return createHash("sha256").update(secret).digest("hex");
}

export function constantTimeEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a);
  const bb = Buffer.from(b);
  return ab.length === bb.length && timingSafeEqual(ab, bb);
}

/** AES-256-GCM with the service key. Used for webhook signing secrets at rest. */
export function encrypt(plaintext: string): string {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", ENC_KEY, iv);
  const body = Buffer.concat([cipher.update(plaintext, "utf8"), cipher.final()]);
  return [iv, cipher.getAuthTag(), body].map((b) => b.toString("base64url")).join(".");
}

export function decrypt(token: string): string {
  const [iv, tag, body] = token.split(".").map((p) => Buffer.from(p, "base64url"));
  const decipher = createDecipheriv("aes-256-gcm", ENC_KEY, iv);
  decipher.setAuthTag(tag);
  return Buffer.concat([decipher.update(body), decipher.final()]).toString("utf8");
}

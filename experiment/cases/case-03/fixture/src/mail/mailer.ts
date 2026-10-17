export type Template = "verify_email" | "email_changed";

export interface Mailer {
  send(template: Template, to: string, vars: Record<string, string>): Promise<void>;
}

/** Sends through the transactional mail provider's HTTP API. */
export class HttpMailer implements Mailer {
  constructor(
    private readonly endpoint: string,
    private readonly apiKey: string,
    private readonly from: string,
  ) {}

  async send(template: Template, to: string, vars: Record<string, string>): Promise<void> {
    const res = await fetch(this.endpoint, {
      method: "POST",
      headers: { authorization: `Bearer ${this.apiKey}`, "content-type": "application/json" },
      body: JSON.stringify({ from: this.from, to, template, vars }),
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) {
      throw new Error(`mail provider returned ${res.status}`);
    }
  }
}

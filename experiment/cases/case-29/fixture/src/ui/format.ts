/** Serialise a result document for --json output. */
export function formatJson(data: unknown): string {
  return JSON.stringify(data, null, 2);
}

/** Message for anything thrown by fetch, wagmi or our own API layer. */
export function errorMessage(err: unknown, fallback = "Something went wrong"): string {
  if (err instanceof Error) return err.message || fallback;
  if (typeof err === "string" && err) return err;
  return fallback;
}

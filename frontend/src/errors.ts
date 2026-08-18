/** Error reporting for failures the UI degrades past instead of showing.
 *
 * A background fetch that fails is allowed to leave a partial UI, but it must
 * never disappear without a trace — every such catch reports here.
 */
export function reportError(context: string, error: unknown): void {
  console.error(`[SoundHub] ${context}:`, error);
}

export function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

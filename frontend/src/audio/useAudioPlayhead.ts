import { useEffect, useRef, type RefObject } from "react";

export interface LoopRegion {
  start: number;
  end: number;
}

/**
 * Track an `<audio>` element's playhead on every animation frame and restart
 * the loop region when it runs past `loop.end`.
 */
export function useAudioPlayhead(
  audioRef: RefObject<HTMLAudioElement | null>,
  loop: LoopRegion | null,
  onPosition: (t: number) => void
): void {
  const onPositionRef = useRef(onPosition);
  onPositionRef.current = onPosition;

  useEffect(() => {
    let raf: number | null = null;
    const tick = () => {
      const a = audioRef.current;
      if (a) {
        onPositionRef.current(a.currentTime);
        if (loop && a.currentTime >= loop.end) {
          a.currentTime = loop.start;
          a.play().catch(() => undefined);
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      if (raf) cancelAnimationFrame(raf);
    };
  }, [audioRef, loop]);
}

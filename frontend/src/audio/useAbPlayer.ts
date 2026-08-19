import { useCallback, useEffect, useRef, useState } from "react";
import { decodeAudio, newAudioContext } from "./sources";
import { errorMessage } from "../errors";

const CROSSFADE_MS = 40;
// Lookahead scheduling window (seconds) — segments are scheduled on the
// AudioContext clock well before they start, so loop boundaries are exact and
// gapless (the pattern from Ableton's web-audio-sequencing: schedule ahead on
// the audio clock, never restart on a rAF frame).
const SCHED_LOOKAHEAD_S = 0.15;
const SCHED_MAX_ITER = 64;

export type Side = "a" | "b";

/** Both sides of a comparison, keyed by side. */
export interface Pair<T> {
  a: T;
  b: T;
}

interface Segment {
  a: AudioBufferSourceNode;
  b: AudioBufferSourceNode;
  startCtx: number;
  endCtx: number;
}

export interface AbPlayerOptions {
  /** Resolve the two audio URLs to decode. Re-run whenever `reloadKey` changes. */
  resolveUrls: () => Promise<Pair<string>>;
  /** Reloads the buffers when it changes (comparison id, mode, …). */
  reloadKey: unknown;
  /** Loop region start, in milliseconds. */
  startMs: number;
  /** Loop region end; defaults to `startMs + 20 s`. */
  endMs?: number | null;
  /** Linear playback gain per side (level match); defaults to unity. */
  levels?: Pair<number>;
  /** Message shown when loading or decoding fails. */
  loadErrorFallback?: string;
}

export interface AbPlayer {
  buffers: Pair<AudioBuffer | null>;
  loading: boolean;
  error: string | null;
  setError: (msg: string | null) => void;
  playing: boolean;
  active: Side;
  /** Playhead position and total duration, in seconds. */
  position: number;
  duration: number;
  loop: { start: number; end: number } | null;
  /** Start playing, or pause and keep the playhead where it is. */
  toggle: () => void;
  /** Crossfade to the other side without moving the playhead. */
  switchSide: (side: Side) => void;
  /** Master trim in dB, applied to the preview graph only. */
  setMasterGainDb: (db: number) => void;
}

/**
 * Two-source A/B player driving one Web Audio graph.
 *
 * Both sides are decoded to AudioBuffers and started at the SAME offset, so
 * toggling sides never resets the playhead — switching only crossfades the
 * gains (40 ms). Per-side `levels` are applied ONLY to this preview graph, so
 * the source files are untouched.
 *
 * Playback uses lookahead scheduling: while playing, the RAF tick fills a
 * small horizon with BufferSource segments (`start(when)` / `stop(when)` at
 * exact AudioContext times), so the loop region loops gapless — no stop/start
 * gap at the boundary and no frame-quantized restart.
 */
export function useAbPlayer({
  resolveUrls,
  reloadKey,
  startMs,
  endMs,
  levels,
  loadErrorFallback = "Failed to load audio",
}: AbPlayerOptions): AbPlayer {
  const [buffers, setBuffers] = useState<Pair<AudioBuffer | null>>({ a: null, b: null });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [active, setActive] = useState<Side>("a");
  const [position, setPosition] = useState(0);
  const [duration, setDuration] = useState(0);

  const ctxRef = useRef<AudioContext | null>(null);
  const gainNodesRef = useRef<Pair<GainNode> | null>(null);
  const masterRef = useRef<GainNode | null>(null);
  const masterGainRef = useRef(1);
  const offsetRef = useRef(0);
  const livePosRef = useRef<number | null>(null);
  const playingRef = useRef(false);
  const rafRef = useRef<number | null>(null);
  const loopRef = useRef<{ start: number; end: number } | null>(null);
  // Mirror of `buffers` state so the scheduler (a stable callback reading refs
  // only) always sees the current buffers without re-creating itself.
  const buffersRef = useRef<Pair<AudioBuffer | null>>({ a: null, b: null });
  // Scheduled playback segments: each plays a slice of the loop region at
  // exact AudioContext times. `nextStartCtxRef` is the ctx time when the NEXT
  // segment should begin; `nextOffsetRef` is its buffer offset.
  const segmentsRef = useRef<Segment[]>([]);
  const nextStartCtxRef = useRef<number | null>(null);
  const nextOffsetRef = useRef(0);

  const levelsRef = useRef<Pair<number>>(levels ?? { a: 1, b: 1 });
  levelsRef.current = levels ?? { a: 1, b: 1 };
  const resolveRef = useRef(resolveUrls);
  resolveRef.current = resolveUrls;

  const stopAllSegments = useCallback(() => {
    for (const seg of segmentsRef.current) {
      try {
        seg.a.stop();
        seg.b.stop();
      } catch {
        /* already stopped */
      }
    }
    segmentsRef.current = [];
  }, []);

  const loopEnd = (endMs ?? startMs + 20000) / 1000;

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const urls = await resolveRef.current();
        if (cancelled) return;
        const ctx = ctxRef.current ?? newAudioContext();
        ctxRef.current = ctx;
        const [a, b] = await Promise.all([decodeAudio(ctx, urls.a), decodeAudio(ctx, urls.b)]);
        if (cancelled) return;
        setBuffers({ a, b });
        buffersRef.current = { a, b };
        const dur = Math.min(a.duration, b.duration);
        setDuration(dur);
        const start = Math.min(startMs / 1000, Math.max(0, dur - 0.05));
        setPosition(start);
        offsetRef.current = start;
        loopRef.current = { start, end: Math.min(loopEnd, dur) };
        playingRef.current = false;
        setPlaying(false);
        stopAllSegments();
        nextStartCtxRef.current = null;
      } catch (e) {
        setError(errorMessage(e, loadErrorFallback));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadKey]);

  useEffect(() => {
    return () => {
      ctxRef.current?.close().catch(() => undefined);
    };
  }, []);

  // Build the shared gain graph once per context. Sources are created by the
  // scheduler on demand — there is no long-lived source pair to restart at the
  // loop boundary.
  const buildGraph = useCallback(() => {
    const ctx = ctxRef.current;
    if (!ctx || gainNodesRef.current) return;
    const a = ctx.createGain();
    const b = ctx.createGain();
    const master = ctx.createGain();
    a.connect(master).connect(ctx.destination);
    b.connect(master).connect(ctx.destination);
    a.gain.value = 0;
    b.gain.value = 0;
    master.gain.value = masterGainRef.current;
    gainNodesRef.current = { a, b };
    masterRef.current = master;
  }, []);

  // Lookahead scheduler: fill the horizon with segments starting at exact
  // AudioContext times. Each segment plays `loop.end - loop.start` (or the
  // remainder when looping is off), so the next one can be scheduled while the
  // current is still playing — the boundary is gapless.
  const schedule = useCallback(() => {
    const ctx = ctxRef.current;
    const { a, b } = buffersRef.current;
    const g = gainNodesRef.current;
    if (!ctx || !a || !b || !g) return;
    const lp = loopRef.current;
    const horizon = ctx.currentTime + SCHED_LOOKAHEAD_S;
    let next = nextStartCtxRef.current;
    let offset = nextOffsetRef.current;
    if (next == null) return;
    // Drop finished segments (they self-stop at their scheduled endCtx).
    const now = ctx.currentTime;
    segmentsRef.current = segmentsRef.current.filter((s) => s.endCtx > now);
    let iterations = 0;
    while (next < horizon && iterations < SCHED_MAX_ITER) {
      const start = Math.max(next, now + 0.01);
      const len = lp ? lp.end - lp.start : Math.max(0, Math.min(a.duration, b.duration) - offset);
      if (len <= 0.0005) break;
      const end = start + len;
      const aSrc = ctx.createBufferSource();
      aSrc.buffer = a;
      const bSrc = ctx.createBufferSource();
      bSrc.buffer = b;
      aSrc.connect(g.a);
      bSrc.connect(g.b);
      aSrc.start(start, offset);
      bSrc.start(start, offset);
      aSrc.stop(end);
      bSrc.stop(end);
      segmentsRef.current.push({ a: aSrc, b: bSrc, startCtx: start, endCtx: end });
      next = end;
      offset = lp ? lp.start : offset + len;
      iterations += 1;
    }
    nextStartCtxRef.current = next;
    nextOffsetRef.current = offset;
  }, []);

  const applyGains = useCallback((side: Side) => {
    const g = gainNodesRef.current;
    if (!g) return;
    const now = ctxRef.current?.currentTime ?? 0;
    const ramp = CROSSFADE_MS / 1000;
    const lv = levelsRef.current;
    for (const key of ["a", "b"] as const) {
      const target = side === key ? lv[key] : 0;
      const param = g[key].gain;
      param.cancelScheduledValues(now);
      param.setValueAtTime(param.value, now);
      param.linearRampToValueAtTime(target, now + ramp);
    }
  }, []);

  const toggle = useCallback(() => {
    if (playingRef.current) {
      if (livePosRef.current != null) offsetRef.current = livePosRef.current;
      stopAllSegments();
      nextStartCtxRef.current = null;
      playingRef.current = false;
      setPlaying(false);
      return;
    }
    const ctx = ctxRef.current;
    if (!ctx) return;
    buildGraph();
    if (nextStartCtxRef.current == null) {
      nextStartCtxRef.current = ctx.currentTime + 0.02;
      nextOffsetRef.current = offsetRef.current;
    }
    void ctx.resume().then(() => {
      applyGains(active);
      playingRef.current = true;
      setPlaying(true);
      schedule();
    });
  }, [active, applyGains, buildGraph, schedule, stopAllSegments]);

  const switchSide = useCallback(
    (side: Side) => {
      setActive(side);
      if (playingRef.current) applyGains(side);
    },
    [applyGains]
  );

  const setMasterGainDb = useCallback((db: number) => {
    masterGainRef.current = 10 ** (db / 20);
    if (masterRef.current) masterRef.current.gain.value = masterGainRef.current;
  }, []);

  // playhead tick + lookahead scheduling
  useEffect(() => {
    const tick = () => {
      const ctx = ctxRef.current;
      if (ctx && playingRef.current) {
        schedule();
        // Position from the most recent scheduled segment: the segment's
        // buffer offset + elapsed audio-clock time since it started.
        const now = ctx.currentTime;
        const segs = segmentsRef.current;
        if (segs.length > 0) {
          const seg = segs.find((s) => s.startCtx <= now && s.endCtx > now) ?? segs[segs.length - 1];
          const lp = loopRef.current;
          const pos = (lp ? lp.start : offsetRef.current) + (now - seg.startCtx);
          const clamped = Math.min(pos, duration || pos);
          setPosition(clamped);
          livePosRef.current = clamped;
        }
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [duration, schedule]);

  return {
    buffers,
    loading,
    error,
    setError,
    playing,
    active,
    position,
    duration,
    loop: loopRef.current,
    toggle,
    switchSide,
    setMasterGainDb,
  };
}

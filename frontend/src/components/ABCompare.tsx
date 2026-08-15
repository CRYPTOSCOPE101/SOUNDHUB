import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { fmtClock } from "./ReviewShared";
import { STEM_LOGICAL_NAMES, type StemAsset, type VersionComparison } from "../types";

const CROSSFADE_MS = 40;
// Lookahead scheduling window (seconds) — segments are scheduled on the
// AudioContext clock well before they start, so loop boundaries are exact
// and gapless (the pattern from Ableton's web-audio-sequencing: schedule
// ahead on the audio clock, never restart on a rAF frame).
const SCHED_LOOKAHEAD_S = 0.15;
const SCHED_MAX_ITER = 64;

/**
 * A/B comparison player.
 *
 * Both versions are decoded to AudioBuffers and started at the SAME offset,
 * so A/B toggling never resets the playhead. Switching crossfades the gains
 * (40 ms). Level-matched gains from the comparison are applied ONLY to the
 * preview graph — source files and the release package are untouched.
 *
 * Playback uses lookahead scheduling: while playing, the RAF tick asks the
 * scheduler to fill a small horizon of BufferSource segments (`start(when)` /
 * `stop(when)` at exact AudioContext times). The loop region therefore loops
 * gapless — no stop/start gap at the boundary, no frame-quantized restart.
 *
 * Modes: `full_mix` compares the whole bounce; `stem` compares one submix
 * (drums / bass / vocal / synths) matched by logical name across both
 * versions. Stems appear in the picker only when present in BOTH versions.
 */
export default function ABCompare({
  sessionId,
  comparison,
  onClose,
  audioUrls,
}: {
  sessionId: number;
  comparison: VersionComparison;
  onClose: () => void;
  /** Pre-resolved public URLs (guest share link) — skips the owner fetch. */
  audioUrls?: { base: string; compare: string };
}) {
  const [comp, setComp] = useState<VersionComparison>(comparison);
  const [buffers, setBuffers] = useState<{ base: AudioBuffer | null; compare: AudioBuffer | null }>({
    base: null,
    compare: null,
  });
  const [stems, setStems] = useState<{ base: StemAsset[]; compare: StemAsset[] }>({ base: [], compare: [] });
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [active, setActive] = useState<"base" | "compare">("base");
  const [position, setPosition] = useState(0);
  const [duration, setDuration] = useState(0);
  const [gain, setGain] = useState(0);
  const [manual, setManual] = useState(false);
  const ctxRef = useRef<AudioContext | null>(null);
  const gainNodesRef = useRef<{ base: GainNode; compare: GainNode } | null>(null);
  const masterRef = useRef<GainNode | null>(null);
  const offsetRef = useRef(0);
  const livePosRef = useRef<number | null>(null);
  const playingRef = useRef(false);
  const rafRef = useRef<number | null>(null);
  const loopRef = useRef<{ start: number; end: number } | null>(null);
  const compRef = useRef(comp);
  compRef.current = comp;
  // Mirror of `buffers` state so the scheduler (a stable callback reading
  // refs only) always sees the current buffers without re-creating itself.
  const buffersRef = useRef<{ base: AudioBuffer | null; compare: AudioBuffer | null }>({
    base: null,
    compare: null,
  });
  // Scheduled playback segments: each plays a slice of the loop region at
  // exact AudioContext times. `nextStartCtxRef` is the ctx time when the
  // NEXT segment should begin; `nextOffsetRef` is its buffer offset.
  interface Segment {
    base: AudioBufferSourceNode;
    compare: AudioBufferSourceNode;
    startCtx: number;
    endCtx: number;
  }
  const segmentsRef = useRef<Segment[]>([]);
  const nextStartCtxRef = useRef<number | null>(null);
  const nextOffsetRef = useRef(0);

  const endMs = (comp.end_ms ?? comp.start_ms + 20000) / 1000;

  // load stems for both versions (for the picker)
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [b, c] = await Promise.all([
          api.listStems(comp.base_version_id),
          api.listStems(comp.compare_version_id),
        ]);
        if (cancelled) return;
        setStems({ base: b, compare: c });
      } catch {
        /* stems are optional — full mix still works */
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [comp.base_version_id, comp.compare_version_id]);

  // stems available in BOTH versions (matched by logical name)
  const sharedStems = STEM_LOGICAL_NAMES.filter(
    (name) => stems.base.some((s) => s.logical_name === name) && stems.compare.some((s) => s.logical_name === name)
  );

  // load both buffers for the current comparison mode
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setErr(null);
      try {
        let baseUrl: string;
        let compareUrl: string;
        if (comp.mode === "stem" && comp.stem_logical_name) {
          const bStem = stems.base.find((s) => s.logical_name === comp.stem_logical_name);
          const cStem = stems.compare.find((s) => s.logical_name === comp.stem_logical_name);
          if (!bStem || !cStem) throw new Error(`Stem “${comp.stem_logical_name}” is unavailable in one of the versions`);
          baseUrl = await fetchAudioBlob(api.stemAudioUrl(comp.base_version_id, bStem.id));
          compareUrl = await fetchAudioBlob(api.stemAudioUrl(comp.compare_version_id, cStem.id));
        } else if (audioUrls) {
          baseUrl = audioUrls.base;
          compareUrl = audioUrls.compare;
        } else {
          baseUrl = await fetchAudioBlob(api.versionAudioUrl(sessionId, comp.base_version_id));
          compareUrl = await fetchAudioBlob(api.versionAudioUrl(sessionId, comp.compare_version_id));
        }
        if (cancelled) return;
        const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        const ctx = ctxRef.current ?? new Ctx();
        ctxRef.current = ctx;
        const [b, c] = await Promise.all([decodeAudio(ctx, baseUrl), decodeAudio(ctx, compareUrl)]);
        if (cancelled) return;
        setBuffers({ base: b, compare: c });
        buffersRef.current = { base: b, compare: c };
        const dur = Math.min(b.duration, c.duration);
        setDuration(dur);
        const start = Math.min(comp.start_ms / 1000, Math.max(0, dur - 0.05));
        setPosition(start);
        offsetRef.current = start;
        loopRef.current = {
          start: Math.min(comp.start_ms / 1000, Math.max(0, dur - 0.05)),
          end: Math.min(endMs, dur),
        };
        playingRef.current = false;
        setPlaying(false);
        stopAllSegments();
        nextStartCtxRef.current = null;
      } catch (e) {
        setErr(e instanceof Error ? e.message : "Failed to load audio");
      } finally {
        setLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [comp, stems.base, stems.compare, sessionId]);

  useEffect(() => {
    return () => {
      ctxRef.current?.close().catch(() => undefined);
    };
  }, []);

  // Build the shared gain graph once per buffer load. Sources are created by
  // the scheduler on demand — there is no single long-lived source pair to
  // restart at the loop boundary.
  const buildGraph = useCallback(() => {
    const ctx = ctxRef.current;
    if (!ctx) return;
    if (gainNodesRef.current) return;
    const gBase = ctx.createGain();
    const gCompare = ctx.createGain();
    const master = ctx.createGain();
    gBase.connect(master).connect(ctx.destination);
    gCompare.connect(master).connect(ctx.destination);
    gainNodesRef.current = { base: gBase, compare: gCompare };
    masterRef.current = master;
    gBase.gain.value = 0;
    gCompare.gain.value = 0;
  }, []);

  const stopAllSegments = useCallback(() => {
    for (const seg of segmentsRef.current) {
      try {
        seg.base.stop();
        seg.compare.stop();
      } catch {
        /* already stopped */
      }
    }
    segmentsRef.current = [];
  }, []);

  // Lookahead scheduler: fill the horizon with segments starting at exact
  // AudioContext times. Each segment plays `loop.end - loop.start` (or the
  // remainder when looping is off), so the next one can be scheduled while
  // the current is still playing — the boundary is gapless.
  const schedule = useCallback(() => {
    const ctx = ctxRef.current;
    const b = buffersRef.current.base;
    const c = buffersRef.current.compare;
    if (!ctx || !b || !c || !gainNodesRef.current) return;
    const g = gainNodesRef.current;
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
      const len = lp ? lp.end - lp.start : Math.max(0, Math.min(b.duration, c.duration) - offset);
      if (len <= 0.0005) break;
      const end = start + len;
      const baseSrc = ctx.createBufferSource();
      baseSrc.buffer = b;
      const compareSrc = ctx.createBufferSource();
      compareSrc.buffer = c;
      baseSrc.connect(g.base);
      compareSrc.connect(g.compare);
      baseSrc.start(start, offset);
      compareSrc.start(start, offset);
      baseSrc.stop(end);
      compareSrc.stop(end);
      segmentsRef.current.push({ base: baseSrc, compare: compareSrc, startCtx: start, endCtx: end });
      next = end;
      offset = lp ? lp.start : offset + len;
      iterations += 1;
    }
    nextStartCtxRef.current = next;
    nextOffsetRef.current = offset;
  }, []);

  const applyGains = useCallback((side: "base" | "compare") => {
    const g = gainNodesRef.current;
    if (!g) return;
    const baseGain = side === "base" ? 1 : 0;
    const compareGain = side === "compare" ? 1 : 0;
    const now = ctxRef.current?.currentTime ?? 0;
    const ramp = CROSSFADE_MS / 1000;
    g.base.gain.cancelScheduledValues(now);
    g.compare.gain.cancelScheduledValues(now);
    g.base.gain.setValueAtTime(g.base.gain.value, now);
    g.compare.gain.setValueAtTime(g.compare.gain.value, now);
    g.base.gain.linearRampToValueAtTime(baseGain, now + ramp);
    g.compare.gain.linearRampToValueAtTime(compareGain, now + ramp);
  }, []);

  const toggle = () => {
    if (playing) {
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
  };

  const switchSide = (side: "base" | "compare") => {
    setActive(side);
    if (playingRef.current) applyGains(side);
  };

  // playhead tick + lookahead scheduling
  useEffect(() => {
    const tick = () => {
      const ctx = ctxRef.current;
      if (ctx && playingRef.current) {
        schedule();
        const lp = loopRef.current;
        // Position from the most recent scheduled segment: the segment's
        // buffer offset + elapsed audio-clock time since it started.
        let pos: number | null = null;
        const now = ctx.currentTime;
        const segs = segmentsRef.current;
        if (segs.length > 0 && lp) {
          const activeSeg = segs.find((s) => s.startCtx <= now && s.endCtx > now) ?? segs[segs.length - 1];
          pos = lp.start + (now - activeSeg.startCtx);
        } else if (segs.length > 0) {
          const activeSeg = segs.find((s) => s.startCtx <= now && s.endCtx > now) ?? segs[segs.length - 1];
          pos = offsetRef.current + (now - activeSeg.startCtx);
        }
        if (pos != null) {
          setPosition(Math.min(pos, duration || pos));
          livePosRef.current = Math.min(pos, duration || pos);
        }
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [duration]);

  const play = () => {
    toggle();
  };

  const switchMode = async (mode: string, stemName?: string) => {
    setLoading(true);
    setErr(null);
    try {
      const c = await api.createComparison({
        baseVersionId: comp.base_version_id,
        compareVersionId: comp.compare_version_id,
        requestId: comp.request_id,
        startMs: comp.start_ms,
        endMs: comp.end_ms,
        levelMatch: comp.level_match === "none" ? "short_term_lufs" : comp.level_match,
        mode,
        stemLogicalName: mode === "stem" ? stemName ?? null : null,
      });
      setComp(c);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to switch mode");
    } finally {
      setLoading(false);
    }
  };

  const stemLabel = (name: string) => {
    const s = stems.base.find((x) => x.logical_name === name);
    return s?.display_name || name;
  };

  const levelLabel = comp.level_match === "none"
    ? "Level match unavailable"
    : comp.base_gain_db
      ? `Level matched · ${comp.base_label} ${comp.base_gain_db >= 0 ? "+" : ""}${comp.base_gain_db.toFixed(1)} dB`
      : comp.compare_gain_db
        ? `Level matched · ${comp.compare_label} ${comp.compare_gain_db >= 0 ? "+" : ""}${comp.compare_gain_db.toFixed(1)} dB`
        : "Level matched · equal loudness";

  const pct = duration > 0 ? (position / duration) * 100 : 0;
  const loopStartPct = duration > 0 ? ((loopRef.current?.start ?? 0) / duration) * 100 : 0;
  const loopEndPct = duration > 0 ? ((loopRef.current?.end ?? duration) / duration) * 100 : 100;

  return (
    <div className="ab-panel">
      <div className="ab-head">
        <span className="ab-title">
          COMPARE {comp.base_label} ↔ {comp.compare_label}
          {comp.mode === "stem" && comp.stem_logical_name && (
            <span className="ab-mode-chip">· {stemLabel(comp.stem_logical_name)}</span>
          )}
        </span>
        {comp.request_id != null && <span className="ab-request">request #{comp.request_id}</span>}
        <button type="button" className="rs-btn ghost sm" onClick={onClose}>
          ✕
        </button>
      </div>

      {/* mode picker: full mix + stems available in BOTH versions */}
      <div className="ab-modes">
        <button
          type="button"
          className={`ab-mode ${comp.mode === "full_mix" ? "active" : ""}`}
          onClick={() => void switchMode("full_mix")}
          disabled={loading}
        >
          Full mix
        </button>
        {sharedStems.map((name) => (
          <button
            key={name}
            type="button"
            className={`ab-mode ${comp.mode === "stem" && comp.stem_logical_name === name ? "active" : ""}`}
            onClick={() => void switchMode("stem", name)}
            disabled={loading}
          >
            {stemLabel(name)}
          </button>
        ))}
      </div>

      <div className="ab-sidebar">
        <button type="button" className={`ab-side ${active === "base" ? "active" : ""}`} onClick={() => switchSide("base")}>
          <strong>{comp.base_label}</strong>
          {comp.short_term_lufs[comp.base_label] != null && (
            <span>{comp.short_term_lufs[comp.base_label]} LUFS</span>
          )}
        </button>
        <button type="button" className={`ab-side ${active === "compare" ? "active" : ""}`} onClick={() => switchSide("compare")}>
          <strong>{comp.compare_label}</strong>
          {comp.short_term_lufs[comp.compare_label] != null && (
            <span>{comp.short_term_lufs[comp.compare_label]} LUFS</span>
          )}
        </button>
      </div>

      <div className="ab-body">
        <div className="ab-wave">
          <div className="ab-loop" style={{ left: `${loopStartPct}%`, width: `${Math.max(0, loopEndPct - loopStartPct)}%` }} />
          <div className="ab-playhead" style={{ left: `${pct}%` }} />
          <span className="ab-time">{fmtClock(position)}</span>
          <span className="ab-time right">{fmtClock(duration)}</span>
        </div>

        <div className="ab-controls">
          <button type="button" className="rs-play ab-play" onClick={play} disabled={loading || !buffers.base}>
            {playing ? "❚❚" : "▶"}
          </button>
          <span className="ab-label">
            {levelLabel}
            {comp.level_match !== "none" && " · loop: ON"}
          </span>
          <button
            type="button"
            className="ab-gain-toggle"
            onClick={() => setManual((m) => !m)}
            title="Manual gain override"
          >
            {manual ? "Manual gain" : "Auto level match"}
          </button>
          {manual && (
            <input
              type="range"
              min={-12}
              max={12}
              step={0.5}
              value={gain}
              onChange={(e) => {
                const g = Number(e.target.value);
                setGain(g);
                if (masterRef.current) masterRef.current.gain.value = 10 ** (g / 20);
              }}
              className="ab-gain-slider"
            />
          )}
        </div>
        {loading && <div className="rs-empty">Switching mode…</div>}
        {err && <div className="error">{err}</div>}
      </div>
    </div>
  );
}

export async function fetchAudioBlob(url: string): Promise<string> {
  const token = localStorage.getItem("soundhub_token");
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error(`Audio request failed (${res.status})`);
  return URL.createObjectURL(await res.blob());
}

export async function decodeAudio(ctx: AudioContext, url: string): Promise<AudioBuffer> {
  const res = await fetch(url);
  const buf = await res.arrayBuffer();
  return ctx.decodeAudioData(buf);
}

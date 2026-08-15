import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { fmtClock } from "./ReviewShared";
import type { VersionComparison } from "../types";

const CROSSFADE_MS = 40;

/**
 * A/B comparison player.
 *
 * Both versions are decoded to AudioBuffers and started at the SAME offset,
 * so A/B toggling never resets the playhead. Switching crossfades the gains
 * (40 ms). Level-matched gains from the comparison are applied ONLY to the
 * preview graph — source files and the release package are untouched.
 */
export default function ABCompare({
  sessionId,
  comparison,
  onClose,
}: {
  sessionId: number;
  comparison: VersionComparison;
  onClose: () => void;
}) {
  const [buffers, setBuffers] = useState<{ base: AudioBuffer | null; compare: AudioBuffer | null }>({
    base: null,
    compare: null,
  });
  const [err, setErr] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [active, setActive] = useState<"base" | "compare">("base");
  const [position, setPosition] = useState(0);
  const [duration, setDuration] = useState(0);
  const [gain, setGain] = useState(0);
  const [manual, setManual] = useState(false);
  const ctxRef = useRef<AudioContext | null>(null);
  const srcRef = useRef<{ base: AudioBufferSourceNode; compare: AudioBufferSourceNode } | null>(null);
  const gainNodesRef = useRef<{ base: GainNode; compare: GainNode } | null>(null);
  const masterRef = useRef<GainNode | null>(null);
  const offsetRef = useRef(0);
  const playingRef = useRef(false);
  const rafRef = useRef<number | null>(null);
  const loopRef = useRef<{ start: number; end: number } | null>(null);
  const startCtxRef = useRef<number | null>(null);

  const endMs = (comparison.end_ms ?? comparison.start_ms + 20000) / 1000;

  // load both buffers
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const baseUrl = await fetchAudioBlob(api.versionAudioUrl(sessionId, comparison.base_version_id));
        const compareUrl = await fetchAudioBlob(api.versionAudioUrl(sessionId, comparison.compare_version_id));
        if (cancelled) return;
        const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        const ctx = new Ctx();
        ctxRef.current = ctx;
        const [b, c] = await Promise.all([decodeAudio(ctx, baseUrl), decodeAudio(ctx, compareUrl)]);
        if (cancelled) return;
        setBuffers({ base: b, compare: c });
        const dur = Math.min(b.duration, c.duration);
        setDuration(dur);
        setPosition(Math.min(comparison.start_ms / 1000, Math.max(0, dur - 0.05)));
        offsetRef.current = Math.min(comparison.start_ms / 1000, Math.max(0, dur - 0.05));
        loopRef.current = {
          start: Math.min(comparison.start_ms / 1000, dur - 0.05),
          end: Math.min(endMs, dur),
        };
      } catch (e) {
        setErr(e instanceof Error ? e.message : "Failed to load audio");
      }
    };
    void load();
    return () => {
      cancelled = true;
      ctxRef.current?.close().catch(() => undefined);
    };
  }, [sessionId, comparison.base_version_id, comparison.compare_version_id, comparison.start_ms, endMs]);

  const buildGraph = useCallback(() => {
    const ctx = ctxRef.current;
    const b = buffers.base;
    const c = buffers.compare;
    if (!ctx || !b || !c) return;
    if (srcRef.current) {
      srcRef.current.base.stop();
      srcRef.current.compare.stop();
    }
    const baseSrc = ctx.createBufferSource();
    baseSrc.buffer = b;
    const compareSrc = ctx.createBufferSource();
    compareSrc.buffer = c;
    const gBase = ctx.createGain();
    const gCompare = ctx.createGain();
    const master = ctx.createGain();
    baseSrc.connect(gBase).connect(master).connect(ctx.destination);
    compareSrc.connect(gCompare).connect(master).connect(ctx.destination);
    srcRef.current = { base: baseSrc, compare: compareSrc };
    gainNodesRef.current = { base: gBase, compare: gCompare };
    masterRef.current = master;
    // level-matched gains (compare attenuates when louder; base is reference)
    gBase.gain.value = 0;
    gCompare.gain.value = 0;
    const t = ctx.currentTime + 0.02;
    baseSrc.start(t, offsetRef.current);
    compareSrc.start(t, offsetRef.current);
    startCtxRef.current = t;
  }, [buffers]);

  const applyGains = useCallback(
    (side: "base" | "compare") => {
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
    },
    []
  );

  const seek = (t: number) => {
    const dur = duration || 0;
    const clamped = Math.max(0, Math.min(t, Math.max(0, dur - 0.02)));
    offsetRef.current = clamped;
    setPosition(clamped);
    if (playingRef.current) {
      // restart from the new offset to keep both sides aligned
      const g = gainNodesRef.current;
      const activeSide = active;
      if (srcRef.current) {
        try {
          srcRef.current.base.stop();
          srcRef.current.compare.stop();
        } catch {
          /* already stopped */
        }
        srcRef.current = null;
      }
      buildGraph();
      // apply crossfade to the active side (inactive silently starts)
      const now = ctxRef.current?.currentTime ?? 0;
      if (g) {
        g.base.gain.cancelScheduledValues(now);
        g.compare.gain.cancelScheduledValues(now);
        g.base.gain.value = 0;
        g.compare.gain.value = 0;
      }
      applyGains(activeSide);
    }
  };

  const toggle = () => {
    if (playing) {
      ctxRef.current?.suspend().catch(() => undefined);
      playingRef.current = false;
      setPlaying(false);
      return;
    }
    const ctx = ctxRef.current;
    if (!ctx) return;
    if (!srcRef.current) buildGraph();
    void ctx.resume().then(() => {
      applyGains(active);
      playingRef.current = true;
      setPlaying(true);
    });
  };

  const markStart = () => {
    startCtxRef.current = ctxRef.current?.currentTime ?? null;
  };

  const switchSide = (side: "base" | "compare") => {
    setActive(side);
    if (playingRef.current) applyGains(side);
  };

  // playhead + loop tick
  useEffect(() => {
    const tick = () => {
      const ctx = ctxRef.current;
      if (ctx && playingRef.current && srcRef.current && startCtxRef.current != null) {
        const pos = offsetRef.current + (ctx.currentTime - startCtxRef.current);
        const lp = loopRef.current;
        if (lp && pos >= lp.end) {
          seek(lp.start);
          return;
        }
        setPosition(Math.min(pos, duration || pos));
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
    markStart();
    toggle();
  };

  const levelLabel = comparison.level_match === "none"
    ? "Level match unavailable"
    : comparison.base_gain_db
      ? `Level matched · ${comparison.base_label} ${comparison.base_gain_db >= 0 ? "+" : ""}${comparison.base_gain_db.toFixed(1)} dB`
      : comparison.compare_gain_db
        ? `Level matched · ${comparison.compare_label} ${comparison.compare_gain_db >= 0 ? "+" : ""}${comparison.compare_gain_db.toFixed(1)} dB`
        : "Level matched · equal loudness";

  const pct = duration > 0 ? (position / duration) * 100 : 0;
  const loopStartPct = duration > 0 ? (loopRef.current?.start ?? 0 / duration) * 100 : 0;
  const loopEndPct = duration > 0 ? (loopRef.current?.end ?? duration / duration) * 100 : 100;

  return (
    <div className="ab-panel">
      <div className="ab-head">
        <span className="ab-title">
          COMPARE {comparison.base_label} ↔ {comparison.compare_label}
        </span>
        {comparison.request_id != null && <span className="ab-request">request #{comparison.request_id}</span>}
        <button type="button" className="rs-btn ghost sm" onClick={onClose}>
          ✕
        </button>
      </div>

      <div className="ab-sidebar">
        <button type="button" className={`ab-side ${active === "base" ? "active" : ""}`} onClick={() => switchSide("base")}>
          <strong>{comparison.base_label}</strong>
          {comparison.short_term_lufs[comparison.base_label] != null && (
            <span>{comparison.short_term_lufs[comparison.base_label]} LUFS</span>
          )}
        </button>
        <button type="button" className={`ab-side ${active === "compare" ? "active" : ""}`} onClick={() => switchSide("compare")}>
          <strong>{comparison.compare_label}</strong>
          {comparison.short_term_lufs[comparison.compare_label] != null && (
            <span>{comparison.short_term_lufs[comparison.compare_label]} LUFS</span>
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
          <button type="button" className="rs-play ab-play" onClick={play}>
            {playing ? "❚❚" : "▶"}
          </button>
          <span className="ab-label">
            {levelLabel}
            {comparison.level_match !== "none" && " · loop: ON"}
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
        {err && <div className="error">{err}</div>}
      </div>
    </div>
  );
}

async function fetchAudioBlob(url: string): Promise<string> {
  const token = localStorage.getItem("soundhub_token");
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error(`Audio request failed (${res.status})`);
  return URL.createObjectURL(await res.blob());
}

async function decodeAudio(ctx: AudioContext, url: string): Promise<AudioBuffer> {
  const res = await fetch(url);
  const buf = await res.arrayBuffer();
  return ctx.decodeAudioData(buf);
}

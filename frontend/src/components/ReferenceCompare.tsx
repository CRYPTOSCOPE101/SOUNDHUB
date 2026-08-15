import { useCallback, useEffect, useRef, useState } from "react";
import { fmtClock } from "./ReviewShared";
import { decodeAudio, fetchAudioBlob } from "./ABCompare";
import type { ReferenceComparison, ReferenceTrack } from "../types";

const CROSSFADE_MS = 40;
// Lookahead scheduling window (seconds) — the pattern from Ableton's
// web-audio-sequencing: schedule segments on the AudioContext clock ahead of
// time so the loop region restarts exactly and gapless, never on a rAF frame.
const SCHED_LOOKAHEAD_S = 0.15;
const SCHED_MAX_ITER = 64;

/**
 * Mix ↔ reference A/B player.
 *
 * Both files are decoded and started at the SAME offset, so toggling never
 * resets the playhead. The loudness gains from the comparison are applied
 * through GainNodes in the Web Audio graph (10^(gain/20)) — the reference
 * file and the mix are never modified, and neither is exported anywhere.
 * Neutral measurements are shown, never a judgement.
 *
 * Playback uses lookahead scheduling (segments started at exact AudioContext
 * times), so the loop region loops gapless with no stop/start gap.
 */
export default function ReferenceCompare({
  comparison,
  reference,
  onClose,
}: {
  comparison: ReferenceComparison;
  reference: ReferenceTrack;
  onClose: () => void;
}) {
  const [buffers, setBuffers] = useState<{ mix: AudioBuffer | null; ref: AudioBuffer | null }>({ mix: null, ref: null });
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [active, setActive] = useState<"mix" | "ref">("mix");
  const [position, setPosition] = useState(0);
  const [duration, setDuration] = useState(0);
  const [manual, setManual] = useState(false);
  const [masterGain, setMasterGain] = useState(0);
  const ctxRef = useRef<AudioContext | null>(null);
  const gainNodesRef = useRef<{ mix: GainNode; ref: GainNode } | null>(null);
  const masterRef = useRef<GainNode | null>(null);
  const offsetRef = useRef(0);
  const livePosRef = useRef<number | null>(null);
  const playingRef = useRef(false);
  const rafRef = useRef<number | null>(null);
  const loopRef = useRef<{ start: number; end: number } | null>(null);
  // Mirror of `buffers` state so the stable scheduler callback always sees
  // the current buffers.
  const buffersRef = useRef<{ mix: AudioBuffer | null; ref: AudioBuffer | null }>({ mix: null, ref: null });
  // Scheduled playback segments (exact AudioContext start/stop times).
  interface Segment {
    mix: AudioBufferSourceNode;
    ref: AudioBufferSourceNode;
    startCtx: number;
    endCtx: number;
  }
  const segmentsRef = useRef<Segment[]>([]);
  const nextStartCtxRef = useRef<number | null>(null);
  const nextOffsetRef = useRef(0);

  const endMs = (comparison.end_ms ?? comparison.start_ms + 20000) / 1000;
  // level compensation as linear gains (applied ONLY in the Web Audio graph)
  const mixLevel = 10 ** (comparison.mix_gain_db / 20);
  const refLevel = 10 ** (comparison.ref_gain_db / 20);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setErr(null);
      try {
        const mixUrl = await fetchAudioBlob(comparison.mix_audio_url);
        const refUrl = await fetchAudioBlob(comparison.ref_audio_url);
        if (cancelled) return;
        const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        const ctx = ctxRef.current ?? new Ctx();
        ctxRef.current = ctx;
        const [m, r] = await Promise.all([decodeAudio(ctx, mixUrl), decodeAudio(ctx, refUrl)]);
        if (cancelled) return;
        setBuffers({ mix: m, ref: r });
        buffersRef.current = { mix: m, ref: r };
        const dur = Math.min(m.duration, r.duration);
        setDuration(dur);
        const start = Math.min(comparison.start_ms / 1000, Math.max(0, dur - 0.05));
        setPosition(start);
        offsetRef.current = start;
        loopRef.current = {
          start: Math.min(comparison.start_ms / 1000, Math.max(0, dur - 0.05)),
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
  }, [comparison.id]);

  useEffect(() => {
    return () => {
      ctxRef.current?.close().catch(() => undefined);
    };
  }, []);

  // Shared gain graph — built once per buffer load; sources are created by
  // the scheduler on demand.
  const buildGraph = useCallback(() => {
    const ctx = ctxRef.current;
    if (!ctx) return;
    if (gainNodesRef.current) return;
    const gMix = ctx.createGain();
    const gRef = ctx.createGain();
    const master = ctx.createGain();
    gMix.connect(master).connect(ctx.destination);
    gRef.connect(master).connect(ctx.destination);
    gainNodesRef.current = { mix: gMix, ref: gRef };
    masterRef.current = master;
    gMix.gain.value = 0;
    gRef.gain.value = 0;
    master.gain.value = 10 ** (masterGain / 20);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [masterGain]);

  const stopAllSegments = useCallback(() => {
    for (const seg of segmentsRef.current) {
      try {
        seg.mix.stop();
        seg.ref.stop();
      } catch {
        /* already stopped */
      }
    }
    segmentsRef.current = [];
  }, []);

  // Lookahead scheduler: fill the horizon with segments starting at exact
  // AudioContext times, so the loop boundary is gapless.
  const schedule = useCallback(() => {
    const ctx = ctxRef.current;
    const m = buffersRef.current.mix;
    const r = buffersRef.current.ref;
    if (!ctx || !m || !r || !gainNodesRef.current) return;
    const g = gainNodesRef.current;
    const lp = loopRef.current;
    const horizon = ctx.currentTime + SCHED_LOOKAHEAD_S;
    let next = nextStartCtxRef.current;
    let offset = nextOffsetRef.current;
    if (next == null) return;
    const now = ctx.currentTime;
    segmentsRef.current = segmentsRef.current.filter((s) => s.endCtx > now);
    let iterations = 0;
    while (next < horizon && iterations < SCHED_MAX_ITER) {
      const start = Math.max(next, now + 0.01);
      const len = lp ? lp.end - lp.start : Math.max(0, Math.min(m.duration, r.duration) - offset);
      if (len <= 0.0005) break;
      const end = start + len;
      const mixSrc = ctx.createBufferSource();
      mixSrc.buffer = m;
      const refSrc = ctx.createBufferSource();
      refSrc.buffer = r;
      mixSrc.connect(g.mix);
      refSrc.connect(g.ref);
      mixSrc.start(start, offset);
      refSrc.start(start, offset);
      mixSrc.stop(end);
      refSrc.stop(end);
      segmentsRef.current.push({ mix: mixSrc, ref: refSrc, startCtx: start, endCtx: end });
      next = end;
      offset = lp ? lp.start : offset + len;
      iterations += 1;
    }
    nextStartCtxRef.current = next;
    nextOffsetRef.current = offset;
  }, []);

  const applyGains = useCallback((side: "mix" | "ref") => {
    const g = gainNodesRef.current;
    if (!g) return;
    const now = ctxRef.current?.currentTime ?? 0;
    const ramp = CROSSFADE_MS / 1000;
    g.mix.gain.cancelScheduledValues(now);
    g.ref.gain.cancelScheduledValues(now);
    g.mix.gain.setValueAtTime(g.mix.gain.value, now);
    g.ref.gain.setValueAtTime(g.ref.gain.value, now);
    g.mix.gain.linearRampToValueAtTime(side === "mix" ? mixLevel : 0, now + ramp);
    g.ref.gain.linearRampToValueAtTime(side === "ref" ? refLevel : 0, now + ramp);
  }, [mixLevel, refLevel]);

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

  const play = () => {
    toggle();
  };

  const switchSide = (side: "mix" | "ref") => {
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
        let pos: number | null = null;
        const now = ctx.currentTime;
        const segs = segmentsRef.current;
        if (segs.length > 0) {
          const activeSeg = segs.find((s) => s.startCtx <= now && s.endCtx > now) ?? segs[segs.length - 1];
          const base = lp ? lp.start : offsetRef.current;
          pos = base + (now - activeSeg.startCtx);
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

  const levelLabel =
    comparison.level_match === "none"
      ? "Level match unavailable"
      : `Level matched · mix ${comparison.mix_gain_db >= 0 ? "+" : ""}${comparison.mix_gain_db.toFixed(1)} dB / reference ${comparison.ref_gain_db >= 0 ? "+" : ""}${comparison.ref_gain_db.toFixed(1)} dB`;

  const pct = duration > 0 ? (position / duration) * 100 : 0;
  const loopStartPct = duration > 0 ? ((loopRef.current?.start ?? 0) / duration) * 100 : 0;
  const loopEndPct = duration > 0 ? ((loopRef.current?.end ?? duration) / duration) * 100 : 100;

  return (
    <div className="ab-panel">
      <div className="ab-head">
        <span className="ab-title">
          MIX {comparison.version_label} ↔ REFERENCE: {comparison.reference_label}
        </span>
        <span className="ab-request">reference A/B</span>
        <button type="button" className="rs-btn ghost sm" onClick={onClose}>
          ✕
        </button>
      </div>

      <div className="ab-sidebar">
        <button type="button" className={`ab-side ${active === "mix" ? "active" : ""}`} onClick={() => switchSide("mix")}>
          <strong>{comparison.version_label} — your mix</strong>
          {comparison.short_term_lufs["mix"] != null && <span>{comparison.short_term_lufs["mix"]} LUFS</span>}
        </button>
        <button type="button" className={`ab-side ${active === "ref" ? "active" : ""}`} onClick={() => switchSide("ref")}>
          <strong>Reference: {comparison.reference_label}</strong>
          {comparison.short_term_lufs["reference"] != null && <span>{comparison.short_term_lufs["reference"]} LUFS</span>}
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
          <button type="button" className="rs-play ab-play" onClick={play} disabled={loading || !buffers.mix}>
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
              value={masterGain}
              onChange={(e) => {
                const g = Number(e.target.value);
                setMasterGain(g);
                if (masterRef.current) masterRef.current.gain.value = 10 ** (g / 20);
              }}
              className="ab-gain-slider"
            />
          )}
        </div>
        {loading && <div className="rs-empty">Loading mix + reference…</div>}
        {err && <div className="error">{err}</div>}

        <div className="ref-metrics">
          <span>Reference: integrated {reference.integrated_lufs != null ? `${reference.integrated_lufs} LUFS` : "—"}</span>
          <span>true peak {reference.true_peak_dbtp != null ? `${reference.true_peak_dbtp} dBTP` : "—"}</span>
          <span>{reference.sample_rate ? `${(reference.sample_rate / 1000).toFixed(1)} kHz` : "—"}</span>
          <span>{reference.channels ? (reference.channels === 1 ? "mono" : `${reference.channels} ch`) : "—"}</span>
          {reference.purpose !== "overall" && <span className="ab-mode-chip">purpose: {reference.purpose}</span>}
        </div>
        <p className="ref-disclaimer">
          Reference audio is private to this review session and is never delivered, redistributed, or included in
          release exports. Measurements are neutral — the decision stays with you.
        </p>
      </div>
    </div>
  );
}

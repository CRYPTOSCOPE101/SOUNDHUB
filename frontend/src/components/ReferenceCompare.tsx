import { useCallback, useEffect, useRef, useState } from "react";
import { fmtClock } from "./ReviewShared";
import { decodeAudio, fetchAudioBlob } from "./ABCompare";
import type { ReferenceComparison, ReferenceTrack } from "../types";

const CROSSFADE_MS = 40;

/**
 * Mix ↔ reference A/B player.
 *
 * Both files are decoded and started at the SAME offset, so toggling never
 * resets the playhead. The loudness gains from the comparison are applied
 * through GainNodes in the Web Audio graph (10^(gain/20)) — the reference
 * file and the mix are never modified, and neither is exported anywhere.
 * Neutral measurements are shown, never a judgement.
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
  const srcRef = useRef<{ mix: AudioBufferSourceNode; ref: AudioBufferSourceNode } | null>(null);
  const gainNodesRef = useRef<{ mix: GainNode; ref: GainNode } | null>(null);
  const masterRef = useRef<GainNode | null>(null);
  const offsetRef = useRef(0);
  const playingRef = useRef(false);
  const rafRef = useRef<number | null>(null);
  const loopRef = useRef<{ start: number; end: number } | null>(null);
  const startCtxRef = useRef<number | null>(null);

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
        srcRef.current = null;
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

  const buildGraph = useCallback(() => {
    const ctx = ctxRef.current;
    const m = buffers.mix;
    const r = buffers.ref;
    if (!ctx || !m || !r) return;
    if (srcRef.current) {
      try {
        srcRef.current.mix.stop();
        srcRef.current.ref.stop();
      } catch {
        /* already stopped */
      }
    }
    const mixSrc = ctx.createBufferSource();
    mixSrc.buffer = m;
    const refSrc = ctx.createBufferSource();
    refSrc.buffer = r;
    const gMix = ctx.createGain();
    const gRef = ctx.createGain();
    const master = ctx.createGain();
    mixSrc.connect(gMix).connect(master).connect(ctx.destination);
    refSrc.connect(gRef).connect(master).connect(ctx.destination);
    srcRef.current = { mix: mixSrc, ref: refSrc };
    gainNodesRef.current = { mix: gMix, ref: gRef };
    masterRef.current = master;
    gMix.gain.value = 0;
    gRef.gain.value = 0;
    master.gain.value = 10 ** (masterGain / 20);
    const t = ctx.currentTime + 0.02;
    mixSrc.start(t, offsetRef.current);
    refSrc.start(t, offsetRef.current);
    startCtxRef.current = t;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buffers]);

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

  const seek = (t: number) => {
    const dur = duration || 0;
    const clamped = Math.max(0, Math.min(t, Math.max(0, dur - 0.02)));
    offsetRef.current = clamped;
    setPosition(clamped);
    if (playingRef.current) {
      srcRef.current = null;
      buildGraph();
      applyGains(active);
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

  const play = () => {
    startCtxRef.current = ctxRef.current?.currentTime ?? null;
    toggle();
  };

  const switchSide = (side: "mix" | "ref") => {
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

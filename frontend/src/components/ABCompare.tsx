import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { fmtClock } from "./ReviewShared";
import { STEM_LOGICAL_NAMES, type StemAsset, type VersionComparison } from "../types";

const CROSSFADE_MS = 40;

/**
 * A/B comparison player.
 *
 * Both versions are decoded to AudioBuffers and started at the SAME offset,
 * so A/B toggling never resets the playhead. Switching crossfades the gains
 * (40 ms). Level-matched gains from the comparison are applied ONLY to the
 * preview graph — source files and the release package are untouched.
 *
 * Modes: `full_mix` compares the whole bounce; `stem` compares one submix
 * (drums / bass / vocal / synths) matched by logical name across both
 * versions. Stems appear in the picker only when present in BOTH versions.
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
  const srcRef = useRef<{ base: AudioBufferSourceNode; compare: AudioBufferSourceNode } | null>(null);
  const gainNodesRef = useRef<{ base: GainNode; compare: GainNode } | null>(null);
  const masterRef = useRef<GainNode | null>(null);
  const offsetRef = useRef(0);
  const playingRef = useRef(false);
  const rafRef = useRef<number | null>(null);
  const loopRef = useRef<{ start: number; end: number } | null>(null);
  const startCtxRef = useRef<number | null>(null);
  const compRef = useRef(comp);
  compRef.current = comp;

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
  }, [comp, stems.base, stems.compare, sessionId]);

  useEffect(() => {
    return () => {
      ctxRef.current?.close().catch(() => undefined);
    };
  }, []);

  const buildGraph = useCallback(() => {
    const ctx = ctxRef.current;
    const b = buffers.base;
    const c = buffers.compare;
    if (!ctx || !b || !c) return;
    if (srcRef.current) {
      try {
        srcRef.current.base.stop();
        srcRef.current.compare.stop();
      } catch {
        /* already stopped */
      }
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
    gBase.gain.value = 0;
    gCompare.gain.value = 0;
    const t = ctx.currentTime + 0.02;
    baseSrc.start(t, offsetRef.current);
    compareSrc.start(t, offsetRef.current);
    startCtxRef.current = t;
  }, [buffers]);

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

  const seek = (t: number) => {
    const dur = duration || 0;
    const clamped = Math.max(0, Math.min(t, Math.max(0, dur - 0.02)));
    offsetRef.current = clamped;
    setPosition(clamped);
    if (playingRef.current) {
      const g = gainNodesRef.current;
      const activeSide = active;
      srcRef.current = null;
      buildGraph();
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

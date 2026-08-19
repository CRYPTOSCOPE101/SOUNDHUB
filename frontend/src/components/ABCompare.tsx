import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import AbTransport from "./AbTransport";
import { STEM_LOGICAL_NAMES, type StemAsset, type VersionComparison } from "../types";
import { errorMessage } from "../errors";
import { fetchAudioBlob } from "../audio/sources";
import { useAbPlayer, type Pair } from "../audio/useAbPlayer";

/**
 * A/B comparison player.
 *
 * Playback (decoding, gapless loop scheduling, crossfaded side switching)
 * lives in `useAbPlayer`; side "a" is the base version, "b" the compare one.
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
  const [stems, setStems] = useState<{ base: StemAsset[]; compare: StemAsset[] }>({ base: [], compare: [] });
  const [switching, setSwitching] = useState(false);

  // load stems for both versions (for the picker) — owner context only.
  // Guests get full-mix comparisons (backend rejects stem mode for guests),
  // and the stems endpoints are owner-only: calling them would 401 and the
  // api layer redirects the whole public review page to /login.
  useEffect(() => {
    if (audioUrls) return; // guest mode — skip owner-only stems
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
  }, [comp.base_version_id, comp.compare_version_id, audioUrls]);

  // stems available in BOTH versions (matched by logical name)
  const sharedStems = STEM_LOGICAL_NAMES.filter(
    (name) => stems.base.some((s) => s.logical_name === name) && stems.compare.some((s) => s.logical_name === name)
  );

  const resolveUrls = useCallback(async (): Promise<Pair<string>> => {
    if (comp.mode === "stem" && comp.stem_logical_name) {
      const bStem = stems.base.find((s) => s.logical_name === comp.stem_logical_name);
      const cStem = stems.compare.find((s) => s.logical_name === comp.stem_logical_name);
      if (!bStem || !cStem) throw new Error(`Stem “${comp.stem_logical_name}” is unavailable in one of the versions`);
      return {
        a: await fetchAudioBlob(api.stemAudioUrl(comp.base_version_id, bStem.id)),
        b: await fetchAudioBlob(api.stemAudioUrl(comp.compare_version_id, cStem.id)),
      };
    }
    if (audioUrls) return { a: audioUrls.base, b: audioUrls.compare };
    return {
      a: await fetchAudioBlob(api.versionAudioUrl(sessionId, comp.base_version_id)),
      b: await fetchAudioBlob(api.versionAudioUrl(sessionId, comp.compare_version_id)),
    };
  }, [audioUrls, comp, sessionId, stems]);

  const reloadKey = useMemo(
    () =>
      [
        sessionId,
        comp.id,
        comp.mode,
        comp.stem_logical_name ?? "",
        stems.base.map((s) => s.id).join(","),
        stems.compare.map((s) => s.id).join(","),
      ].join("|"),
    [comp, sessionId, stems]
  );

  const player = useAbPlayer({
    resolveUrls,
    reloadKey,
    startMs: comp.start_ms,
    endMs: comp.end_ms,
  });
  const { active } = player;
  const loading = player.loading || switching;

  const switchMode = async (mode: string, stemName?: string) => {
    setSwitching(true);
    player.setError(null);
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
      player.setError(errorMessage(e, "Failed to switch mode"));
    } finally {
      setSwitching(false);
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
        <button type="button" className={`ab-side ${active === "a" ? "active" : ""}`} onClick={() => player.switchSide("a")}>
          <strong>{comp.base_label}</strong>
          {comp.short_term_lufs[comp.base_label] != null && (
            <span>{comp.short_term_lufs[comp.base_label]} LUFS</span>
          )}
        </button>
        <button type="button" className={`ab-side ${active === "b" ? "active" : ""}`} onClick={() => player.switchSide("b")}>
          <strong>{comp.compare_label}</strong>
          {comp.short_term_lufs[comp.compare_label] != null && (
            <span>{comp.short_term_lufs[comp.compare_label]} LUFS</span>
          )}
        </button>
      </div>

      <div className="ab-body">
        <AbTransport
          player={player}
          levelLabel={levelLabel}
          showLoop={comp.level_match !== "none"}
          loading={loading}
          loadingText="Switching mode…"
        />
      </div>
    </div>
  );
}

import { useCallback, useMemo } from "react";
import AbTransport from "./AbTransport";
import type { ReferenceComparison, ReferenceTrack } from "../types";
import { fetchAudioBlob } from "../audio/sources";
import { useAbPlayer, type Pair } from "../audio/useAbPlayer";

/**
 * Mix ↔ reference A/B player.
 *
 * Playback lives in `useAbPlayer` ("a" is the mix, "b" the reference). The
 * loudness gains from the comparison are applied as per-side gains in the Web
 * Audio graph (10^(gain/20)) — the reference file and the mix are never
 * modified, and neither is exported anywhere. Neutral measurements are shown,
 * never a judgement.
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
  const resolveUrls = useCallback(
    async (): Promise<Pair<string>> => ({
      a: await fetchAudioBlob(comparison.mix_audio_url),
      b: await fetchAudioBlob(comparison.ref_audio_url),
    }),
    [comparison.mix_audio_url, comparison.ref_audio_url]
  );

  // level compensation as linear gains (applied ONLY in the Web Audio graph)
  const levels = useMemo<Pair<number>>(
    () => ({ a: 10 ** (comparison.mix_gain_db / 20), b: 10 ** (comparison.ref_gain_db / 20) }),
    [comparison.mix_gain_db, comparison.ref_gain_db]
  );

  const player = useAbPlayer({
    resolveUrls,
    reloadKey: comparison.id,
    startMs: comparison.start_ms,
    endMs: comparison.end_ms,
    levels,
  });
  const { active } = player;

  const levelLabel =
    comparison.level_match === "none"
      ? "Level match unavailable"
      : `Level matched · mix ${comparison.mix_gain_db >= 0 ? "+" : ""}${comparison.mix_gain_db.toFixed(1)} dB / reference ${comparison.ref_gain_db >= 0 ? "+" : ""}${comparison.ref_gain_db.toFixed(1)} dB`;

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
        <button type="button" className={`ab-side ${active === "a" ? "active" : ""}`} onClick={() => player.switchSide("a")}>
          <strong>{comparison.version_label} — your mix</strong>
          {comparison.short_term_lufs["mix"] != null && <span>{comparison.short_term_lufs["mix"]} LUFS</span>}
        </button>
        <button type="button" className={`ab-side ${active === "b" ? "active" : ""}`} onClick={() => player.switchSide("b")}>
          <strong>Reference: {comparison.reference_label}</strong>
          {comparison.short_term_lufs["reference"] != null && <span>{comparison.short_term_lufs["reference"]} LUFS</span>}
        </button>
      </div>

      <div className="ab-body">
        <AbTransport
          player={player}
          levelLabel={levelLabel}
          showLoop={comparison.level_match !== "none"}
          loadingText="Loading mix + reference…"
        />

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

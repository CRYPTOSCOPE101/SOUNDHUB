import { useState } from "react";
import { fmtClock } from "./ReviewShared";
import type { AbPlayer } from "../audio/useAbPlayer";

/**
 * Transport strip shared by the A/B players: loop-marked waveform, playhead,
 * play/pause, level-match label and the manual master-gain override.
 */
export default function AbTransport({
  player,
  levelLabel,
  showLoop,
  loadingText,
  loading,
}: {
  player: AbPlayer;
  levelLabel: string;
  /** Show the "loop: ON" hint next to the level label. */
  showLoop: boolean;
  loadingText: string;
  /** Busy state; defaults to the player's own loading flag. */
  loading?: boolean;
}) {
  const [manual, setManual] = useState(false);
  const [gainDb, setGainDb] = useState(0);
  const { duration, loop, playing, position } = player;
  const busy = loading ?? player.loading;

  const pct = duration > 0 ? (position / duration) * 100 : 0;
  const loopStartPct = duration > 0 ? ((loop?.start ?? 0) / duration) * 100 : 0;
  const loopEndPct = duration > 0 ? ((loop?.end ?? duration) / duration) * 100 : 100;

  return (
    <>
      <div className="ab-wave">
        <div className="ab-loop" style={{ left: `${loopStartPct}%`, width: `${Math.max(0, loopEndPct - loopStartPct)}%` }} />
        <div className="ab-playhead" style={{ left: `${pct}%` }} />
        <span className="ab-time">{fmtClock(position)}</span>
        <span className="ab-time right">{fmtClock(duration)}</span>
      </div>

      <div className="ab-controls">
        <button type="button" className="rs-play ab-play" onClick={player.toggle} disabled={busy || !player.buffers.a}>
          {playing ? "❚❚" : "▶"}
        </button>
        <span className="ab-label">
          {levelLabel}
          {showLoop && " · loop: ON"}
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
            value={gainDb}
            onChange={(e) => {
              const g = Number(e.target.value);
              setGainDb(g);
              player.setMasterGainDb(g);
            }}
            className="ab-gain-slider"
          />
        )}
      </div>
      {busy && <div className="rs-empty">{loadingText}</div>}
      {player.error && <div className="error">{player.error}</div>}
    </>
  );
}

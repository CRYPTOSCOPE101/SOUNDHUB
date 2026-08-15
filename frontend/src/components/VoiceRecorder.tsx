import { useEffect, useRef, useState } from "react";

interface Props {
  onRecorded: (blob: Blob, durationS: number) => void;
  onCancel?: () => void;
  label?: string;
}

/**
 * Tiny MediaRecorder wrapper for voice notes. Uses the browser's microphone —
 * no account, no upload until the user confirms. Falls back to default
 * mimeType when webm/opus isn't available (Safari).
 */
export default function VoiceRecorder({ onRecorded, onCancel, label }: Props) {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const startRef = useRef(0);

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      mediaRef.current?.stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const start = async () => {
    setErr(null);
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("Recording isn't supported in this browser");
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : MediaRecorder.isTypeSupported("audio/ogg")
          ? "audio/ogg"
          : "";
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mime || "audio/webm" });
        const dur = (Date.now() - startRef.current) / 1000;
        stream.getTracks().forEach((t) => t.stop());
        if (dur < 0.4) {
          setErr("Recording was too short — hold it a moment longer");
          return;
        }
        onRecorded(blob, Math.round(dur * 10) / 10);
      };
      rec.onerror = () => setErr("Recording failed — check the microphone permission");
      mediaRef.current = rec;
      startRef.current = Date.now();
      rec.start();
      setRecording(true);
      setSeconds(0);
      timerRef.current = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Microphone unavailable");
    }
  };

  const stop = () => {
    if (mediaRef.current && mediaRef.current.state !== "inactive") {
      mediaRef.current.stop();
    }
    setRecording(false);
    if (timerRef.current) window.clearInterval(timerRef.current);
  };

  const cancel = () => {
    stop();
    onCancel?.();
  };

  return (
    <div className="voice-rec">
      {!recording ? (
        <button type="button" className="rs-btn ghost sm" onClick={() => void start()} title="Record a voice note">
          🎙 {label ?? "Record voice note"}
        </button>
      ) : (
        <span className="voice-rec-live">
          <span className="voice-rec-dot" /> recording {seconds}s
          <button type="button" className="rs-btn approve sm" onClick={stop}>
            ■ Stop
          </button>
          <button type="button" className="rs-btn ghost sm" onClick={cancel}>
            ✕
          </button>
        </span>
      )}
      {err && <div className="error" style={{ marginTop: 4 }}>{err}</div>}
    </div>
  );
}

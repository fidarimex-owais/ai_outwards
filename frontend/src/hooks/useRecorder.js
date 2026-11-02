import { useCallback, useRef, useState } from "react";

// Manual recording only (click to start, click Stop or Cancel to end) - this spec doesn't
// ask for a hands-free/auto-stop mode, so there's no silence detection here, just live
// volume data for the waveform display.
export function useRecorder() {
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const audioCtxRef = useRef(null);
  const rafRef = useRef(null);
  const cancelledRef = useRef(false);

  const stopVolumeLoop = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
  }, []);

  const start = useCallback(async (onVolume) => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;
    chunksRef.current = [];
    cancelledRef.current = false;

    const recorder = new MediaRecorder(stream);
    mediaRecorderRef.current = recorder;
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    recorder.start();
    setIsRecording(true);

    if (onVolume) {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      audioCtxRef.current = audioCtx;
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 2048;
      source.connect(analyser);
      const data = new Uint8Array(analyser.fftSize);

      const tick = () => {
        analyser.getByteTimeDomainData(data);
        let sumSquares = 0;
        for (let i = 0; i < data.length; i++) {
          const v = (data[i] - 128) / 128;
          sumSquares += v * v;
        }
        onVolume(Math.sqrt(sumSquares / data.length));
        rafRef.current = requestAnimationFrame(tick);
      };
      rafRef.current = requestAnimationFrame(tick);
    }
  }, []);

  // Resolves with the recorded Blob, or null if cancelled / nothing was recording.
  const stop = useCallback(
    ({ cancel = false } = {}) =>
      new Promise((resolve) => {
        const recorder = mediaRecorderRef.current;
        if (!recorder || recorder.state === "inactive") {
          resolve(null);
          return;
        }
        cancelledRef.current = cancel;
        recorder.onstop = () => {
          stopVolumeLoop();
          streamRef.current?.getTracks().forEach((t) => t.stop());
          setIsRecording(false);
          if (cancelledRef.current) {
            resolve(null);
            return;
          }
          const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
          resolve(blob);
        };
        recorder.stop();
      }),
    [stopVolumeLoop]
  );

  return { isRecording, start, stop };
}

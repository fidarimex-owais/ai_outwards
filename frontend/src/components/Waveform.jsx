import { useEffect, useRef } from "react";
import "./Waveform.css";

// `getVolume` is a function (not a prop value) returning the latest RMS reading - driven by
// a ref under the hood so this can redraw every frame without forcing a React re-render.
export default function Waveform({ active, getVolume }) {
  const canvasRef = useRef(null);
  const rafRef = useRef(null);

  useEffect(() => {
    if (!active) return undefined;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");

    const draw = () => {
      const rms = getVolume ? getVolume() : 0;
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = "#4f9cff";
      const barCount = 28;
      const barWidth = w / barCount;
      const now = Date.now();
      for (let i = 0; i < barCount; i++) {
        // live volume sets the overall height, a per-bar time-based wiggle keeps it lively
        const wiggle = 0.5 + 0.5 * Math.sin(now / 130 + i * 0.9);
        const amp = Math.min(1, Math.max(0.06, Math.min(1, rms * 7)) * wiggle + 0.04);
        const barH = Math.max(2, amp * h);
        ctx.fillRect(i * barWidth + 1, (h - barH) / 2, Math.max(1, barWidth - 2), barH);
      }
      rafRef.current = requestAnimationFrame(draw);
    };
    rafRef.current = requestAnimationFrame(draw);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [active, getVolume]);

  return <canvas ref={canvasRef} width={280} height={36} className="waveform-canvas" />;
}

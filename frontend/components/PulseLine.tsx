"use client";

import { useEffect, useRef } from "react";

/**
 * PulseLine — animated ECG that rotates through real cardiac rhythms:
 * Normal Sinus → Atrial Fibrillation → Atrial Flutter → SVT → Torsades de Pointes
 * Canvas-based with a traveling red glow dot.
 */

// Each rhythm is an array of [x, y] points normalized 0–1
// y=0.5 is baseline, y=0 is top, y=1 is bottom

function sinusRhythm(): [number, number][] {
  // Classic NSR: flat → P wave → flat → QRS → flat → T wave → flat (repeated)
  const pts: [number, number][] = [];
  const cycles = 3;
  for (let c = 0; c < cycles; c++) {
    const o = c / cycles;
    const s = 1 / cycles;
    pts.push([o, 0.5]);
    // P wave
    pts.push([o + s * 0.12, 0.5]);
    pts.push([o + s * 0.16, 0.42]);
    pts.push([o + s * 0.20, 0.5]);
    // PR segment
    pts.push([o + s * 0.25, 0.5]);
    // QRS complex
    pts.push([o + s * 0.28, 0.55]);
    pts.push([o + s * 0.30, 0.12]);  // R peak
    pts.push([o + s * 0.33, 0.75]);  // S wave
    pts.push([o + s * 0.35, 0.5]);
    // ST segment
    pts.push([o + s * 0.45, 0.5]);
    // T wave
    pts.push([o + s * 0.52, 0.38]);
    pts.push([o + s * 0.58, 0.5]);
    // Baseline
    pts.push([o + s * 0.75, 0.5]);
  }
  pts.push([1, 0.5]);
  return pts;
}

function afibRhythm(): [number, number][] {
  // AFib: irregular fibrillatory baseline + irregular QRS complexes
  const pts: [number, number][] = [];
  const beats = [0.0, 0.18, 0.42, 0.55, 0.78]; // irregular spacing
  let x = 0;
  for (let i = 0; i < beats.length; i++) {
    const bx = beats[i];
    // Fibrillatory baseline between beats
    while (x < bx) {
      pts.push([x, 0.5 + (Math.sin(x * 80) * 0.03) + (Math.cos(x * 120) * 0.02)]);
      x += 0.008;
    }
    // Narrow QRS (no P wave)
    pts.push([bx, 0.5]);
    pts.push([bx + 0.01, 0.55]);
    pts.push([bx + 0.02, 0.15 + Math.random() * 0.1]); // R peak, variable height
    pts.push([bx + 0.035, 0.7]);
    pts.push([bx + 0.045, 0.5]);
    x = bx + 0.06;
    // Small T wave
    pts.push([x, 0.5]);
    pts.push([x + 0.02, 0.42]);
    pts.push([x + 0.04, 0.5]);
    x += 0.05;
  }
  while (x <= 1) {
    pts.push([x, 0.5 + Math.sin(x * 80) * 0.03]);
    x += 0.008;
  }
  return pts;
}

function flutterRhythm(): [number, number][] {
  // Atrial Flutter: sawtooth F waves at ~300bpm with periodic QRS
  const pts: [number, number][] = [];
  const qrsPositions = [0.22, 0.52, 0.82]; // regular ventricular response
  let x = 0;
  const fWavePeriod = 0.055; // ~300bpm sawtooth
  while (x <= 1) {
    // Check if QRS here
    const nearQRS = qrsPositions.find(q => x >= q && x < q + 0.04);
    if (nearQRS !== undefined) {
      const dx = x - nearQRS;
      if (dx < 0.01) pts.push([x, 0.5]);
      else if (dx < 0.015) pts.push([x, 0.55]);
      else if (dx < 0.02) pts.push([x, 0.12]);
      else if (dx < 0.03) pts.push([x, 0.72]);
      else pts.push([x, 0.5]);
    } else {
      // Sawtooth F waves
      const phase = (x % fWavePeriod) / fWavePeriod;
      const y = phase < 0.7 ? 0.5 - phase * 0.12 : 0.5 - 0.084 + (phase - 0.7) * 0.28;
      pts.push([x, y]);
    }
    x += 0.003;
  }
  return pts;
}

function svtRhythm(): [number, number][] {
  // SVT: regular narrow complex tachycardia ~180bpm, no visible P waves
  const pts: [number, number][] = [];
  const cycles = 6; // fast rate
  for (let c = 0; c < cycles; c++) {
    const o = c / cycles;
    const s = 1 / cycles;
    pts.push([o, 0.5]);
    // No P wave — straight to QRS
    pts.push([o + s * 0.30, 0.5]);
    pts.push([o + s * 0.35, 0.55]);
    pts.push([o + s * 0.38, 0.14]); // R peak
    pts.push([o + s * 0.42, 0.68]); // S wave
    pts.push([o + s * 0.45, 0.5]);
    // Tiny T wave merging with next beat
    pts.push([o + s * 0.60, 0.5]);
    pts.push([o + s * 0.68, 0.40]);
    pts.push([o + s * 0.75, 0.5]);
    pts.push([o + s * 0.95, 0.5]);
  }
  pts.push([1, 0.5]);
  return pts;
}

function torsadesRhythm(): [number, number][] {
  // Torsades de Pointes: wide complex with "twisting" amplitude modulation
  const pts: [number, number][] = [];
  const totalCycles = 10;
  for (let i = 0; i <= 300; i++) {
    const x = i / 300;
    // Sinusoidal QRS-like oscillation
    const freq = totalCycles * Math.PI * 2 * x;
    // Amplitude envelope: crescendo-decrescendo (spindle)
    const envelope = Math.sin(Math.PI * x) * 0.42;
    // Axis shift (the "twisting")
    const twist = Math.sin(Math.PI * 2 * x * 1.3) * 0.06;
    const y = 0.5 + Math.sin(freq) * envelope + twist;
    pts.push([x, y]);
  }
  return pts;
}

const RHYTHMS = [
  { name: "Normal Sinus Rhythm", gen: sinusRhythm, dur: 5000 },
  { name: "Atrial Fibrillation", gen: afibRhythm, dur: 5000 },
  { name: "Atrial Flutter", gen: flutterRhythm, dur: 5000 },
  { name: "SVT", gen: svtRhythm, dur: 4000 },
  { name: "Torsades de Pointes", gen: torsadesRhythm, dur: 5000 },
];

function interpolatePoints(pts: [number, number][], t: number): { x: number; y: number } {
  if (pts.length === 0) return { x: 0, y: 0.5 };
  const idx = t * (pts.length - 1);
  const i = Math.floor(idx);
  const f = idx - i;
  if (i >= pts.length - 1) return { x: pts[pts.length - 1][0], y: pts[pts.length - 1][1] };
  const a = pts[i];
  const b = pts[i + 1];
  return { x: a[0] + (b[0] - a[0]) * f, y: a[1] + (b[1] - a[1]) * f };
}

export default function PulseLine({ className = "", dimmed = false }: { className?: string; dimmed?: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const raf = useRef<number>(0);
  const dimRef = useRef(dimmed);

  // Keep ref in sync with prop
  useEffect(() => {
    dimRef.current = dimmed;
  }, [dimmed]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const DPR = window.devicePixelRatio || 1;
    const W = 600;
    const H = 60;
    canvas.width = W * DPR;
    canvas.height = H * DPR;
    canvas.style.width = `${W}px`;
    canvas.style.height = `${H}px`;
    ctx.scale(DPR, DPR);

    let rhythmIdx = 0;
    let currentPts = RHYTHMS[0].gen();
    let nextPts = currentPts;
    let crossfade = 0; // 0 = current, 1 = next
    let sweepT = 0; // 0–1 sweep position
    let rhythmStart = performance.now();
    let transitioning = false;

    const SWEEP_SPEED = 0.4; // full sweeps per second
    const CROSSFADE_DUR = 1200; // ms for rhythm transition
    let crossfadeStart = 0;

    // Fade alpha — smoothly lerps toward 0 when dimmed, 1 when not
    let fadeAlpha = 1;

    const draw = (now: number) => {
      const dt = 1 / 60;
      sweepT += dt * SWEEP_SPEED;
      if (sweepT > 1) sweepT -= 1;

      // Check if time to transition
      const elapsed = now - rhythmStart;
      const currentDur = RHYTHMS[rhythmIdx].dur;
      if (!transitioning && elapsed > currentDur) {
        transitioning = true;
        crossfadeStart = now;
        const nextIdx = (rhythmIdx + 1) % RHYTHMS.length;
        nextPts = RHYTHMS[nextIdx].gen();
      }

      if (transitioning) {
        crossfade = Math.min(1, (now - crossfadeStart) / CROSSFADE_DUR);
        if (crossfade >= 1) {
          rhythmIdx = (rhythmIdx + 1) % RHYTHMS.length;
          currentPts = nextPts;
          crossfade = 0;
          transitioning = false;
          rhythmStart = now;
        }
      }

      ctx.clearRect(0, 0, W, H);

      // Smooth fade when dimmed (search input focused)
      const target = dimRef.current ? 0 : 1;
      fadeAlpha += (target - fadeAlpha) * 0.06;
      if (fadeAlpha < 0.01 && target === 0) { raf.current = requestAnimationFrame(draw); return; }
      ctx.globalAlpha = fadeAlpha;

      // Draw waveform
      const margin = 10;
      const drawW = W - margin * 2;
      const drawH = H - 8;
      const oY = 4;

      // Get blended points for drawing
      const numSamples = 400;

      // Static faint trace
      ctx.beginPath();
      for (let i = 0; i <= numSamples; i++) {
        const t = i / numSamples;
        const p1 = interpolatePoints(currentPts, t);
        const p2 = transitioning ? interpolatePoints(nextPts, t) : p1;
        const y = p1.y * (1 - crossfade) + p2.y * crossfade;
        const px = margin + t * drawW;
        const py = oY + y * drawH;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.strokeStyle = "rgba(239,68,68,0.1)";
      ctx.lineWidth = 1.5;
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      ctx.stroke();

      // Glowing sweep
      ctx.beginPath();
      const glowWidth = 0.15; // width of lit segment
      let dotX = 0, dotY = 0;
      for (let i = 0; i <= numSamples; i++) {
        const t = i / numSamples;
        const p1 = interpolatePoints(currentPts, t);
        const p2 = transitioning ? interpolatePoints(nextPts, t) : p1;
        const y = p1.y * (1 - crossfade) + p2.y * crossfade;
        const px = margin + t * drawW;
        const py = oY + y * drawH;

        // Distance from sweep head
        let dist = t - sweepT;
        if (dist < -0.5) dist += 1;
        if (dist > 0.5) dist -= 1;

        if (dist >= -glowWidth && dist <= 0) {
          const alpha = 1 - Math.abs(dist) / glowWidth;
          if (dist > -0.005) { dotX = px; dotY = py; }
          ctx.globalAlpha = alpha * 0.7 * fadeAlpha;
          if (i === 0 || dist <= -glowWidth + 0.003) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
      }
      ctx.strokeStyle = "rgba(248,113,113,0.9)";
      ctx.lineWidth = 2.5;
      ctx.shadowColor = "rgba(239,68,68,0.6)";
      ctx.shadowBlur = 8;
      ctx.stroke();
      ctx.shadowBlur = 0;
      ctx.globalAlpha = fadeAlpha;

      // Leading dot
      if (dotX > 0) {
        ctx.beginPath();
        ctx.arc(dotX, dotY, 3, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(248,113,113,0.95)";
        ctx.shadowColor = "rgba(239,68,68,0.8)";
        ctx.shadowBlur = 12;
        ctx.fill();
        ctx.shadowBlur = 0;
      }

      // Rhythm label (subtle)
      const label = transitioning
        ? RHYTHMS[(rhythmIdx + 1) % RHYTHMS.length].name
        : RHYTHMS[rhythmIdx].name;
      const labelAlpha = transitioning ? crossfade * 0.3 : 0.3;
      ctx.font = "9px 'JetBrains Mono', monospace";
      ctx.fillStyle = `rgba(248,113,113,${labelAlpha})`;
      ctx.textAlign = "right";
      ctx.fillText(label, W - margin, H - 2);

      raf.current = requestAnimationFrame(draw);
    };

    raf.current = requestAnimationFrame(draw);

    return () => cancelAnimationFrame(raf.current);
  }, []);

  return (
    <div className={`relative w-full max-w-xl mx-auto overflow-hidden ${className}`}>
      <canvas
        ref={canvasRef}
        className="w-full h-auto"
        style={{ width: 600, height: 60, maxWidth: "100%" }}
      />
    </div>
  );
}


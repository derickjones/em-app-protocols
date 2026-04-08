"use client";

import { useEffect, useRef } from "react";

/**
 * GravityGrid — a canvas dot grid with a gravity-well distortion
 * that compresses dots toward the mouse cursor.
 */
export default function GravityGrid() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mouse = useRef({ x: -1000, y: -1000 });
  const raf = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Config
    const SPACING = 28;
    const DOT_RADIUS = 1;
    const PULL_RADIUS = 220; // how far the gravity reaches
    const PULL_STRENGTH = 0.7; // 0–1 how much dots compress toward cursor
    const DOT_COLOR_BASE = "rgba(255,255,255,0.15)";
    const DOT_COLOR_NEAR = "rgba(59,130,246,0.5)"; // blue glow near cursor

    let cols = 0;
    let rows = 0;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;
      ctx.scale(dpr, dpr);
      cols = Math.ceil(window.innerWidth / SPACING) + 1;
      rows = Math.ceil(window.innerHeight / SPACING) + 1;
    };

    const handleMouseMove = (e: MouseEvent) => {
      mouse.current = { x: e.clientX, y: e.clientY };
    };

    const handleMouseLeave = () => {
      mouse.current = { x: -1000, y: -1000 };
    };

    const draw = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      ctx.clearRect(0, 0, w, h);

      const mx = mouse.current.x;
      const my = mouse.current.y;

      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          // Original grid position
          const ox = c * SPACING;
          const oy = r * SPACING;

          // Distance to mouse
          const dx = ox - mx;
          const dy = oy - my;
          const dist = Math.sqrt(dx * dx + dy * dy);

          let x = ox;
          let y = oy;
          let alpha = 0;

          if (dist < PULL_RADIUS && dist > 0) {
            // Ease: stronger pull when closer
            const t = 1 - dist / PULL_RADIUS;
            const ease = t * t; // quadratic ease-in
            const pull = ease * PULL_STRENGTH;

            // Move dot toward mouse
            x = ox - dx * pull;
            y = oy - dy * pull;
            alpha = ease;
          }

          // Interpolate color
          ctx.beginPath();
          ctx.arc(x, y, DOT_RADIUS + (alpha * 0.8), 0, Math.PI * 2);

          if (alpha > 0) {
            // Blend toward blue
            const r_c = Math.round(255 + (59 - 255) * alpha);
            const g_c = Math.round(255 + (130 - 255) * alpha);
            const b_c = Math.round(255 + (246 - 255) * alpha);
            const a = 0.15 + alpha * 0.35;
            ctx.fillStyle = `rgba(${r_c},${g_c},${b_c},${a})`;
          } else {
            ctx.fillStyle = DOT_COLOR_BASE;
          }
          ctx.fill();
        }
      }

      raf.current = requestAnimationFrame(draw);
    };

    resize();
    window.addEventListener("resize", resize);
    window.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseleave", handleMouseLeave);
    raf.current = requestAnimationFrame(draw);

    return () => {
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseleave", handleMouseLeave);
      cancelAnimationFrame(raf.current);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none fixed inset-0 z-0"
      style={{ willChange: "transform" }}
    />
  );
}

"use client";

import React, { useState, useRef, useEffect } from "react";
import { ChevronDown, Check } from "lucide-react";

export type AppMode = "qa" | "protocol-summary";

interface ModeSelectorProps {
  mode: AppMode;
  onChange: (mode: AppMode) => void;
  darkMode: boolean;
}

const MODES = [
  {
    key: "qa" as AppMode,
    label: "ED Universe Q&A",
    description: "AI-powered answers with citations",
  },
  {
    key: "protocol-summary" as AppMode,
    label: "Protocol Summary",
    description: "Browse matching local protocols",
  },
];

export default function ModeSelector({ mode, onChange, darkMode }: ModeSelectorProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const current = MODES.find((m) => m.key === mode)!;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
          darkMode
            ? "bg-neutral-700 hover:bg-neutral-600 text-gray-200"
            : "bg-gray-200 hover:bg-gray-300 text-gray-700"
        }`}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span>{current.label}</span>
        <ChevronDown
          className={`w-3 h-3 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div
          className={`absolute right-0 bottom-full mb-2 w-60 rounded-xl shadow-xl z-50 overflow-hidden border ${
            darkMode
              ? "bg-neutral-800 border-neutral-700"
              : "bg-white border-gray-200"
          }`}
        >
          {MODES.map((m) => (
            <button
              key={m.key}
              onClick={() => {
                onChange(m.key);
                setOpen(false);
              }}
              className={`w-full flex items-center gap-3 px-4 py-3 text-left transition-colors ${
                darkMode ? "hover:bg-neutral-700" : "hover:bg-gray-50"
              } ${mode === m.key ? (darkMode ? "bg-neutral-700/50" : "bg-gray-50") : ""}`}
            >
              <div className="flex-1 min-w-0">
                <div
                  className={`text-sm font-medium ${
                    darkMode ? "text-gray-100" : "text-gray-800"
                  }`}
                >
                  {m.label}
                </div>
                <div
                  className={`text-xs ${
                    darkMode ? "text-gray-400" : "text-gray-500"
                  }`}
                >
                  {m.description}
                </div>
              </div>
              {mode === m.key && (
                <Check className="w-4 h-4 text-blue-400 flex-shrink-0" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

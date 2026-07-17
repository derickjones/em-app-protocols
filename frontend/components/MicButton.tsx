"use client";

import { Mic, MicOff } from "lucide-react";

interface MicButtonProps {
  isSupported: boolean;
  listening: boolean;
  permissionDenied: boolean;
  onToggle: () => void;
  darkMode: boolean;
  size?: "sm" | "md";
}

export default function MicButton({ isSupported, listening, permissionDenied, onToggle, darkMode, size = "sm" }: MicButtonProps) {
  if (!isSupported) return null;

  const dim = size === "sm" ? "w-7 h-7" : "w-8 h-8";
  const iconDim = size === "sm" ? "w-3.5 h-3.5" : "w-4 h-4";

  return (
    <div className="relative inline-flex items-center">
      <button
        type="button"
        onClick={onToggle}
        title={listening ? "Stop dictation" : "Dictate your question"}
        className={`inline-flex items-center justify-center ${dim} rounded-[4px] transition-all duration-200 ${
          listening
            ? "bg-red-600 text-white animate-pulse"
            : darkMode
              ? "text-[#6B7280] hover:text-gray-300 hover:bg-[#1E1E1E]"
              : "text-gray-400 hover:text-gray-600 hover:bg-gray-100"
        }`}
      >
        {listening ? <MicOff className={iconDim} /> : <Mic className={iconDim} />}
      </button>
      {permissionDenied && (
        <span className="absolute top-full mt-1 right-0 whitespace-nowrap text-[10px] text-red-500 bg-white dark:bg-[#0F0F0F] px-1.5 py-0.5 rounded shadow z-10">
          Mic access denied — enable in Settings
        </span>
      )}
    </div>
  );
}

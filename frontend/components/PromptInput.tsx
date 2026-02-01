"use client";

import React, { useState } from "react";
import { ArrowUp, Mic, MicOff } from "lucide-react";

type PromptInputProps = {
  question: string;
  setQuestion: React.Dispatch<React.SetStateAction<string>>;
  onSubmit: () => void;
  loading: boolean;
  pinned?: boolean;
};

export default function PromptInput({
  question,
  setQuestion,
  onSubmit,
  loading,
  pinned = false,
}: PromptInputProps) {
  const [isListening, setIsListening] = useState(false);

  const handleMicClick = () => {
    setIsListening(!isListening);
  };

  const handleSubmit = () => {
    if (!question.trim() || loading) return;
    onSubmit();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div
      className={`w-full ${
        pinned
          ? "fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 py-3 shadow-lg z-50"
          : ""
      }`}
    >
      <div className="w-full max-w-4xl mx-auto">
        {/* Input container - pill shape with blue glow */}
        <div
          className="relative flex items-center bg-gray-50 rounded-full border-2 border-gray-200 shadow-lg hover:shadow-xl transition-shadow duration-200 focus-within:border-blue-400 focus-within:ring-4 focus-within:ring-blue-50"
          style={{
            boxShadow: "0 4px 20px rgba(59, 130, 246, 0.15)",
          }}
        >
          {/* Text input */}
          <input
            type="text"
            className="flex-1 bg-transparent py-4 px-6 text-gray-800 placeholder-gray-400 focus:outline-none text-base"
            placeholder="Enter a clinical question or use the mic..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
          />

          {/* Mic button */}
          <button
            type="button"
            onClick={handleMicClick}
            className={`flex-shrink-0 w-11 h-11 rounded-full flex items-center justify-center mr-1 transition-all duration-200 ${
              isListening
                ? "bg-red-100 text-red-600"
                : "bg-white text-gray-500 border border-gray-200 hover:bg-gray-100"
            }`}
          >
            {isListening ? (
              <MicOff className="w-5 h-5" />
            ) : (
              <Mic className="w-5 h-5" />
            )}
          </button>

          {/* Submit button - black circle */}
          <button
            type="button"
            onClick={handleSubmit}
            disabled={loading || !question.trim()}
            className="flex-shrink-0 w-11 h-11 rounded-full bg-black text-white flex items-center justify-center mr-2 hover:bg-gray-800 disabled:bg-gray-300 disabled:cursor-not-allowed transition-all duration-200"
          >
            {loading ? (
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <ArrowUp className="w-5 h-5" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

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
  const [listening, setListening] = useState(false);
  const [interimTranscript, setInterimTranscript] = useState("");

  const handleMicClick = () => {
    setListening(!listening);
  };

  const handleSubmit = () => {
    if (!question.trim() || loading) return;
    onSubmit();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div
      className={`w-full flex justify-center ${
        pinned ? "fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 py-2 shadow-md z-50" : ""
      }`}
    >
      <div className="w-full max-w-4xl">
        <div className="relative mt-2">
          <textarea
            className="w-full p-4 pl-5 pr-20 border-2 border-gray-300 rounded-3xl bg-gray-50 text-sm text-gray-800 shadow-lg resize-none focus:outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100 transition-all duration-200 hover:shadow-xl"
            placeholder="Enter a clinical question or use the mic..."
            rows={2}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
          />

          <button
            onClick={handleMicClick}
            title="Voice input"
            className={`absolute right-14 top-1/2 -translate-y-1/2 w-10 h-10 rounded-2xl ${
              listening ? "bg-red-200 text-red-700" : "bg-white text-gray-600"
            } flex items-center justify-center hover:bg-gray-100 border-2 border-gray-300 transition-all duration-200 shadow-md hover:shadow-lg`}
          >
            {listening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
          </button>

          <button
            onClick={handleSubmit}
            disabled={loading}
            title="Submit"
            className="absolute right-2 top-1/2 -translate-y-1/2 w-10 h-10 rounded-2xl bg-black text-white flex items-center justify-center transition-all duration-200 hover:bg-gray-800 hover:scale-105 border-2 border-transparent hover:border-gray-300 disabled:opacity-50 disabled:hover:scale-100 shadow-md hover:shadow-lg"
          >
            {loading ? (
              <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <ArrowUp className="w-4 h-4" />
            )}
          </button>
        </div>

        {interimTranscript && (
          <p className="text-xs text-gray-500 italic mt-1 px-1 font-sans">
            🎤 {interimTranscript}
          </p>
        )}
      </div>
    </div>
  );
}

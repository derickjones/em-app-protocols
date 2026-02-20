"use client";

import React, { useState } from "react";
import { Plus, Mic, SlidersHorizontal } from "lucide-react";

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
        pinned ? "fixed bottom-0 left-0 right-0 px-4 py-6 z-50 bg-gradient-to-t from-[#131314] to-transparent" : ""
      }`}
    >
      <div className="w-full max-w-3xl">
        {/* Input container */}
        <div className="bg-[#1e1f20] border border-[#3c4043] rounded-3xl overflow-hidden hover:border-[#5f6368] transition-colors">
          {/* Text input area */}
          <div className="px-6 pt-5 pb-3">
            <textarea
              className="w-full bg-transparent text-white placeholder-[#9aa0a6] focus:outline-none text-base resize-none leading-relaxed"
              placeholder="What's the emergency?"
              rows={1}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              style={{ minHeight: '28px' }}
            />
          </div>

          {/* Bottom toolbar */}
          <div className="flex items-center justify-between px-4 pb-4">
            <div className="flex items-center space-x-1">
              {/* Plus button */}
              <button
                type="button"
                className="w-10 h-10 flex items-center justify-center text-[#9aa0a6] hover:text-white hover:bg-[#3c4043] rounded-full transition-all duration-200"
              >
                <Plus className="w-5 h-5" strokeWidth={1.5} />
              </button>

              {/* Tools button */}
              <button
                type="button"
                className="flex items-center space-x-2 px-4 py-2 text-[#9aa0a6] hover:text-white hover:bg-[#3c4043] rounded-full transition-all duration-200"
              >
                <SlidersHorizontal className="w-4 h-4" strokeWidth={1.5} />
                <span className="text-sm font-light">Tools</span>
              </button>
            </div>

            <div className="flex items-center space-x-2">
              {/* Mic button */}
              <button
                type="button"
                onClick={handleMicClick}
                className={`w-10 h-10 flex items-center justify-center rounded-full transition-all duration-200 ${
                  listening 
                    ? "text-red-400 bg-red-500/20" 
                    : "text-[#9aa0a6] hover:text-white hover:bg-[#3c4043]"
                }`}
              >
                <Mic className="w-5 h-5" strokeWidth={1.5} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

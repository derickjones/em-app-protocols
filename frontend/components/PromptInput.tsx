"use client";

import React, { useState, useRef, useEffect } from "react";
import { ArrowUp, Mic, MicOff } from "lucide-react";

type PromptInputProps = {
  question: string;
  setQuestion: React.Dispatch<React.SetStateAction<string>>;
  onSubmit: () => void;
  loading: boolean;
  pinned?: boolean;
};

// Web Speech API types
interface SpeechRecognitionEvent {
  resultIndex: number;
  results: SpeechRecognitionResultList;
}

interface SpeechRecognitionResultList {
  length: number;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionResult {
  isFinal: boolean;
  [index: number]: SpeechRecognitionAlternative;
}

interface SpeechRecognitionAlternative {
  transcript: string;
  confidence: number;
}

interface SpeechRecognitionErrorEvent {
  error: string;
}

interface ISpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

declare global {
  interface Window {
    SpeechRecognition: new () => ISpeechRecognition;
    webkitSpeechRecognition: new () => ISpeechRecognition;
  }
}

export default function PromptInput({
  question,
  setQuestion,
  onSubmit,
  loading,
  pinned = false,
}: PromptInputProps) {
  const [isListening, setIsListening] = useState(false);
  const [interimTranscript, setInterimTranscript] = useState("");
  const recognitionRef = useRef<ISpeechRecognition | null>(null);

  useEffect(() => {
    // Check for browser support
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = true;
      recognitionRef.current.interimResults = true;

      recognitionRef.current.onresult = (event) => {
        let interim = "";
        let final = "";

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            final += transcript;
          } else {
            interim += transcript;
          }
        }

        if (final) {
          setQuestion((prev) => prev + final);
          setInterimTranscript("");
        } else {
          setInterimTranscript(interim);
        }
      };

      recognitionRef.current.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
        setIsListening(false);
      };

      recognitionRef.current.onend = () => {
        setIsListening(false);
        setInterimTranscript("");
      };
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
    };
  }, [setQuestion]);

  const handleMicClick = () => {
    if (!recognitionRef.current) {
      alert("Speech recognition not supported in this browser");
      return;
    }

    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      recognitionRef.current.start();
      setIsListening(true);
    }
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

          {/* Mic button */}
          <button
            onClick={handleMicClick}
            title="Voice input"
            className={`absolute right-14 top-1/2 -translate-y-1/2 w-10 h-10 rounded-2xl ${
              isListening ? "bg-red-200 text-red-700" : "bg-white text-gray-600"
            } flex items-center justify-center hover:bg-gray-100 border-2 border-gray-300 transition-all duration-200 shadow-md hover:shadow-lg`}
          >
            {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
          </button>

          {/* Submit button */}
          <button
            onClick={handleSubmit}
            disabled={loading || !question.trim()}
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

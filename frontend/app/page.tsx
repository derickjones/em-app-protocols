"use client";

import { useState, useRef } from "react";
import { Sparkles } from "lucide-react";
import ReactMarkdown from "react-markdown";
import PromptInput from "@/components/PromptInput";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://em-protocol-api-930035889332.us-central1.run.app";

interface Citation {
  protocol_id: string;
  source_uri: string;
  relevance_score: number;
}

interface ProtocolImage {
  page: number;
  url: string;
  protocol_id: string;
}

interface QueryResponse {
  answer: string;
  images: ProtocolImage[];
  citations: Citation[];
  query_time_ms: number;
}

export default function Home() {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSubmit = async () => {
    if (!question.trim() || loading) return;

    setLoading(true);
    setError(null);
    setHasSearched(true);

    try {
      const res = await fetch(`${API_URL}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: question.trim() }),
      });

      if (!res.ok) {
        throw new Error(`Error: ${res.status}`);
      }

      const data: QueryResponse = await res.json();
      setResponse(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch response");
      setResponse(null);
    } finally {
      setLoading(false);
    }
  };

  const resetSearch = () => {
    setQuestion("");
    setResponse(null);
    setError(null);
    setHasSearched(false);
  };

  // Get unique citations
  const uniqueCitations = response?.citations
    ? Array.from(
        new Map(
          response.citations
            .filter((c) => c.protocol_id !== "extracted_text")
            .map((c) => [c.protocol_id, c])
        ).values()
      )
    : [];

  // Quick action buttons
  const quickActions = [
    { emoji: "��", label: "ACLS protocols" },
    { emoji: "🩺", label: "Trauma assessment" },
    { emoji: "💊", label: "Drug dosing" },
    { emoji: "⚡", label: "Stroke pathway" },
  ];

  return (
    <main className="min-h-screen bg-[#131314] text-white">
      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-50 px-6 py-4 flex items-center justify-between">
        <button 
          onClick={resetSearch}
          className="text-lg font-medium text-white/90 hover:text-white transition-colors cursor-pointer"
        >
          EM Protocols
        </button>
        
        <div className="flex items-center space-x-3">
          <span className="text-xs text-[#9aa0a6] px-2 py-1 bg-[#1e1f20] rounded-full border border-[#3c4043]">
            PRO
          </span>
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-400 to-blue-500 flex items-center justify-center text-sm font-medium">
            D
          </div>
        </div>
      </header>

      {/* Main content */}
      <div className="flex flex-col items-center justify-center min-h-screen px-4 pb-32">
        {!hasSearched ? (
          /* Welcome state */
          <div className="w-full max-w-3xl space-y-8 -mt-16">
            {/* Greeting */}
            <div className="space-y-2">
              <div className="flex items-center space-x-2 text-[#9aa0a6]">
                <Sparkles className="w-5 h-5 text-blue-400" />
                <span className="text-lg">Hi there</span>
              </div>
              <h1 className="text-4xl md:text-5xl font-light text-white/90">
                Where should we start?
              </h1>
            </div>

            {/* Input */}
            <PromptInput
              question={question}
              setQuestion={setQuestion}
              onSubmit={handleSubmit}
              loading={loading}
            />

            {/* Quick actions */}
            <div className="flex flex-wrap gap-3 justify-center pt-4">
              {quickActions.map((action, i) => (
                <button
                  key={i}
                  onClick={() => setQuestion(action.label)}
                  className="flex items-center space-x-2 px-5 py-3 bg-[#1e1f20] border border-[#3c4043] rounded-full text-sm text-[#e3e3e3] hover:bg-[#2d2e2f] hover:border-[#5f6368] transition-all duration-200"
                >
                  <span>{action.emoji}</span>
                  <span>{action.label}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Results state */
          <div className="w-full max-w-3xl pt-24 space-y-6">
            {/* User question */}
            <div className="flex justify-end">
              <div className="bg-[#1e1f20] border border-[#3c4043] rounded-2xl px-5 py-3 max-w-[80%]">
                <p className="text-white/90">{question}</p>
              </div>
            </div>

            {/* AI Response */}
            <div className="space-y-4">
              {loading ? (
                <div className="flex items-center space-x-3 text-[#9aa0a6]">
                  <div className="flex space-x-1">
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                  <span className="text-sm">Searching protocols...</span>
                </div>
              ) : error ? (
                <div className="bg-red-500/10 border border-red-500/30 rounded-2xl px-5 py-4">
                  <p className="text-red-400">{error}</p>
                </div>
              ) : response ? (
                <div className="space-y-4">
                  {/* Response time badge */}
                  <div className="flex items-center space-x-2 text-xs text-[#9aa0a6]">
                    <Sparkles className="w-4 h-4 text-blue-400" />
                    <span>Response in {response.query_time_ms}ms</span>
                  </div>
                  
                  {/* Answer */}
                  <div className="prose prose-invert prose-sm max-w-none">
                    <ReactMarkdown
                      components={{
                        h1: ({ children }) => <h1 className="text-xl font-semibold text-white mb-4">{children}</h1>,
                        h2: ({ children }) => <h2 className="text-lg font-medium text-white mt-6 mb-3">{children}</h2>,
                        h3: ({ children }) => <h3 className="text-base font-medium text-white mt-4 mb-2">{children}</h3>,
                        p: ({ children }) => <p className="text-[#e3e3e3] leading-relaxed mb-4">{children}</p>,
                        ul: ({ children }) => <ul className="space-y-2 mb-4">{children}</ul>,
                        ol: ({ children }) => <ol className="space-y-2 mb-4 list-decimal list-inside">{children}</ol>,
                        li: ({ children }) => <li className="text-[#e3e3e3]">{children}</li>,
                        strong: ({ children }) => <strong className="text-white font-medium">{children}</strong>,
                        code: ({ children }) => <code className="bg-[#1e1f20] px-2 py-1 rounded text-sm text-blue-300">{children}</code>,
                      }}
                    >
                      {response.answer}
                    </ReactMarkdown>
                  </div>

                  {/* Citations */}
                  {uniqueCitations.length > 0 && (
                    <div className="pt-4 border-t border-[#3c4043]">
                      <p className="text-xs text-[#9aa0a6] mb-3">Sources</p>
                      <div className="flex flex-wrap gap-2">
                        {uniqueCitations.map((citation, i) => (
                          <span
                            key={i}
                            className="px-3 py-1.5 bg-[#1e1f20] border border-[#3c4043] rounded-full text-xs text-[#9aa0a6]"
                          >
                            {citation.protocol_id}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Images */}
                  {response.images && response.images.length > 0 && (
                    <div className="pt-4 border-t border-[#3c4043]">
                      <p className="text-xs text-[#9aa0a6] mb-3">Related diagrams</p>
                      <div className="grid grid-cols-2 gap-3">
                        {response.images.slice(0, 4).map((img, i) => (
                          <div key={i} className="rounded-xl overflow-hidden border border-[#3c4043]">
                            <img src={img.url} alt={`Protocol diagram ${i + 1}`} className="w-full" />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          </div>
        )}
      </div>

      {/* Pinned input when in results */}
      {hasSearched && (
        <PromptInput
          question={question}
          setQuestion={setQuestion}
          onSubmit={handleSubmit}
          loading={loading}
          pinned
        />
      )}
    </main>
  );
}

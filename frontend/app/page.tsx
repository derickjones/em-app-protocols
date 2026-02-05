"use client";

import { useState } from "react";
import { Sparkles, Menu, SquarePen, Settings } from "lucide-react";
import ReactMarkdown from "react-markdown";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://em-protocol-api-930035889332.us-central1.run.app";

interface QueryResponse {
  answer: string;
  images: { page: number; url: string; protocol_id: string }[];
  citations: { protocol_id: string; source_uri: string; relevance_score: number }[];
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
      if (!res.ok) throw new Error(`Error: ${res.status}`);
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

  return (
    <div className="min-h-screen bg-[#131314] text-white flex">
      {/* Left Sidebar */}
      <div className="w-16 flex-shrink-0 flex flex-col items-center justify-between py-4 bg-[#1e1f20]">
        <div className="flex flex-col items-center">
          <button className="w-10 h-10 flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/10 rounded-full transition-colors">
            <Menu className="w-5 h-5" />
          </button>
          <button className="w-10 h-10 mt-4 flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/10 rounded-full transition-colors">
            <SquarePen className="w-5 h-5" />
          </button>
        </div>
        <button className="w-10 h-10 flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/10 rounded-full transition-colors">
          <Settings className="w-5 h-5" />
        </button>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="h-16 flex items-center justify-between px-6">
          <button onClick={resetSearch} className="text-xl font-light text-white hover:text-white/80 transition-colors">
            EM Protocols
          </button>
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-400 px-2.5 py-1 bg-white/5 rounded-full border border-white/10">
              PRO
            </span>
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-cyan-400 via-blue-500 to-purple-500 p-0.5 animate-pulse">
              <div className="w-full h-full rounded-full bg-[#131314] flex items-center justify-center text-sm font-medium">
                D
              </div>
            </div>
          </div>
        </header>

        {/* Center Content */}
        <div className="flex-1 flex flex-col items-center justify-center px-6 pb-32">
          {!hasSearched ? (
            <div className="w-full max-w-[800px] space-y-8 animate-fade-in">
              {/* Title */}
              <div className="flex flex-col items-center">
                <h1 className="text-2xl sm:text-3xl md:text-4xl font-light text-white text-center">
                  Emergency Medicine App
                </h1>
              </div>

              {/* Input Box */}
              <div className="bg-[#1e1f20] rounded-3xl border border-[#3c4043] hover:border-[#5f6368] focus-within:border-[#8ab4f8] focus-within:shadow-[0_0_0_1px_rgba(138,180,248,0.3)] transition-all p-4">
                <input
                  type="text"
                  placeholder="Ask about emergency protocols..."
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
                  className="w-full bg-transparent text-white text-lg placeholder-[#8e9193] focus:outline-none mb-8"
                />
                <div className="flex items-center justify-end">
                  <button
                    onClick={handleSubmit}
                    disabled={!question.trim()}
                    className="w-10 h-10 flex items-center justify-center text-[#9aa0a6] hover:text-white hover:bg-white/10 rounded-full disabled:text-[#5f6368] disabled:hover:bg-transparent transition-all"
                  >
                    <svg viewBox="0 0 24 24" className="w-6 h-6" fill="currentColor">
                      <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          ) : (
            /* Results View */
            <div className="w-full max-w-[800px] pt-8 space-y-6">
              {/* User Question */}
              <div className="flex justify-end">
                <div className="bg-[#2f3133] rounded-2xl px-5 py-3 max-w-[80%]">
                  <p className="text-white">{question}</p>
                </div>
              </div>

              {/* Response */}
              {loading ? (
                <div className="flex items-center gap-3">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                  <span className="text-sm text-gray-400">Searching protocols...</span>
                </div>
              ) : error ? (
                <div className="bg-red-500/10 border border-red-500/20 rounded-2xl px-5 py-4">
                  <p className="text-red-400">{error}</p>
                </div>
              ) : response ? (
                <div className="space-y-6">
                  <div className="flex items-center gap-2 text-sm text-gray-500">
                    <Sparkles className="w-4 h-4 text-blue-400" />
                    <span>{response.query_time_ms}ms</span>
                  </div>
                  <div className="prose prose-invert prose-p:text-[#e3e3e3] prose-headings:text-white max-w-none">
                    <ReactMarkdown>{response.answer}</ReactMarkdown>
                  </div>

                  {/* Protocol Images */}
                  {response.images.length > 0 && (
                    <div className="space-y-4 pt-4 border-t border-white/10">
                      <h3 className="text-sm font-medium text-gray-400">Related Diagrams</h3>
                      <div className="grid gap-4">
                        {response.images.map((img, idx) => (
                          <div key={idx} className="bg-[#1e1f20] rounded-xl overflow-hidden border border-[#3c4043]">
                            <img
                              src={img.url}
                              alt={`Protocol diagram from ${img.protocol_id}, page ${img.page}`}
                              className="w-full"
                            />
                            <div className="px-4 py-2 text-xs text-gray-400 border-t border-[#3c4043]">
                              {img.protocol_id} · Page {img.page}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Citations */}
                  {response.citations.length > 0 && (
                    <div className="space-y-3 pt-4 border-t border-white/10">
                      <h3 className="text-sm font-medium text-gray-400">Sources</h3>
                      <div className="flex flex-wrap gap-2">
                        {response.citations.map((cite, idx) => (
                          <a
                            key={idx}
                            href={cite.source_uri}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-2 px-3 py-1.5 bg-[#1e1f20] border border-[#3c4043] rounded-lg text-sm text-[#8ab4f8] hover:bg-[#2c2d2e] hover:border-[#5f6368] transition-all"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            {cite.protocol_id}
                          </a>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          )}
        </div>

        {/* Bottom Input (when searching) */}
        {hasSearched && (
          <div className="fixed bottom-0 left-16 right-0 p-6 bg-gradient-to-t from-[#131314] via-[#131314] to-transparent">
            <div className="max-w-[800px] mx-auto">
              <div className="bg-[#1e1f20] rounded-full border border-[#3c4043] flex items-center px-4 py-2">
                <input
                  type="text"
                  placeholder="Ask a follow-up..."
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
                  className="flex-1 bg-transparent text-white placeholder-[#8e9193] focus:outline-none px-2"
                />
                <button
                  onClick={handleSubmit}
                  disabled={!question.trim()}
                  className="w-9 h-9 flex items-center justify-center text-[#9aa0a6] hover:text-white disabled:text-[#5f6368] transition-colors"
                >
                  <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
                    <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

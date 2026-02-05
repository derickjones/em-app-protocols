"use client";

import { useState } from "react";
import { Sparkles, Menu, Mic, SquarePen, Settings } from "lucide-react";
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
        <header className="py-4 px-6 border-b border-white/5">
          <div className="flex items-center justify-center">
            <button onClick={resetSearch} className="flex flex-col items-center hover:opacity-80 transition-opacity">
              <span className="text-2xl font-light tracking-wide text-white lowercase">
                emergency medicine app
              </span>
              <span className="text-sm text-gray-400 mt-1">AI-powered emergency medicine clinical decision support</span>
            </button>
          </div>
          {/* Sign In - absolute positioned */}
          <div className="absolute top-4 right-6">
            <button className="flex items-center gap-2 px-4 py-2 border border-[#3c4043] rounded-full text-white hover:bg-white/5 transition-colors">
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              <span>Sign in</span>
            </button>
          </div>
        </header>

        {/* Center Content */}
        <div className={`flex-1 flex flex-col items-center px-8 ${!hasSearched ? 'justify-center' : 'overflow-y-auto'}`}>
          {!hasSearched ? (
            <div className="w-full max-w-[720px] animate-fade-in -mt-20">
              {/* Input Box */}
              <div className="bg-[#1e1f20] rounded-3xl border border-[#3c4043] hover:border-[#5f6368] focus-within:border-[#8ab4f8] focus-within:shadow-[0_0_0_1px_rgba(138,180,248,0.3)] transition-all px-8 py-5 flex items-center gap-4">
                <input
                  type="text"
                  placeholder="Enter a clinical question..."
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
                  className="flex-1 bg-transparent text-white text-xl placeholder-[#8e9193] focus:outline-none"
                />
                <button className="w-12 h-12 flex-shrink-0 flex items-center justify-center text-[#9aa0a6] hover:text-white hover:bg-white/10 rounded-full transition-all">
                  <Mic className="w-6 h-6" />
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={!question.trim()}
                  className="w-12 h-12 flex-shrink-0 flex items-center justify-center bg-white text-[#131314] rounded-full hover:bg-gray-200 disabled:bg-[#3c4043] disabled:text-[#5f6368] transition-all"
                >
                  <svg viewBox="0 0 24 24" className="w-6 h-6" fill="currentColor">
                    <path d="M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8z" />
                  </svg>
                </button>
              </div>
            </div>
          ) : (
            /* Results View */
            <div className="w-full max-w-[800px] pt-8 pb-32 space-y-6">
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
                            {cite.protocol_id.replace(/_/g, " ")}
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
          <div className="fixed bottom-0 left-16 right-0 p-8 bg-gradient-to-t from-[#131314] via-[#131314]/95 to-transparent pointer-events-none">
            <div className="max-w-[800px] mx-auto pointer-events-auto">
              <div className="bg-[#1e1f20] rounded-full border border-[#3c4043] hover:border-[#5f6368] focus-within:border-[#8ab4f8] focus-within:shadow-[0_0_0_1px_rgba(138,180,248,0.3)] transition-all flex items-center px-6 py-4 gap-4">
                <input
                  type="text"
                  placeholder="Ask a follow-up question..."
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
                  className="flex-1 bg-transparent text-white text-lg placeholder-[#8e9193] focus:outline-none"
                />
                <button className="w-10 h-10 flex-shrink-0 flex items-center justify-center text-[#9aa0a6] hover:text-white hover:bg-white/10 rounded-full transition-all">
                  <Mic className="w-5 h-5" />
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={!question.trim()}
                  className="w-10 h-10 flex-shrink-0 flex items-center justify-center bg-white text-[#131314] rounded-full hover:bg-gray-200 disabled:bg-[#3c4043] disabled:text-[#5f6368] transition-all"
                >
                  <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
                    <path d="M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8z" />
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

"use client";

import { useState, useRef } from "react";
import { Clock, FileText, Menu, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import Link from "next/link";
import PromptInput from "@/components/PromptInput";
import AuthButton from "@/components/AuthButton";

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
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

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

  return (
    <main className="relative flex flex-col items-center justify-start min-h-screen px-4 sm:px-6 py-6 bg-white text-gray-900">
      {/* Header */}
      <div className="sticky top-0 z-50 w-full bg-white px-4 pt-4 border-b border-gray-100 pb-3">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          {/* Left: Hamburger Menu */}
          <div className="flex items-center space-x-3 relative">
            <button 
              onClick={() => setMenuOpen(!menuOpen)} 
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              {menuOpen ? (
                <X className="w-5 h-5" />
              ) : (
                <Menu className="w-5 h-5" />
              )}
            </button>
            
            {/* Dropdown Menu */}
            {menuOpen && (
              <div 
                ref={menuRef} 
                className="absolute top-12 left-0 w-56 bg-white border border-gray-200 rounded-xl shadow-lg z-50"
              >
                <div className="p-2">
                  <Link
                    href="/admin"
                    onClick={() => setMenuOpen(false)}
                    className="flex items-center space-x-3 w-full px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                  >
                    <FileText className="w-4 h-4" />
                    <span>Admin Panel</span>
                  </Link>
                </div>
              </div>
            )}
          </div>

          {/* Center: Title */}
          <div className="flex-1 flex flex-col items-center text-center">
            <h1
              onClick={hasSearched ? resetSearch : undefined}
              className={`font-title font-bold tracking-wide transition-all duration-300 cursor-pointer ${
                hasSearched ? "text-xl hover:text-blue-600" : "text-2xl sm:text-4xl"
              }`}
            >
              emergency medicine app
            </h1>
            {!hasSearched && (
              <p className="text-sm text-gray-500 italic mt-1">
                AI-powered emergency medicine clinical decision support
              </p>
            )}
          </div>

          {/* Right: Auth Button */}
          <div className="flex items-center">
            <AuthButton />
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="max-w-4xl w-full mt-8 space-y-8 pb-40">
        {/* Search Input - only show at top when not searched */}
        {!hasSearched && (
          <div className="w-full">
            <PromptInput
              question={question}
              setQuestion={setQuestion}
              onSubmit={handleSubmit}
              loading={loading}
              pinned={false}
            />
            
            {/* Quick Examples */}
            <div className="mt-6">
              <p className="text-sm text-gray-500 mb-3 text-center">Try asking:</p>
              <div className="flex flex-wrap justify-center gap-2">
                {[
                  "When should I give epinephrine?",
                  "ACLS algorithm for VFib",
                  "Trauma assessment steps",
                ].map((example) => (
                  <button
                    key={example}
                    onClick={() => {
                      setQuestion(example);
                    }}
                    className="px-4 py-2 text-sm bg-gray-100 text-gray-700 rounded-full hover:bg-gray-200 transition-colors"
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="w-full p-4 bg-red-50 border border-red-200 rounded-xl">
            <p className="text-red-600 text-sm">{error}</p>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="w-full flex flex-col items-center justify-center py-12">
            <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mb-4" />
            <p className="text-gray-500 text-sm">Searching protocols...</p>
          </div>
        )}

        {/* Response */}
        {response && !loading && (
          <div className="w-full space-y-6">
            {/* Query Time */}
            <div className="flex items-center justify-end text-xs text-gray-400">
              <Clock className="w-3 h-3 mr-1" />
              {(response.query_time_ms / 1000).toFixed(2)}s
            </div>

            {/* Answer */}
            <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
              <div className="prose prose-sm max-w-none">
                <ReactMarkdown
                  components={{
                    h1: ({ children }) => (
                      <h1 className="text-xl font-bold text-gray-900 mt-4 mb-2">{children}</h1>
                    ),
                    h2: ({ children }) => (
                      <h2 className="text-lg font-semibold text-gray-800 mt-6 mb-2">{children}</h2>
                    ),
                    h3: ({ children }) => (
                      <h3 className="text-base font-medium text-gray-700 mt-4 mb-1">{children}</h3>
                    ),
                    p: ({ children }) => (
                      <p className="text-gray-700 leading-relaxed mb-3">{children}</p>
                    ),
                    ul: ({ children }) => (
                      <ul className="list-disc list-inside space-y-1 mb-3 text-gray-700">{children}</ul>
                    ),
                    ol: ({ children }) => (
                      <ol className="list-decimal list-inside space-y-1 mb-3 text-gray-700">{children}</ol>
                    ),
                    li: ({ children }) => <li className="ml-2">{children}</li>,
                    strong: ({ children }) => (
                      <strong className="font-semibold text-gray-900">{children}</strong>
                    ),
                    code: ({ children }) => (
                      <code className="bg-gray-100 px-1.5 py-0.5 rounded text-sm font-mono text-blue-700">
                        {children}
                      </code>
                    ),
                  }}
                >
                  {response.answer}
                </ReactMarkdown>
              </div>
            </div>

            {/* Protocol Images */}
            {response.images && response.images.length > 0 && (
              <div className="space-y-4">
                <h3 className="text-sm font-medium text-gray-700 flex items-center">
                  <FileText className="w-4 h-4 mr-2" />
                  Protocol Images
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {response.images.map((img, idx) => (
                    <div
                      key={idx}
                      className="border border-gray-200 rounded-xl overflow-hidden bg-white shadow-sm hover:shadow-md transition-shadow"
                    >
                      <div className="p-2 bg-gray-50 border-b border-gray-100">
                        <p className="text-xs text-gray-500">
                          {img.protocol_id} - Page {img.page}
                        </p>
                      </div>
                      <img
                        src={img.url}
                        alt={`${img.protocol_id} page ${img.page}`}
                        className="w-full h-auto"
                        loading="lazy"
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Citations */}
            {uniqueCitations.length > 0 && (
              <div className="bg-gray-50 rounded-xl p-4 border border-gray-100">
                <h3 className="text-sm font-medium text-gray-700 mb-3">📚 Sources</h3>
                <div className="flex flex-wrap gap-2">
                  {uniqueCitations.map((citation, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center px-3 py-1 rounded-full text-xs bg-blue-100 text-blue-700"
                    >
                      {citation.protocol_id}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Pinned Input at Bottom (when searched) */}
      {hasSearched && (
        <PromptInput
          question={question}
          setQuestion={setQuestion}
          onSubmit={handleSubmit}
          loading={loading}
          pinned={true}
        />
      )}
    </main>
  );
}

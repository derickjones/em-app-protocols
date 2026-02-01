"use client";

import { useState } from "react";
import { Search, Clock, FileText, AlertCircle } from "lucide-react";
import ReactMarkdown from "react-markdown";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://em-protocol-api-930035889332.us-central1.run.app";

interface Citation {
  protocol_id: string;
  source_uri: string;
  relevance_score: number;
}

interface QueryResponse {
  answer: string;
  images: string[];
  citations: Citation[];
  query_time_ms: number;
}

export default function Home() {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
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

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const resetSearch = () => {
    setQuestion("");
    setResponse(null);
    setError(null);
    setHasSearched(false);
  };

  return (
    <main className="flex flex-col items-center min-h-screen px-4 py-8">
      {/* Header */}
      <div className="w-full max-w-3xl">
        <div className="flex flex-col items-center mb-8">
          <h1
            onClick={hasSearched ? resetSearch : undefined}
            className={`font-bold tracking-wide transition-all duration-300 ${
              hasSearched
                ? "text-xl cursor-pointer hover:text-blue-600"
                : "text-3xl md:text-4xl"
            }`}
          >
            🏥 EM Protocol Assistant
          </h1>
          {!hasSearched && (
            <p className="text-gray-500 mt-2 text-center">
              AI-powered emergency medicine protocol lookup
            </p>
          )}
        </div>

        {/* Search Input */}
        <form onSubmit={handleSubmit} className="relative mb-8">
          <div className="relative">
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a clinical question... (e.g., 'When should I give epinephrine in cardiac arrest?')"
              rows={2}
              className="w-full px-5 py-4 pr-14 text-gray-800 bg-gray-50 border-2 border-gray-200 rounded-3xl resize-none focus:outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100 transition-all duration-200 placeholder-gray-400 shadow-sm hover:shadow-md"
            />
            <button
              type="submit"
              disabled={loading || !question.trim()}
              className="absolute right-3 bottom-3 w-10 h-10 rounded-full bg-blue-600 text-white flex items-center justify-center hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-all duration-200 shadow-md hover:shadow-lg"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <Search className="w-5 h-5" />
              )}
            </button>
          </div>
        </form>

        {/* Quick Examples */}
        {!hasSearched && (
          <div className="mb-8">
            <p className="text-sm text-gray-500 mb-3">Try asking:</p>
            <div className="flex flex-wrap gap-2">
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
                  className="px-4 py-2 text-sm bg-white border border-gray-200 rounded-full hover:bg-gray-50 hover:border-gray-300 transition-all duration-200"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-red-800">Error</p>
              <p className="text-sm text-red-600">{error}</p>
            </div>
          </div>
        )}

        {/* Response Display */}
        {response && (
          <div className="space-y-6">
            {/* Response Time Badge */}
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Clock className="w-4 h-4" />
              <span>Response time: {response.query_time_ms}ms</span>
              {response.query_time_ms < 2000 && (
                <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded-full text-xs font-medium">
                  ⚡ Fast
                </span>
              )}
            </div>

            {/* Answer Card */}
            <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm">
              <div className="prose prose-gray max-w-none">
                <ReactMarkdown
                  components={{
                    h1: ({ children }) => (
                      <h1 className="text-xl font-bold text-gray-900 mb-4">{children}</h1>
                    ),
                    h2: ({ children }) => (
                      <h2 className="text-lg font-semibold text-gray-800 mt-6 mb-3">{children}</h2>
                    ),
                    p: ({ children }) => (
                      <p className="text-gray-700 leading-relaxed mb-3">{children}</p>
                    ),
                    ul: ({ children }) => (
                      <ul className="list-disc list-inside space-y-2 mb-4">{children}</ul>
                    ),
                    li: ({ children }) => (
                      <li className="text-gray-700">{children}</li>
                    ),
                    strong: ({ children }) => (
                      <strong className="font-semibold text-gray-900">{children}</strong>
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
                <h3 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
                  <FileText className="w-5 h-5" />
                  Related Protocol Images
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {response.images.map((imageUrl, index) => (
                    <div
                      key={index}
                      className="border border-gray-200 rounded-xl overflow-hidden bg-white shadow-sm hover:shadow-md transition-shadow"
                    >
                      <img
                        src={imageUrl}
                        alt={`Protocol diagram ${index + 1}`}
                        className="w-full h-auto"
                        loading="lazy"
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Citations */}
            {response.citations && response.citations.length > 0 && (
              <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
                <h3 className="text-sm font-medium text-gray-600 mb-2">Sources</h3>
                <ul className="space-y-1">
                  {response.citations.map((citation, index) => (
                    <li key={index} className="text-sm text-gray-500">
                      • {citation.protocol_id} (relevance: {(citation.relevance_score * 100).toFixed(0)}%)
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-12">
            <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mb-4" />
            <p className="text-gray-500">Searching protocols...</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="mt-auto pt-8 pb-4 text-center text-sm text-gray-400">
        <p>Powered by Vertex AI RAG + Gemini 2.0 Flash</p>
      </footer>
    </main>
  );
}

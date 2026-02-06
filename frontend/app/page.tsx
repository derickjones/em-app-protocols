"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, Mic, LogOut, ChevronDown } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useAuth } from "@/lib/auth-context";

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
  const [showUserMenu, setShowUserMenu] = useState(false);

  const { user, userProfile, loading: authLoading, emailVerified, signOut, getIdToken, resendVerificationEmail } = useAuth();
  const router = useRouter();
  const [verificationSent, setVerificationSent] = useState(false);

  const handleSubmit = async () => {
    if (!question.trim() || loading) return;
    
    if (user && !emailVerified) {
      setError("Please verify your email before searching. Check your inbox for a verification link.");
      return;
    }
    
    setLoading(true);
    setError(null);
    setHasSearched(true);

    try {
      const token = await getIdToken();
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch(`${API_URL}/query`, {
        method: "POST",
        headers,
        body: JSON.stringify({ query: question.trim() }),
      });
      if (!res.ok) {
        if (res.status === 401) {
          throw new Error("Please sign in to search protocols");
        } else if (res.status === 403) {
          const data = await res.json();
          throw new Error(data.detail || "Access denied");
        }
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

  const handleSignOut = async () => {
    await signOut();
    setShowUserMenu(false);
  };

  const handleResendVerification = async () => {
    try {
      await resendVerificationEmail();
      setVerificationSent(true);
      setTimeout(() => setVerificationSent(false), 5000);
    } catch {
      // Error handled in auth context
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="flex gap-1">
          <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
          <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
          <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
        </div>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-white text-gray-900 font-sans">
      {/* Header */}
      <div className="sticky top-0 z-50 w-full bg-white px-4 pt-4 border-b border-gray-100 pb-3">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          {/* Left: Menu */}
          <div className="flex items-center space-x-3">
            <button className="p-1">
              <div className="space-y-1">
                <span className="block w-5 h-0.5 bg-black" />
                <span className="block w-5 h-0.5 bg-black" />
                <span className="block w-5 h-0.5 bg-black" />
              </div>
            </button>
          </div>

          {/* Center: Title */}
          <div className="flex-1 flex flex-col items-center text-center">
            <h1
              onClick={resetSearch}
              className={`font-title font-bold tracking-wide transition-all duration-300 cursor-pointer ${
                hasSearched ? "text-xl" : "text-4xl"
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

          {/* Right: Auth */}
          <div className="flex items-center">
            {user ? (
              <div className="relative">
                <button
                  onClick={() => setShowUserMenu(!showUserMenu)}
                  className="flex items-center space-x-2 px-3 py-2 rounded-full border border-gray-200 hover:bg-gray-50 transition-colors"
                >
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-sm font-medium">
                    {user.email?.charAt(0).toUpperCase()}
                  </div>
                  <span className="text-sm text-gray-700 max-w-[100px] truncate hidden sm:block">
                    {userProfile?.orgName || user.email?.split("@")[0]}
                  </span>
                  <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${showUserMenu ? 'rotate-180' : ''}`} />
                </button>
                
                {showUserMenu && (
                  <>
                    <div 
                      className="fixed inset-0 z-10" 
                      onClick={() => setShowUserMenu(false)}
                    />
                    <div className="absolute right-0 mt-2 w-64 bg-white border border-gray-200 rounded-lg shadow-lg z-20">
                      <div className="px-4 py-3 border-b border-gray-100">
                        <p className="text-sm font-medium text-gray-900 truncate">{user.email}</p>
                        {userProfile?.orgName && (
                          <p className="text-xs text-gray-500 mt-1">{userProfile.orgName}</p>
                        )}
                        {userProfile?.bundleAccess && userProfile.bundleAccess.length > 0 && (
                          <p className="text-xs text-gray-400 mt-1">
                            Bundles: {userProfile.bundleAccess.join(", ")}
                          </p>
                        )}
                      </div>
                      <button
                        onClick={handleSignOut}
                        className="w-full flex items-center gap-2 px-4 py-3 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
                      >
                        <LogOut className="w-4 h-4" />
                        Sign out
                      </button>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <button
                onClick={() => router.push("/login")}
                className="flex items-center gap-2 px-4 py-2 rounded-full border border-gray-200 hover:bg-gray-50 transition-colors"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                <span className="text-sm text-gray-700">Sign in</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Email Verification Banner */}
      {user && !emailVerified && (
        <div className="bg-yellow-50 border-b border-yellow-100 px-4 py-3">
          <div className="max-w-4xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span className="text-yellow-800 text-sm">
                Please verify your email to search protocols.
              </span>
            </div>
            <button
              onClick={handleResendVerification}
              disabled={verificationSent}
              className="text-sm text-yellow-700 hover:text-yellow-900 font-medium disabled:text-yellow-500"
            >
              {verificationSent ? "Email sent!" : "Resend email"}
            </button>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="max-w-4xl mx-auto px-4 py-8">
        {!hasSearched ? (
          /* Initial Search View */
          <div className="flex flex-col items-center justify-center min-h-[60vh]">
            <div className="w-full max-w-2xl">
              {/* Input Box */}
              <div className="relative">
                <textarea
                  placeholder="Enter a clinical question or use the mic..."
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSubmit();
                    }
                  }}
                  rows={2}
                  className="w-full p-4 pl-5 pr-24 border-2 border-gray-300 rounded-3xl bg-gray-50 text-sm text-gray-800 shadow-lg resize-none focus:outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100 transition-all duration-200 hover:shadow-xl"
                />
                
                {/* Mic Button */}
                <button
                  title="Voice input"
                  className="absolute right-14 top-1/2 -translate-y-1/2 w-10 h-10 rounded-2xl bg-white text-gray-600 flex items-center justify-center hover:bg-gray-100 border-2 border-gray-300 transition-all duration-200 shadow-md hover:shadow-lg"
                >
                  <Mic className="w-4 h-4" />
                </button>

                {/* Submit Button */}
                <button
                  onClick={handleSubmit}
                  disabled={!question.trim() || loading}
                  title="Submit"
                  className="absolute right-2 top-1/2 -translate-y-1/2 w-10 h-10 rounded-2xl bg-black text-white flex items-center justify-center transition-all duration-200 hover:bg-gray-800 hover:scale-105 disabled:opacity-50 disabled:hover:scale-100 shadow-md hover:shadow-lg"
                >
                  {loading ? (
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2}>
                      <path d="M5 12h14M12 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </button>
              </div>
            </div>
          </div>
        ) : (
          /* Results View */
          <div className="space-y-6 pb-32">
            {/* User Question */}
            <div className="flex justify-end">
              <div className="bg-blue-50 border border-blue-100 rounded-2xl px-5 py-3 max-w-[80%]">
                <p className="text-gray-800">{question}</p>
              </div>
            </div>

            {/* Response */}
            {loading ? (
              <div className="flex items-center gap-3 p-4">
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
                <span className="text-sm text-gray-500">Searching protocols...</span>
              </div>
            ) : error ? (
              <div className="bg-red-50 border border-red-100 rounded-2xl px-5 py-4">
                <p className="text-red-700">{error}</p>
              </div>
            ) : response ? (
              <div className="space-y-6">
                {/* Query Time */}
                <div className="flex items-center gap-2 text-xs text-gray-400">
                  <Sparkles className="w-3 h-3 text-blue-500" />
                  <span>{response.query_time_ms}ms</span>
                </div>

                {/* Answer */}
                <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm">
                  <div className="prose prose-sm max-w-none text-gray-800 leading-relaxed">
                    <ReactMarkdown>{response.answer}</ReactMarkdown>
                  </div>
                </div>

                {/* Citations */}
                {response.citations.length > 0 && (
                  <div className="bg-gray-50 border border-gray-200 rounded-2xl p-5">
                    <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
                      <svg className="w-4 h-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      Source Protocols
                    </h3>
                    <div className="space-y-2">
                      {response.citations.map((cite, idx) => (
                        <a
                          key={idx}
                          href={cite.source_uri}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-3 px-4 py-3 rounded-xl text-blue-600 hover:bg-white hover:shadow-sm transition-all text-sm"
                        >
                          <span className="w-6 h-6 flex items-center justify-center bg-blue-100 rounded text-xs text-blue-700 font-medium">{idx + 1}</span>
                          <span className="flex-1">{cite.protocol_id.replace(/_/g, " ")}</span>
                          <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                          </svg>
                        </a>
                      ))}
                    </div>
                  </div>
                )}

                {/* Images */}
                {response.images.length > 0 && (
                  <div className="space-y-4">
                    <h3 className="text-sm font-semibold text-gray-700">Related Diagrams</h3>
                    <div className="grid gap-4">
                      {response.images.map((img, idx) => (
                        <div key={idx} className="bg-white rounded-2xl overflow-hidden border border-gray-200 shadow-sm">
                          <img
                            src={img.url}
                            alt={`Protocol diagram from ${img.protocol_id}, page ${img.page}`}
                            className="w-full"
                          />
                          <div className="px-4 py-3 text-xs text-gray-500 border-t border-gray-100">
                            {img.protocol_id} · Page {img.page}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : null}
          </div>
        )}
      </div>

      {/* Pinned Input (when searching) */}
      {hasSearched && (
        <div className="fixed bottom-0 left-0 right-0 bg-gradient-to-t from-white via-white to-transparent pt-8 pb-6 px-4">
          <div className="max-w-2xl mx-auto relative">
            <textarea
              placeholder="Ask a follow-up question..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit();
                }
              }}
              rows={2}
              className="w-full p-4 pl-5 pr-24 border-2 border-gray-300 rounded-3xl bg-gray-50 text-sm text-gray-800 shadow-lg resize-none focus:outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100 transition-all duration-200 hover:shadow-xl"
            />
            
            <button
              title="Voice input"
              className="absolute right-14 top-1/2 -translate-y-1/2 w-10 h-10 rounded-2xl bg-white text-gray-600 flex items-center justify-center hover:bg-gray-100 border-2 border-gray-300 transition-all duration-200 shadow-md hover:shadow-lg"
            >
              <Mic className="w-4 h-4" />
            </button>

            <button
              onClick={handleSubmit}
              disabled={!question.trim() || loading}
              title="Submit"
              className="absolute right-2 top-1/2 -translate-y-1/2 w-10 h-10 rounded-2xl bg-black text-white flex items-center justify-center transition-all duration-200 hover:bg-gray-800 hover:scale-105 disabled:opacity-50 disabled:hover:scale-100 shadow-md hover:shadow-lg"
            >
              {loading ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M5 12h14M12 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </button>
          </div>
        </div>
      )}
    </main>
  );
}

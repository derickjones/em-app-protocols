"use client";

/**
 * Login Page
 * Google sign-in with Mayo domain auto-approve.
 * Corporate fallback for Mayo laptops blocked by Imprivata (EMA-71).
 * Non-mayo users see a "Request Access" form under the Mayo Bundle section.
 */

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export default function LoginPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [showCorporate, setShowCorporate] = useState(false);
  const [corporateEmail, setCorporateEmail] = useState("");

  const { user, userProfile, signInWithGoogle, corporateLogin, error: authError } = useAuth();
  const router = useRouter();

  const handleGoogleSignIn = async () => {
    setLocalError(null);
    setIsLoading(true);
    try {
      await signInWithGoogle();
    } catch {
      // Error is set in auth context
    } finally {
      setIsLoading(false);
    }
  };

  const handleCorporateLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    setIsLoading(true);
    try {
      await corporateLogin(corporateEmail);
      router.push("/");
    } catch {
      // Error is set in auth context
    } finally {
      setIsLoading(false);
    }
  };

  // If user is signed in (Google or corporate), redirect to home
  if ((user || userProfile) && userProfile) {
    router.push("/");
    return null;
  }

  const displayError = localError || authError;

  return (
    <div className="min-h-screen bg-[#131314] flex items-center justify-center px-4">
      <div className="max-w-md w-full">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="font-title font-bold text-3xl text-white lowercase tracking-wide">
            emergency medicine app
          </h1>
          <p className="text-gray-400 mt-2">
            Sign in to continue
          </p>
        </div>

        {/* Card */}
        <div className="bg-[#1e1f20] rounded-2xl p-8 border border-white/10">
          {/* Error Display */}
          {displayError && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
              {displayError}
            </div>
          )}

          {/* Google Sign In */}
          <button
            onClick={handleGoogleSignIn}
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-3 py-3 bg-white hover:bg-gray-100 disabled:bg-white/50 text-gray-800 font-medium rounded-lg transition-colors"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            {isLoading && !showCorporate ? "Signing in..." : "Sign in with Google"}
          </button>

          {/* Info */}
          <p className="mt-4 text-center text-gray-400 text-sm">
            Sign in with your <span className="font-semibold text-blue-400">@mayo.edu</span> account for instant access to department protocols.
          </p>

          {/* Corporate Login Toggle */}
          <div className="mt-6 border-t border-white/10 pt-4">
            <button
              onClick={() => setShowCorporate(!showCorporate)}
              className="w-full text-center text-sm text-gray-500 hover:text-gray-300 transition-colors"
            >
              {showCorporate ? "Hide" : "Or sign in with email"}
            </button>

            {showCorporate && (
              <form onSubmit={handleCorporateLogin} className="mt-4 space-y-3">
                <p className="text-xs text-gray-500">
                  Enter your email to sign in without Google.
                </p>
                <input
                  type="email"
                  placeholder="your.name@mayo.edu"
                  value={corporateEmail}
                  onChange={(e) => setCorporateEmail(e.target.value)}
                  required
                  className="w-full px-4 py-3 bg-[#131314] border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 text-sm"
                />
                <button
                  type="submit"
                  disabled={isLoading || !corporateEmail}
                  className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 text-white font-medium rounded-lg transition-colors text-sm"
                >
                  {isLoading && showCorporate ? "Signing in..." : "Sign in with email"}
                </button>
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

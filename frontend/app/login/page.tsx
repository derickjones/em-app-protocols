"use client";

/**
 * Login Page
 * Google-only sign-in with Mayo domain auto-approve.
 * Non-mayo users see a "Request Access" form under the Mayo Bundle section.
 */

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export default function LoginPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Request access form state
  const [requestName, setRequestName] = useState("");
  const [requestEmail, setRequestEmail] = useState("");
  const [requestError, setRequestError] = useState<string | null>(null);
  const [requestLoading, setRequestLoading] = useState(false);

  const { user, userProfile, signInWithGoogle, submitAccessRequest, error: authError } = useAuth();
  const router = useRouter();

  const handleGoogleSignIn = async () => {
    setLocalError(null);
    setIsLoading(true);
    try {
      await signInWithGoogle();
      // After sign-in, check if auto-approved (mayo email) and redirect
      // The auth context will update userProfile, and the useEffect below handles redirect
    } catch {
      // Error is set in auth context
    } finally {
      setIsLoading(false);
    }
  };

  const handleRequestAccess = async (e: React.FormEvent) => {
    e.preventDefault();
    setRequestError(null);
    setSuccessMessage(null);

    // Validate @mayo.edu email
    if (!requestEmail.toLowerCase().trim().endsWith("@mayo.edu")) {
      setRequestError("Please enter your @mayo.edu email address");
      return;
    }

    if (!requestName.trim()) {
      setRequestError("Please enter your full name");
      return;
    }

    setRequestLoading(true);
    try {
      const result = await submitAccessRequest(requestName.trim(), requestEmail.trim());
      setSuccessMessage(result.message || "Your request has been submitted. Please allow 3-5 business days for review.");
      setRequestName("");
      setRequestEmail("");
    } catch (err) {
      setRequestError(err instanceof Error ? err.message : "Failed to submit request");
    } finally {
      setRequestLoading(false);
    }
  };

  // If user is signed in and has access, redirect to home
  if (user && userProfile?.accessStatus === "approved") {
    router.push("/");
    return null;
  }

  const displayError = localError || authError;
  const isSignedIn = !!user;
  const isPending = userProfile?.accessStatus === "pending";
  const isDenied = userProfile?.accessStatus === "denied";
  const needsAccess = isSignedIn && userProfile?.accessStatus !== "approved";

  return (
    <div className="min-h-screen bg-[#131314] flex items-center justify-center px-4">
      <div className="max-w-md w-full">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="font-title font-bold text-3xl text-white lowercase tracking-wide">
            emergency medicine app
          </h1>
          <p className="text-gray-400 mt-2">
            {isSignedIn ? `Signed in as ${user?.email}` : "Sign in to continue"}
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

          {/* Success Display */}
          {successMessage && (
            <div className="mb-4 p-3 bg-green-500/10 border border-green-500/20 rounded-lg text-green-400 text-sm">
              {successMessage}
            </div>
          )}

          {!isSignedIn ? (
            <>
              {/* Google Sign In — Primary */}
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
                {isLoading ? "Signing in..." : "Sign in with Google"}
              </button>

              {/* Info */}
              <p className="mt-4 text-center text-gray-500 text-xs">
                Mayo Clinic staff: use your @mayo.edu Google account for instant access.
              </p>
            </>
          ) : isPending ? (
            /* Pending approval state */
            <div className="text-center py-4">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-yellow-500/10 flex items-center justify-center">
                <svg className="w-8 h-8 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h2 className="text-lg font-medium text-white mb-2">Request Pending</h2>
              <p className="text-gray-400 text-sm">
                Your access request is being reviewed. Please allow 3-5 business days for approval.
              </p>
              <p className="text-gray-500 text-xs mt-3">
                Once approved, sign back in and you&apos;ll have full access.
              </p>
              <button
                onClick={async () => {
                  const { signOut } = await import("firebase/auth");
                  const { auth } = await import("@/lib/firebase");
                  await signOut(auth);
                  window.location.reload();
                }}
                className="mt-4 text-sm text-[#8ab4f8] hover:text-[#aecbfa] transition-colors"
              >
                Sign out
              </button>
            </div>
          ) : isDenied ? (
            /* Denied state */
            <div className="text-center py-4">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-red-500/10 flex items-center justify-center">
                <svg className="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
              <h2 className="text-lg font-medium text-white mb-2">Access Denied</h2>
              <p className="text-gray-400 text-sm">
                Your access request was not approved. If you believe this is an error, please contact the site administrator.
              </p>
              <button
                onClick={async () => {
                  const { signOut } = await import("firebase/auth");
                  const { auth } = await import("@/lib/firebase");
                  await signOut(auth);
                  window.location.reload();
                }}
                className="mt-4 text-sm text-[#8ab4f8] hover:text-[#aecbfa] transition-colors"
              >
                Sign out
              </button>
            </div>
          ) : needsAccess ? (
            /* Signed in with non-mayo account — show request access form */
            <>
              {/* Mayo Bundle Section */}
              <div className="border-t border-white/10 pt-6">
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center">
                    <svg className="w-4 h-4 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                    </svg>
                  </div>
                  <h2 className="text-lg font-medium text-white">Mayo Clinic Access</h2>
                </div>

                <p className="text-gray-400 text-sm mb-4">
                  This app is for Mayo Clinic staff. Request access by providing your Mayo email and name. An administrator will review your request.
                </p>

                {/* Request Access Form */}
                <form onSubmit={handleRequestAccess} className="space-y-4">
                  {requestError && (
                    <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
                      {requestError}
                    </div>
                  )}

                  <div>
                    <label htmlFor="requestName" className="block text-sm text-gray-400 mb-1">
                      Full Name
                    </label>
                    <input
                      id="requestName"
                      type="text"
                      value={requestName}
                      onChange={(e) => setRequestName(e.target.value)}
                      placeholder="Dr. Jane Smith"
                      required
                      className="w-full px-4 py-3 bg-[#131314] border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors"
                    />
                  </div>

                  <div>
                    <label htmlFor="requestEmail" className="block text-sm text-gray-400 mb-1">
                      Mayo Email
                    </label>
                    <input
                      id="requestEmail"
                      type="email"
                      value={requestEmail}
                      onChange={(e) => setRequestEmail(e.target.value)}
                      placeholder="jane.smith@mayo.edu"
                      required
                      className="w-full px-4 py-3 bg-[#131314] border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors"
                    />
                    <p className="text-xs text-gray-500 mt-1">Must be a @mayo.edu email address</p>
                  </div>

                  <button
                    type="submit"
                    disabled={requestLoading}
                    className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 text-white font-medium rounded-lg transition-colors"
                  >
                    {requestLoading ? "Submitting..." : "Request Access"}
                  </button>
                </form>

                <p className="mt-4 text-center text-gray-500 text-xs">
                  Please allow 3-5 business days for approval.
                </p>
              </div>

              {/* Sign out option */}
              <div className="mt-6 pt-4 border-t border-white/10 text-center">
                <button
                  onClick={async () => {
                    const { signOut } = await import("firebase/auth");
                    const { auth } = await import("@/lib/firebase");
                    await signOut(auth);
                    window.location.reload();
                  }}
                  className="text-sm text-gray-500 hover:text-gray-300 transition-colors"
                >
                  Sign in with a different account
                </button>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}

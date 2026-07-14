"use client";

/**
 * Auth Context Provider
 * Manages Firebase authentication state across the app
 * 
 * Auth flow:
 * - @mayo.edu Google sign-in → auto-approved, full access
 * - Non-mayo Google sign-in → authenticated but no app access
 *   → can submit access request (name + @mayo.edu email)
 *   → owner approves at /owner → user gets access
 * 
 * Corporate fallback (EMA-71):
 * - Passwordless email login for environments where Google
 *   popup/redirect is blocked by Imprivata or browser policy.
 *   Backend creates Firebase user & exchanges tokens server-side,
 *   bypassing blocked googleapis.com domains entirely.
 */

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import {
  User,
  onAuthStateChanged,
  signInWithPopup,
  signInWithRedirect,
  getRedirectResult,
  signOut as firebaseSignOut,
} from "firebase/auth";
import { auth, googleProvider } from "./firebase";
import { Capacitor } from "@capacitor/core";

interface UserProfile {
  uid: string;
  email: string | null;
  enterpriseId: string | null;
  enterpriseName: string | null;
  role: "user" | "admin" | "super_admin";
  edAccess: string[];
  accessStatus: "approved" | "pending" | "denied" | "no_access";
}

interface AuthContextType {
  user: User | null;
  userProfile: UserProfile | null;
  loading: boolean;
  error: string | null;
  isSignedIn: boolean;
  isMayoUser: boolean;
  hasAccess: boolean;
  signInWithGoogle: () => Promise<void>;
  corporateLogin: (email: string) => Promise<void>;
  signOut: () => Promise<void>;
  getIdToken: () => Promise<string | null>;
  submitAccessRequest: (name: string, mayoEmail: string) => Promise<{ status: string; message: string }>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://em-protocol-api-930035889332.us-central1.run.app";

// Keys for storing corporate login tokens in localStorage
const CORPORATE_TOKEN_KEY = "em_corporate_id_token";
const CORPORATE_REFRESH_KEY = "em_corporate_refresh_token";
const CORPORATE_EXPIRY_KEY = "em_corporate_token_expiry";
const CORPORATE_PROFILE_KEY = "em_corporate_profile";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Track whether this session is a corporate (server-token) login
  const [isCorporateSession, setIsCorporateSession] = useState(false);

  // ----- Corporate token helpers -----

  const storeCorporateTokens = (idToken: string, refreshToken: string, expiresIn: string, profile: UserProfile) => {
    const expiryMs = Date.now() + parseInt(expiresIn, 10) * 1000;
    localStorage.setItem(CORPORATE_TOKEN_KEY, idToken);
    localStorage.setItem(CORPORATE_REFRESH_KEY, refreshToken);
    localStorage.setItem(CORPORATE_EXPIRY_KEY, expiryMs.toString());
    localStorage.setItem(CORPORATE_PROFILE_KEY, JSON.stringify(profile));
  };

  const clearCorporateTokens = () => {
    localStorage.removeItem(CORPORATE_TOKEN_KEY);
    localStorage.removeItem(CORPORATE_REFRESH_KEY);
    localStorage.removeItem(CORPORATE_EXPIRY_KEY);
    localStorage.removeItem(CORPORATE_PROFILE_KEY);
  };

  const getCorporateIdToken = (): string | null => {
    return localStorage.getItem(CORPORATE_TOKEN_KEY);
  };

  const getCorporateRefreshToken = (): string | null => {
    return localStorage.getItem(CORPORATE_REFRESH_KEY);
  };

  const isCorporateTokenExpired = (): boolean => {
    const expiry = localStorage.getItem(CORPORATE_EXPIRY_KEY);
    if (!expiry) return true;
    // Refresh 5 minutes before actual expiry
    return Date.now() > parseInt(expiry, 10) - 5 * 60 * 1000;
  };

  const refreshCorporateToken = async (): Promise<string | null> => {
    const refreshToken = getCorporateRefreshToken();
    if (!refreshToken) return null;

    try {
      const resp = await fetch(`${API_URL}/auth/refresh-token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refreshToken }),
      });

      if (!resp.ok) {
        // Refresh failed — force re-login
        clearCorporateTokens();
        setIsCorporateSession(false);
        setUserProfile(null);
        return null;
      }

      const data = await resp.json();
      const expiryMs = Date.now() + parseInt(data.expiresIn, 10) * 1000;
      localStorage.setItem(CORPORATE_TOKEN_KEY, data.idToken);
      localStorage.setItem(CORPORATE_REFRESH_KEY, data.refreshToken);
      localStorage.setItem(CORPORATE_EXPIRY_KEY, expiryMs.toString());
      return data.idToken;
    } catch {
      return null;
    }
  };

  // ----- Shared helpers -----

  const fetchUserProfile = async (firebaseUser: User): Promise<UserProfile | null> => {
    try {
      const token = await firebaseUser.getIdToken();
      
      const response = await fetch(`${API_URL}/auth/me`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        return await response.json();
      } else if (response.status === 404) {
        return null;
      }
      return null;
    } catch (err) {
      console.error("Failed to fetch user profile:", err);
      return null;
    }
  };

  const fetchProfileWithToken = async (idToken: string): Promise<UserProfile | null> => {
    try {
      const response = await fetch(`${API_URL}/auth/me`, {
        headers: {
          Authorization: `Bearer ${idToken}`,
        },
      });

      if (response.ok) {
        return await response.json();
      }
      return null;
    } catch (err) {
      console.error("Failed to fetch user profile:", err);
      return null;
    }
  };

  const refreshProfile = async () => {
    if (isCorporateSession) {
      const token = await getIdToken();
      if (token) {
        const profile = await fetchProfileWithToken(token);
        setUserProfile(profile);
        if (profile) {
          localStorage.setItem(CORPORATE_PROFILE_KEY, JSON.stringify(profile));
        }
      }
    } else if (user) {
      const profile = await fetchUserProfile(user);
      setUserProfile(profile);
    }
  };

  // ----- Init: restore corporate session or listen for Firebase auth -----

  useEffect(() => {
    // Check for existing corporate session first
    const savedToken = getCorporateIdToken();
    const savedProfile = localStorage.getItem(CORPORATE_PROFILE_KEY);

    if (savedToken && savedProfile) {
      // Restore corporate session
      setIsCorporateSession(true);
      setUserProfile(JSON.parse(savedProfile));
      setLoading(false);

      // Refresh token if needed (async, non-blocking)
      if (isCorporateTokenExpired()) {
        refreshCorporateToken().then(async (newToken) => {
          if (newToken) {
            const profile = await fetchProfileWithToken(newToken);
            if (profile) {
              setUserProfile(profile);
              localStorage.setItem(CORPORATE_PROFILE_KEY, JSON.stringify(profile));
            }
          }
        });
      }
      // Don't return early — always set up the Firebase listener below
      // so that switching from corporate → Google sign-in works seamlessly
    }

    // Redirect-based web OAuth doesn't apply on native (Phase 3 replaces
    // sign-in with a native plugin), so skip it there.
    if (!Capacitor.isNativePlatform()) {
      getRedirectResult(auth)
        .then(async (result) => {
          if (result?.user) {
            const profile = await fetchUserProfile(result.user);
            setUserProfile(profile);
          }
        })
        .catch((err) => {
          console.error("Redirect sign-in error:", err);
          setError(err instanceof Error ? err.message : "Sign in failed after redirect");
        });
    }

    // Firebase JS Auth's onAuthStateChanged never fires under the
    // capacitor://localhost origin (confirmed: reproduces with a bare
    // Firebase instance loaded independently of this app's bundle — not an
    // app bug). Don't block rendering on it here; Phase 3 replaces native
    // auth state entirely via a native plugin bridge.
    if (Capacitor.isNativePlatform() && !savedToken) {
      setLoading(false);
    }

    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      setUser(firebaseUser);
      
      if (firebaseUser) {
        // If we had a corporate session but now have a real Firebase user,
        // switch over to standard Firebase auth
        if (getCorporateIdToken()) {
          clearCorporateTokens();
          setIsCorporateSession(false);
        }
        const profile = await fetchUserProfile(firebaseUser);
        setUserProfile(profile);
      } else if (!getCorporateIdToken()) {
        // Only clear profile if there's no corporate session either
        setUserProfile(null);
      }
      
      setLoading(false);
    });

    return () => unsubscribe();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ----- Auth methods -----

  const signInWithGoogle = async () => {
    setError(null);

    // Clear any existing corporate session so Google auth takes over cleanly
    if (isCorporateSession) {
      clearCorporateTokens();
      setIsCorporateSession(false);
    }

    try {
      const result = await signInWithPopup(auth, googleProvider);
      const profile = await fetchUserProfile(result.user);
      setUserProfile(profile);
    } catch (err: unknown) {
      const code = (err as { code?: string })?.code;
      const popupFailureCodes = [
        "auth/popup-closed-by-user",
        "auth/popup-blocked",
        "auth/cancelled-popup-request",
      ];
      if (code && popupFailureCodes.includes(code)) {
        await signInWithRedirect(auth, googleProvider);
        return;
      }
      const message = err instanceof Error ? err.message : "Google sign in failed";
      setError(message);
      throw err;
    }
  };

  const corporateLogin = async (email: string) => {
    setError(null);
    try {
      const resp = await fetch(`${API_URL}/auth/corporate-login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      if (!resp.ok) {
        const data = await resp.json().catch(() => ({ detail: "Login failed" }));
        throw new Error(data.detail || "Corporate login failed");
      }

      const data = await resp.json();
      
      // Store tokens locally (Firebase SDK is bypassed for corporate users)
      storeCorporateTokens(data.idToken, data.refreshToken, data.expiresIn, data.user);
      setIsCorporateSession(true);
      setUserProfile(data.user);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Corporate login failed";
      setError(message);
      throw err;
    }
  };

  const signOut = async () => {
    if (isCorporateSession) {
      clearCorporateTokens();
      setIsCorporateSession(false);
    } else {
      await firebaseSignOut(auth);
    }
    setUser(null);
    setUserProfile(null);
  };

  const getIdToken = async (): Promise<string | null> => {
    // Corporate session: use stored token, refresh if needed
    if (isCorporateSession) {
      if (isCorporateTokenExpired()) {
        return refreshCorporateToken();
      }
      return getCorporateIdToken();
    }
    // Standard Firebase session
    if (!user) return null;
    return user.getIdToken();
  };

  const submitAccessRequest = async (name: string, mayoEmail: string): Promise<{ status: string; message: string }> => {
    const token = await getIdToken();
    if (!token) throw new Error("Must be signed in to submit access request");
    
    const response = await fetch(`${API_URL}/access-requests`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ name, mayo_email: mayoEmail }),
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.detail || "Failed to submit access request");
    }
    
    // Refresh profile to get updated access_status
    await refreshProfile();
    
    return data;
  };

  // Derived state — corporate users count as "signed in" even without a Firebase User object
  const isSignedIn = !!user || isCorporateSession;
  const isMayoUser = (user?.email?.endsWith("@mayo.edu") ?? false) || (userProfile?.email?.endsWith("@mayo.edu") ?? false);
  const hasAccess = userProfile?.accessStatus === "approved" || false;

  return (
    <AuthContext.Provider
      value={{
        user,
        userProfile,
        loading,
        error,
        isSignedIn,
        isMayoUser,
        hasAccess,
        signInWithGoogle,
        corporateLogin,
        signOut,
        getIdToken,
        submitAccessRequest,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

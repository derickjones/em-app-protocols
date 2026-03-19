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
  isMayoUser: boolean;
  hasAccess: boolean;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
  getIdToken: () => Promise<string | null>;
  submitAccessRequest: (name: string, mayoEmail: string) => Promise<{ status: string; message: string }>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://em-protocol-api-930035889332.us-central1.run.app";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch user profile from backend after auth
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

  const refreshProfile = async () => {
    if (user) {
      const profile = await fetchUserProfile(user);
      setUserProfile(profile);
    }
  };

  useEffect(() => {
    // Handle redirect result (for corporate environments where popups are blocked)
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

    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      setUser(firebaseUser);
      
      if (firebaseUser) {
        const profile = await fetchUserProfile(firebaseUser);
        setUserProfile(profile);
      } else {
        setUserProfile(null);
      }
      
      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  const signInWithGoogle = async () => {
    setError(null);
    try {
      const result = await signInWithPopup(auth, googleProvider);
      const profile = await fetchUserProfile(result.user);
      setUserProfile(profile);
    } catch (err: unknown) {
      // If popup is blocked or closed by corporate policy, fall back to redirect.
      // Corporate environments (e.g. Mayo laptops) can trigger several different
      // error codes depending on how the popup is prevented. See EMA-71.
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

  const signOut = async () => {
    await firebaseSignOut(auth);
    setUserProfile(null);
  };

  const getIdToken = async (): Promise<string | null> => {
    if (!user) return null;
    return user.getIdToken();
  };

  const submitAccessRequest = async (name: string, mayoEmail: string): Promise<{ status: string; message: string }> => {
    if (!user) throw new Error("Must be signed in to submit access request");
    
    const token = await user.getIdToken();
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
    const profile = await fetchUserProfile(user);
    setUserProfile(profile);
    
    return data;
  };

  // Derived state
  const isMayoUser = user?.email?.endsWith("@mayo.edu") ?? false;
  const hasAccess = userProfile?.accessStatus === "approved" || false;

  return (
    <AuthContext.Provider
      value={{
        user,
        userProfile,
        loading,
        error,
        isMayoUser,
        hasAccess,
        signInWithGoogle,
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

"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, LogOut, ChevronDown, ArrowUp, Mic, Plus, MessageSquare, X, Trash2, Building2, Check, Heart, Syringe, Activity, Stethoscope, Zap, Brain, Bone, ShieldPlus, Cross, Pill, Crown, Shield } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useAuth } from "@/lib/auth-context";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://em-protocol-api-930035889332.us-central1.run.app";
const STORAGE_KEY = "em-protocol-conversations";
const THEME_KEY = "em-protocol-theme";
const BUNDLE_KEY = "em-protocol-selected-bundles";
const HOSPITAL_KEY = "em-protocol-selected-hospital";

interface QueryResponse {
  answer: string;
  images: { page: number; url: string; protocol_id: string }[];
  citations: { protocol_id: string; source_uri: string; relevance_score: number }[];
  query_time_ms: number;
}

interface Conversation {
  id: string;
  title: string;
  timestamp: string; // Changed to string for JSON serialization
  question: string;
  response: QueryResponse | null;
}

interface HospitalData {
  [bundle: string]: unknown[];
}

interface AllHospitals {
  [hospital: string]: HospitalData;
}

export default function Home() {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [darkMode, setDarkMode] = useState(false);
  
  // Hospital/Bundle selection state
  const [allHospitals, setAllHospitals] = useState<AllHospitals>({});
  const [selectedBundles, setSelectedBundles] = useState<Set<string>>(new Set());
  const [expandedHospitals, setExpandedHospitals] = useState<Set<string>>(new Set());
  const [showBundleSelector, setShowBundleSelector] = useState(false);
  const [selectedHospital, setSelectedHospital] = useState<string>("");
  const [showHospitalDropdown, setShowHospitalDropdown] = useState(false);

  const { user, userProfile, loading: authLoading, emailVerified, signOut, getIdToken, resendVerificationEmail } = useAuth();
  const router = useRouter();
  const [verificationSent, setVerificationSent] = useState(false);

  // Load theme from localStorage on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const savedTheme = localStorage.getItem(THEME_KEY);
      if (savedTheme) {
        setDarkMode(savedTheme === 'dark');
      } else {
        // Check system preference
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        setDarkMode(prefersDark);
      }
    }
  }, []);

  // Save theme to localStorage and update document class
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(THEME_KEY, darkMode ? 'dark' : 'light');
      if (darkMode) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    }
  }, [darkMode]);

  // Load conversations from localStorage on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          setConversations(parsed);
        } catch (e) {
          console.error("Failed to parse saved conversations:", e);
        }
      }
    }
  }, []);

  // Save conversations to localStorage when they change
  useEffect(() => {
    if (typeof window !== 'undefined' && conversations.length > 0) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
    }
  }, [conversations]);

  // Fetch hospitals and bundles
  const fetchHospitals = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/hospitals`);
      if (res.ok) {
        const data = await res.json();
        const hospitals = data.hospitals || {};
        setAllHospitals(hospitals);
        
        // Auto-select hospital if none selected
        const hospitalNames = Object.keys(hospitals);
        if (hospitalNames.length > 0) {
          const savedHospital = localStorage.getItem(HOSPITAL_KEY);
          if (savedHospital && hospitalNames.includes(savedHospital)) {
            setSelectedHospital(savedHospital);
          } else {
            setSelectedHospital(hospitalNames[0]);
          }
        }
      }
    } catch (err) {
      console.error("Failed to fetch hospitals:", err);
    }
  }, []);

  // Load hospitals on mount
  useEffect(() => {
    fetchHospitals();
  }, [fetchHospitals]);

  // Load selected bundles from localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(BUNDLE_KEY);
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          setSelectedBundles(new Set(parsed));
        } catch (e) {
          console.error("Failed to parse saved bundles:", e);
        }
      }
    }
  }, []);

  // Save selected bundles to localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(BUNDLE_KEY, JSON.stringify(Array.from(selectedBundles)));
    }
  }, [selectedBundles]);

  // Save selected hospital to localStorage
  useEffect(() => {
    if (typeof window !== 'undefined' && selectedHospital) {
      localStorage.setItem(HOSPITAL_KEY, selectedHospital);
    }
  }, [selectedHospital]);

  // Toggle hospital expansion in selector
  const toggleHospitalExpand = (hospital: string) => {
    setExpandedHospitals(prev => {
      const next = new Set(prev);
      if (next.has(hospital)) {
        next.delete(hospital);
      } else {
        next.add(hospital);
      }
      return next;
    });
  };

  // Get icon for bundle based on name or index
  const getBundleIcon = (bundleName: string, index: number, isSelected: boolean) => {
    const iconClass = `w-4 h-4 ${isSelected ? 'text-white' : ''}`;
    
    // Match bundle names to relevant icons
    const nameLower = bundleName.toLowerCase();
    if (nameLower.includes('cardiac') || nameLower.includes('acls') || nameLower.includes('heart')) {
      return <Heart className={`${iconClass} ${!isSelected ? 'text-red-500' : ''}`} />;
    }
    if (nameLower.includes('trauma') || nameLower.includes('injury')) {
      return <Zap className={`${iconClass} ${!isSelected ? 'text-orange-500' : ''}`} />;
    }
    if (nameLower.includes('neuro') || nameLower.includes('stroke') || nameLower.includes('brain')) {
      return <Brain className={`${iconClass} ${!isSelected ? 'text-purple-500' : ''}`} />;
    }
    if (nameLower.includes('ortho') || nameLower.includes('fracture') || nameLower.includes('bone')) {
      return <Bone className={`${iconClass} ${!isSelected ? 'text-gray-400' : ''}`} />;
    }
    if (nameLower.includes('peds') || nameLower.includes('pediatric')) {
      return <ShieldPlus className={`${iconClass} ${!isSelected ? 'text-pink-500' : ''}`} />;
    }
    if (nameLower.includes('med') || nameLower.includes('pharm') || nameLower.includes('drug')) {
      return <Pill className={`${iconClass} ${!isSelected ? 'text-green-500' : ''}`} />;
    }
    if (nameLower.includes('procedure') || nameLower.includes('injection')) {
      return <Syringe className={`${iconClass} ${!isSelected ? 'text-cyan-500' : ''}`} />;
    }
    
    // Cycle through icons for generic bundles
    const icons = [
      <Activity key="activity" className={`${iconClass} ${!isSelected ? 'text-red-500' : ''}`} />,
      <Stethoscope key="stethoscope" className={`${iconClass} ${!isSelected ? 'text-blue-500' : ''}`} />,
      <Heart key="heart" className={`${iconClass} ${!isSelected ? 'text-red-500' : ''}`} />,
      <Cross key="cross" className={`${iconClass} ${!isSelected ? 'text-emerald-500' : ''}`} />,
      <Zap key="zap" className={`${iconClass} ${!isSelected ? 'text-yellow-500' : ''}`} />,
      <Brain key="brain" className={`${iconClass} ${!isSelected ? 'text-purple-500' : ''}`} />,
    ];
    return icons[index % icons.length];
  };

  // Toggle bundle selection
  const toggleBundleSelection = (bundleKey: string) => {
    setSelectedBundles(prev => {
      const next = new Set(prev);
      if (next.has(bundleKey)) {
        next.delete(bundleKey);
      } else {
        next.add(bundleKey);
      }
      return next;
    });
  };

  // Select all bundles for a hospital
  const selectAllHospitalBundles = (hospital: string) => {
    const bundles = Object.keys(allHospitals[hospital] || {});
    setSelectedBundles(prev => {
      const next = new Set(prev);
      bundles.forEach(bundle => next.add(`${hospital}/${bundle}`));
      return next;
    });
  };

  // Deselect all bundles for a hospital
  const deselectAllHospitalBundles = (hospital: string) => {
    setSelectedBundles(prev => {
      const next = new Set(prev);
      Array.from(next).forEach(key => {
        if (key.startsWith(`${hospital}/`)) {
          next.delete(key);
        }
      });
      return next;
    });
  };

  const handleSubmit = async () => {
    if (!question.trim() || loading) return;
    
    // Require login to search
    if (!user) {
      router.push("/login");
      return;
    }
    
    if (user && !emailVerified) {
      setError("Please verify your email before searching. Check your inbox for a verification link.");
      return;
    }
    
    setLoading(true);
    setError(null);
    setHasSearched(true);

    // Create a new conversation if we don't have one
    const conversationId = currentConversationId || `conv-${Date.now()}`;
    if (!currentConversationId) {
      setCurrentConversationId(conversationId);
    }

    try {
      const token = await getIdToken();
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch(`${API_URL}/query`, {
        method: "POST",
        headers,
        body: JSON.stringify({ 
          query: question.trim(),
          bundle_ids: selectedBundles.size > 0 ? Array.from(selectedBundles) : ["all"],
          include_images: true
        }),
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

      // Save conversation to history
      const newConversation: Conversation = {
        id: conversationId,
        title: question.trim().slice(0, 50) + (question.length > 50 ? "..." : ""),
        timestamp: new Date().toISOString(),
        question: question.trim(),
        response: data,
      };
      
      setConversations(prev => {
        const existing = prev.findIndex(c => c.id === conversationId);
        if (existing >= 0) {
          const updated = [...prev];
          updated[existing] = newConversation;
          return updated;
        }
        return [newConversation, ...prev];
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch response");
      setResponse(null);
    } finally {
      setLoading(false);
    }
  };

  const startNewConversation = () => {
    setQuestion("");
    setResponse(null);
    setError(null);
    setHasSearched(false);
    setCurrentConversationId(null);
    setSidebarOpen(false);
  };

  const loadConversation = (conversation: Conversation) => {
    setQuestion(conversation.question);
    setResponse(conversation.response);
    setHasSearched(true);
    setCurrentConversationId(conversation.id);
    setError(null);
    setSidebarOpen(false);
  };

  const deleteConversation = (conversationId: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent loading the conversation when clicking delete
    setConversations(prev => {
      const updated = prev.filter(c => c.id !== conversationId);
      // Update localStorage
      if (typeof window !== 'undefined') {
        if (updated.length === 0) {
          localStorage.removeItem(STORAGE_KEY);
        } else {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
        }
      }
      return updated;
    });
    // If we deleted the current conversation, reset the view
    if (currentConversationId === conversationId) {
      resetSearch();
    }
  };

  const resetSearch = () => {
    setQuestion("");
    setResponse(null);
    setError(null);
    setHasSearched(false);
    setCurrentConversationId(null);
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
    <div className={`min-h-screen font-sans flex ${darkMode ? 'bg-black text-gray-100' : 'bg-white text-gray-900'}`}>
      {/* Sidebar Overlay - mobile only */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/20 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`fixed inset-y-0 left-0 z-50 w-72 border-r transform transition-all duration-300 ease-in-out ${
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      } flex flex-col ${darkMode ? 'bg-neutral-900 border-neutral-800' : 'bg-gray-50 border-gray-200'}`}>
        {/* Sidebar Header */}
        <div className={`p-4 border-b ${darkMode ? 'border-neutral-800' : 'border-gray-200'}`}>
          <div className="flex items-center justify-between mb-4">
            <h2 className={`text-lg font-semibold ${darkMode ? 'text-gray-100' : 'text-gray-800'}`}>Conversations</h2>
            <button 
              onClick={() => setSidebarOpen(false)}
              className={`p-1 rounded ${darkMode ? 'hover:bg-neutral-800' : 'hover:bg-gray-200'}`}
            >
              <X className={`w-5 h-5 ${darkMode ? 'text-gray-400' : 'text-gray-600'}`} />
            </button>
          </div>
          <button
            onClick={startNewConversation}
            className={`w-full flex items-center gap-2 px-4 py-3 rounded-xl transition-colors shadow-md ${
              darkMode ? 'bg-neutral-800 text-white hover:bg-neutral-700' : 'bg-black text-white hover:bg-gray-800'
            }`}
          >
            <Plus className="w-5 h-5" />
            <span className="font-medium">New Conversation</span>
          </button>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {conversations.length === 0 ? (
            <div className={`text-center py-8 text-sm ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
              <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>No conversations yet</p>
              <p className="text-xs mt-1">Start a new conversation above</p>
            </div>
          ) : (
            conversations.map((conv) => (
              <div
                key={conv.id}
                onClick={() => loadConversation(conv)}
                className={`group w-full text-left px-4 py-3 rounded-xl transition-colors cursor-pointer ${
                  currentConversationId === conv.id
                    ? darkMode ? 'bg-neutral-800 border border-neutral-700' : 'bg-blue-100 border border-blue-200'
                    : darkMode ? 'hover:bg-neutral-800 border border-transparent' : 'hover:bg-gray-100 border border-transparent'
                }`}
              >
                <div className="flex items-start gap-3">
                  <MessageSquare className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                    currentConversationId === conv.id ? 'text-blue-500' : darkMode ? 'text-gray-500' : 'text-gray-400'
                  }`} />
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-medium truncate ${
                      currentConversationId === conv.id 
                        ? darkMode ? 'text-blue-300' : 'text-blue-900'
                        : darkMode ? 'text-gray-200' : 'text-gray-800'
                    }`}>
                      {conv.title}
                    </p>
                    <p className={`text-xs mt-1 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                      {new Date(conv.timestamp).toLocaleDateString()} {new Date(conv.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </div>
                  <button
                    onClick={(e) => deleteConversation(conv.id, e)}
                    className={`opacity-0 group-hover:opacity-100 p-1 rounded transition-all ${darkMode ? 'hover:bg-neutral-700' : 'hover:bg-red-100'}`}
                    title="Delete conversation"
                  >
                    <Trash2 className="w-4 h-4 text-red-500" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Sidebar Footer */}
        <div className={`p-4 border-t ${darkMode ? 'border-neutral-800' : 'border-gray-200'}`}>
          {/* Dark/Light Mode Toggle */}
          <div className="flex items-center justify-between px-1 mb-4">
            <span className={`text-xs ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Light</span>
            <button
              onClick={() => setDarkMode(!darkMode)}
              className={`relative w-12 h-6 rounded-full transition-colors duration-300 ${
                darkMode ? 'bg-blue-600' : 'bg-gray-300'
              }`}
            >
              <span
                className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform duration-300 ${
                  darkMode ? 'translate-x-6' : 'translate-x-0'
                }`}
              />
            </button>
            <span className={`text-xs ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Dark</span>
          </div>

          {/* Hospital Selector */}
          {user && Object.keys(allHospitals).length > 0 && (
            <div className="mb-4">
              <p className={`text-xs font-medium mb-2 px-1 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                Logged into
              </p>
              <div className="relative">
                <button
                  onClick={() => setShowHospitalDropdown(!showHospitalDropdown)}
                  className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors ${
                    darkMode 
                      ? 'bg-neutral-800 border-neutral-700 hover:border-neutral-600' 
                      : 'bg-white border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <Building2 className={`w-4 h-4 flex-shrink-0 ${darkMode ? 'text-blue-400' : 'text-blue-600'}`} />
                  <span className={`flex-1 text-left text-sm truncate ${darkMode ? 'text-gray-200' : 'text-gray-700'}`}>
                    {selectedHospital ? selectedHospital.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ') : 'Select hospital...'}
                  </span>
                  <ChevronDown className={`w-4 h-4 flex-shrink-0 transition-transform ${darkMode ? 'text-gray-500' : 'text-gray-400'} ${showHospitalDropdown ? 'rotate-180' : ''}`} />
                </button>

                {showHospitalDropdown && (
                  <>
                    <div 
                      className="fixed inset-0 z-10" 
                      onClick={() => setShowHospitalDropdown(false)}
                    />
                    <div className={`absolute bottom-full left-0 right-0 mb-2 border rounded-lg shadow-lg z-20 max-h-48 overflow-y-auto ${darkMode ? 'bg-neutral-900 border-neutral-800' : 'bg-white border-gray-200'}`}>
                      {Object.keys(allHospitals).map((hospital) => (
                        <button
                          key={hospital}
                          onClick={() => {
                            setSelectedHospital(hospital);
                            setShowHospitalDropdown(false);
                            // Clear bundle selection when switching hospitals
                            setSelectedBundles(new Set());
                          }}
                          className={`w-full flex items-center gap-2 px-3 py-2 text-sm transition-colors first:rounded-t-lg last:rounded-b-lg ${
                            selectedHospital === hospital
                              ? darkMode 
                                ? 'bg-blue-900/30 text-blue-400' 
                                : 'bg-blue-50 text-blue-700'
                              : darkMode 
                                ? 'text-gray-300 hover:bg-neutral-800' 
                                : 'text-gray-700 hover:bg-gray-50'
                          }`}
                        >
                          <Building2 className="w-4 h-4 flex-shrink-0" />
                          <span className="flex-1 text-left truncate">
                            {hospital.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                          </span>
                          {selectedHospital === hospital && (
                            <Check className="w-4 h-4 flex-shrink-0" />
                          )}
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </div>
          )}

          {/* User Auth - at bottom */}
          {user ? (
            <div className="relative">
              <button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl transition-colors ${darkMode ? 'hover:bg-neutral-800' : 'hover:bg-gray-100'}`}
              >
                {user.photoURL ? (
                  <img 
                    src={user.photoURL} 
                    alt="Profile" 
                    className="w-10 h-10 rounded-full flex-shrink-0"
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-sm font-medium flex-shrink-0">
                    {user.email?.charAt(0).toUpperCase()}
                  </div>
                )}
                <div className="flex-1 min-w-0 text-left">
                  <p className={`text-sm font-medium truncate ${darkMode ? 'text-gray-100' : 'text-gray-900'}`}>
                    {userProfile?.orgName || user.email?.split("@")[0]}
                  </p>
                  <p className={`text-xs truncate ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>{user.email}</p>
                </div>
                <ChevronDown className={`w-4 h-4 transition-transform flex-shrink-0 ${darkMode ? 'text-gray-500' : 'text-gray-400'} ${showUserMenu ? 'rotate-180' : ''}`} />
              </button>
              
              {showUserMenu && (
                <>
                  <div 
                    className="fixed inset-0 z-10" 
                    onClick={() => setShowUserMenu(false)}
                  />
                  <div className={`absolute bottom-full left-0 right-0 mb-2 border rounded-lg shadow-lg z-20 ${darkMode ? 'bg-neutral-900 border-neutral-800' : 'bg-white border-gray-200'}`}>
                    <div className={`px-4 py-3 border-b ${darkMode ? 'border-neutral-800' : 'border-gray-100'}`}>
                      <p className={`text-sm font-medium truncate ${darkMode ? 'text-gray-100' : 'text-gray-900'}`}>{user.email}</p>
                      {userProfile?.orgName && (
                        <p className={`text-xs mt-1 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>{userProfile.orgName}</p>
                      )}
                      {userProfile?.bundleAccess && userProfile.bundleAccess.length > 0 && (
                        <p className={`text-xs mt-1 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                          Bundles: {userProfile.bundleAccess.join(", ")}
                        </p>
                      )}
                    </div>
                    {/* Admin Dashboard Links */}
                    {userProfile && (userProfile.role === "admin" || userProfile.role === "super_admin") && (
                      <>
                        <button
                          onClick={() => router.push("/owner")}
                          className={`w-full flex items-center gap-2 px-4 py-3 text-sm transition-colors ${darkMode ? 'text-gray-300 hover:bg-neutral-800' : 'text-gray-600 hover:bg-gray-50'} border-b ${darkMode ? 'border-neutral-800' : 'border-gray-100'}`}
                        >
                          <Crown className="w-4 h-4" />
                          Owner Dashboard
                        </button>
                        <button
                          onClick={() => router.push("/admin")}
                          className={`w-full flex items-center gap-2 px-4 py-3 text-sm transition-colors ${darkMode ? 'text-gray-300 hover:bg-neutral-800' : 'text-gray-600 hover:bg-gray-50'} border-b ${darkMode ? 'border-neutral-800' : 'border-gray-100'}`}
                        >
                          <Shield className="w-4 h-4" />
                          Upload Protocols
                        </button>
                      </>
                    )}
                    <button
                      onClick={handleSignOut}
                      className={`w-full flex items-center gap-2 px-4 py-3 text-sm transition-colors rounded-b-lg ${darkMode ? 'text-gray-300 hover:bg-neutral-800' : 'text-gray-600 hover:bg-gray-50'}`}
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
              className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl border transition-colors ${darkMode ? 'border-neutral-700 hover:bg-neutral-800' : 'border-gray-200 hover:bg-gray-100'}`}
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              <span className={`text-sm ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>Sign in with Google</span>
            </button>
          )}
        </div>
      </aside>

      {/* Main Content */}
      <main className={`flex-1 flex flex-col min-h-screen transition-all duration-300 ${sidebarOpen ? 'ml-72' : 'ml-0'}`}>
        {/* Header */}
        <div className={`sticky top-0 z-30 w-full px-4 pt-4 border-b pb-3 ${darkMode ? 'bg-black border-neutral-800' : 'bg-white border-gray-100'}`}>
          <div className="flex items-center">
            {/* Far Left: Menu - only show when sidebar collapsed */}
            {!sidebarOpen && (
              <button 
                onClick={() => setSidebarOpen(true)}
                className={`p-2 rounded-lg transition-colors ${darkMode ? 'hover:bg-neutral-800' : 'hover:bg-gray-100'}`}
              >
                <div className="flex flex-col gap-1.5">
                  <span className={`block w-5 h-0.5 rounded-full ${darkMode ? 'bg-gray-300' : 'bg-black'}`} />
                  <span className={`block w-5 h-0.5 rounded-full ${darkMode ? 'bg-gray-300' : 'bg-black'}`} />
                  <span className={`block w-5 h-0.5 rounded-full ${darkMode ? 'bg-gray-300' : 'bg-black'}`} />
                </div>
              </button>
            )}

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
              <p className={`text-sm italic mt-1 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                AI-powered emergency medicine clinical decision support
              </p>
            )}
          </div>

          {/* Right: Spacer for balance */}
          <div className="w-10"></div>
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
      <div className="w-full max-w-5xl mx-auto px-4 py-8">
        {!hasSearched ? (
          /* Initial Search View */
          <div className="flex flex-col items-center justify-center min-h-[60vh]">
            <div className="w-full max-w-3xl px-4">
              {/* Input Box */}
              <div className="relative mt-2">
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
                  className={`w-full p-4 pl-5 pr-28 border-2 rounded-3xl text-sm shadow-lg resize-none focus:outline-none focus:border-blue-400 focus:ring-4 transition-all duration-200 hover:shadow-xl ${
                    darkMode 
                      ? 'bg-neutral-900 border-neutral-700 text-gray-100 placeholder-gray-500 focus:ring-blue-900' 
                      : 'bg-gray-50 border-gray-300 text-gray-800 focus:ring-blue-100'
                  }`}
                />

                {/* Mic Button */}
                <button
                  title="Voice input"
                  className={`absolute right-16 top-1/2 -translate-y-1/2 w-10 h-10 flex-shrink-0 rounded-2xl flex items-center justify-center border-2 transition-all duration-200 shadow-md hover:shadow-lg ${
                    darkMode 
                      ? 'bg-neutral-800 text-gray-300 border-neutral-700 hover:bg-neutral-700' 
                      : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-100'
                  }`}
                >
                  <Mic className="w-4 h-4" />
                </button>

                {/* Submit Button */}
                <button
                  onClick={handleSubmit}
                  disabled={!question.trim() || loading}
                  title="Submit"
                  className={`absolute right-3 top-1/2 -translate-y-1/2 w-10 h-10 flex-shrink-0 rounded-2xl text-white flex items-center justify-center transition-all duration-200 hover:scale-105 border-2 border-transparent disabled:opacity-50 disabled:hover:scale-100 shadow-md hover:shadow-lg ${
                    darkMode ? 'bg-blue-600 hover:bg-blue-500' : 'bg-black hover:bg-gray-800 hover:border-gray-300'
                  }`}
                >
                  {loading ? (
                    <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <ArrowUp className="w-4 h-4" />
                  )}
                </button>
              </div>

              {/* Bundle Toggle Chips - Gemini Style */}
              {selectedHospital && allHospitals[selectedHospital] && Object.keys(allHospitals[selectedHospital]).length > 0 && (
                <div className="mt-6">
                  <div className="flex flex-wrap gap-3 justify-center">
                    {Object.keys(allHospitals[selectedHospital]).map((bundle, index) => {
                      const bundleKey = `${selectedHospital}/${bundle}`;
                      const isSelected = selectedBundles.has(bundleKey);
                      return (
                        <button
                          key={bundleKey}
                          onClick={() => toggleBundleSelection(bundleKey)}
                          className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium transition-all duration-200 ${
                            isSelected
                              ? darkMode
                                ? 'bg-blue-600 text-white border-2 border-blue-500'
                                : 'bg-blue-500 text-white border-2 border-blue-400'
                              : darkMode
                                ? 'bg-neutral-800 text-gray-300 border-2 border-neutral-700 hover:bg-neutral-700 hover:border-neutral-600'
                                : 'bg-gray-100 text-gray-600 border-2 border-gray-200 hover:bg-gray-200 hover:border-gray-300'
                          }`}
                        >
                          {getBundleIcon(bundle, index, isSelected)}
                          <span>{bundle}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          /* Results View */
          <div className="space-y-6 pb-32">
            {/* User Question */}
            <div className="flex justify-end">
              <div className={`rounded-2xl px-5 py-3 max-w-[80%] ${darkMode ? 'bg-neutral-800 border border-neutral-700' : 'bg-blue-50 border border-blue-100'}`}>
                <p className={darkMode ? 'text-gray-100' : 'text-gray-800'}>{question}</p>
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
                <span className={`text-sm ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Searching protocols...</span>
              </div>
            ) : error ? (
              <div className={`rounded-2xl px-5 py-4 ${darkMode ? 'bg-red-950 border border-red-900' : 'bg-red-50 border border-red-100'}`}>
                <p className={darkMode ? 'text-red-300' : 'text-red-700'}>{error}</p>
              </div>
            ) : response ? (
              <div className="space-y-6">
                {/* Query Time */}
                <div className={`flex items-center gap-2 text-xs ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                  <Sparkles className="w-3 h-3 text-blue-500" />
                  <span>{response.query_time_ms}ms</span>
                </div>

                {/* Answer */}
                <div className={`rounded-2xl p-6 shadow-sm ${darkMode ? 'bg-neutral-900 border border-neutral-800' : 'bg-white border border-gray-200'}`}>
                  <div className={`prose prose-sm max-w-none leading-relaxed ${darkMode ? 'prose-invert text-gray-200' : 'text-gray-800'}`}>
                    <ReactMarkdown>{response.answer}</ReactMarkdown>
                  </div>
                </div>

                {/* Citations */}
                {response.citations.length > 0 && (
                  <div className={`rounded-2xl p-5 ${darkMode ? 'bg-neutral-900 border border-neutral-800' : 'bg-gray-50 border border-gray-200'}`}>
                    <h3 className={`text-sm font-semibold mb-4 flex items-center gap-2 ${darkMode ? 'text-gray-200' : 'text-gray-700'}`}>
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
                          className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all text-sm ${darkMode ? 'text-blue-400 hover:bg-neutral-800' : 'text-blue-600 hover:bg-white hover:shadow-sm'}`}
                        >
                          <span className={`w-6 h-6 flex items-center justify-center rounded text-xs font-medium ${darkMode ? 'bg-blue-900/50 text-blue-300' : 'bg-blue-100 text-blue-700'}`}>{idx + 1}</span>
                          <span className="flex-1">{cite.protocol_id.replace(/_/g, " ")}</span>
                          <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                          </svg>
                        </a>
                      ))}
                    </div>
                  </div>
                )}

                {/* Images - Horizontal Scrolling Carousel */}
                {response.images.length > 0 && (
                  <div className="space-y-3">
                    <h3 className={`text-sm font-semibold flex items-center gap-2 ${darkMode ? 'text-gray-200' : 'text-gray-700'}`}>
                      <svg className="w-4 h-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      Related Diagrams
                    </h3>
                    {/* Horizontal Scroll Container */}
                    <div className="relative -mx-4 px-4">
                      <div className="flex gap-4 overflow-x-auto pb-4 snap-x snap-mandatory scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent hover:scrollbar-thumb-gray-400">
                        {response.images.map((img, idx) => (
                          <div 
                            key={idx} 
                            className={`flex-shrink-0 w-80 rounded-2xl overflow-hidden border shadow-sm snap-start transition-transform hover:scale-[1.02] ${darkMode ? 'bg-neutral-900 border-neutral-700' : 'bg-white border-gray-200'}`}
                          >
                            <img
                              src={img.url}
                              alt={`Protocol diagram from ${img.protocol_id}, page ${img.page}`}
                              className="w-full h-auto object-contain"
                              loading="lazy"
                            />
                            <div className={`px-4 py-3 text-xs border-t ${darkMode ? 'text-gray-400 border-neutral-700' : 'text-gray-500 border-gray-100'}`}>
                              {img.protocol_id.replace(/_/g, " ")} · Page {img.page}
                            </div>
                          </div>
                        ))}
                      </div>
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
        <div className={`fixed bottom-0 right-0 border-t px-4 py-4 z-40 transition-all duration-300 ${sidebarOpen ? 'left-72' : 'left-0'} ${darkMode ? 'bg-black border-neutral-800' : 'bg-white border-gray-100'}`}>
          <div className="max-w-3xl mx-auto relative">
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
              className={`w-full p-4 pl-5 pr-28 border-2 rounded-3xl text-sm shadow-lg resize-none focus:outline-none focus:border-blue-400 focus:ring-4 transition-all duration-200 hover:shadow-xl ${
                darkMode 
                  ? 'bg-neutral-900 border-neutral-700 text-gray-100 placeholder-gray-500 focus:ring-blue-900' 
                  : 'bg-gray-50 border-gray-300 text-gray-800 focus:ring-blue-100'
              }`}
            />

            {/* Mic Button */}
            <button
              title="Voice input"
              className={`absolute right-16 top-1/2 -translate-y-1/2 w-10 h-10 flex-shrink-0 rounded-2xl flex items-center justify-center border-2 transition-all duration-200 shadow-md hover:shadow-lg ${
                darkMode 
                  ? 'bg-neutral-800 text-gray-300 border-neutral-700 hover:bg-neutral-700' 
                  : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-100'
              }`}
            >
              <Mic className="w-4 h-4" />
            </button>

            <button
              onClick={handleSubmit}
              disabled={!question.trim() || loading}
              title="Submit"
              className={`absolute right-3 top-1/2 -translate-y-1/2 w-10 h-10 flex-shrink-0 rounded-2xl text-white flex items-center justify-center transition-all duration-200 hover:scale-105 border-2 border-transparent disabled:opacity-50 disabled:hover:scale-100 shadow-md hover:shadow-lg ${
                darkMode ? 'bg-blue-600 hover:bg-blue-500' : 'bg-black hover:bg-gray-800 hover:border-gray-300'
              }`}
            >
              {loading ? (
                <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <ArrowUp className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
      )}
      </main>
    </div>
  );
}

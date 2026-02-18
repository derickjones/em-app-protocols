"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, LogOut, ChevronDown, ChevronRight, ArrowUp, Mic, Plus, MessageSquare, X, Trash2, Building2, Check, Heart, Syringe, Activity, Stethoscope, Zap, Brain, Bone, ShieldPlus, Cross, Pill, Crown, Shield, Globe, FileText, BookOpen, Save } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAuth } from "@/lib/auth-context";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://em-protocol-api-930035889332.us-central1.run.app";
const STORAGE_KEY = "em-protocol-conversations";
const THEME_KEY = "em-protocol-theme";
const BUNDLE_KEY = "em-protocol-selected-bundles";
const ED_KEY = "em-protocol-selected-eds";
const UNIVERSE_KEY = "em-protocol-ed-universe";

// PMC Journal registry — key is the exact string stored in GCS metadata
const PMC_JOURNALS: { key: string; label: string; count: number }[] = [
  { key: "The Western Journal of Emergency Medicine", label: "Western J EM", count: 2023 },
  { key: "Journal of the American College of Emergency Physicians Open", label: "JACEP Open", count: 1561 },
  { key: "The American Journal of Emergency Medicine", label: "Am J Emerg Med", count: 867 },
  { key: "Annals of Emergency Medicine", label: "Annals of EM", count: 664 },
  { key: "Acad Emerg Med", label: "Academic EM", count: 548 },
  { key: "The Journal of Emergency Medicine", label: "J Emerg Med", count: 258 },
  { key: "Pediatric Emergency Care", label: "Peds Emerg Care", count: 238 },
  { key: "Advanced Journal of Emergency Medicine", label: "Adv J Emerg Med", count: 145 },
  { key: "Eur J Emerg Med", label: "Eur J Emerg Med", count: 107 },
  { key: "Prehospital Emergency Care", label: "Prehosp Emerg Care", count: 107 },
  { key: "Air Medical Journal", label: "Air Med Journal", count: 86 },
];
const ALL_PMC_JOURNAL_KEYS = PMC_JOURNALS.map(j => j.key);
const TOTAL_PMC_COUNT = PMC_JOURNALS.reduce((sum, j) => sum + j.count, 0);

interface QueryResponse {
  answer: string;
  images: { page: number; url: string; protocol_id: string }[];
  citations: { protocol_id: string; source_uri: string; relevance_score: number; source_type: string }[];
  query_time_ms: number;
}

interface Conversation {
  id: string;
  title: string;
  timestamp: string; // Changed to string for JSON serialization
  question: string;
  response: QueryResponse | null;
}

interface BundleData {
  id: string;
  name: string;
  slug: string;
  description?: string;
  icon?: string;
  color?: string;
}

interface EDData {
  id: string;
  name: string;
  slug: string;
  location?: string;
  bundles: BundleData[];
}

interface EnterpriseData {
  id: string;
  name: string;
  eds: EDData[];
  userEdAccess: string[];
  userRole: string;
  allEnterprises?: { id: string; name: string; eds: EDData[] }[];
}

export default function Home() {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [streamingAnswer, setStreamingAnswer] = useState<string>("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [darkMode, setDarkMode] = useState(false);
  
  // Enterprise/ED/Bundle selection state
  const [enterprise, setEnterprise] = useState<EnterpriseData | null>(null);
  const [selectedEds, setSelectedEds] = useState<Set<string>>(new Set());
  const [selectedBundles, setSelectedBundles] = useState<Set<string>>(new Set());
  const [expandedHospitals, setExpandedHospitals] = useState<Set<string>>(new Set());
  const [showBundleSelector, setShowBundleSelector] = useState(false);

  // ED Universe state
  const [wikemEnabled, setWikemEnabled] = useState(true);
  const [pmcEnabled, setPmcEnabled] = useState(true);
  const [litflEnabled, setLitflEnabled] = useState(true);
  const [selectedJournals, setSelectedJournals] = useState<Set<string>>(new Set(ALL_PMC_JOURNAL_KEYS));
  const [wikemExpanded, setWikemExpanded] = useState(false);
  const [pmcExpanded, setPmcExpanded] = useState(false);
  const [litflExpanded, setLitflExpanded] = useState(false);
  const [universeDirty, setUniverseDirty] = useState(false); // track unsaved changes

  // Lightbox state for image enlargement
  const [lightboxImage, setLightboxImage] = useState<{ url: string; protocol_id: string; page: number } | null>(null);

  // Toggle wikem source on/off (can be turned off if EDs are selected)
  // Globe toggles ALL external sources together
  const toggleSource = (source: string) => {
    if (source === "wikem") {
      const isCurrentlyOn = wikemEnabled || pmcEnabled || litflEnabled;
      if (isCurrentlyOn) {
        // Turn off all — only if we have EDs selected (need at least one source)
        if (selectedEds.size > 0) {
          setWikemEnabled(false);
          setPmcEnabled(false);
          setLitflEnabled(false);
        }
      } else {
        // Turn all back on
        setWikemEnabled(true);
        setPmcEnabled(true);
        setLitflEnabled(true);
      }
    }
  };

  // Derive the effective sources array for API calls
  const getEffectiveSources = (): string[] => {
    const sources: string[] = [];
    if (selectedEds.size > 0) sources.push("local");
    if (wikemEnabled) sources.push("wikem");
    if (pmcEnabled && selectedJournals.size > 0) sources.push("pmc");
    if (litflEnabled) sources.push("litfl");
    return sources;
  };

  // Derive the effective PMC journal filter (null = no filter = all)
  const getEffectivePmcJournals = (): string[] | undefined => {
    if (!pmcEnabled) return undefined;
    if (selectedJournals.size === ALL_PMC_JOURNAL_KEYS.length) return undefined; // all selected = no filter
    return Array.from(selectedJournals);
  };

  // Is the globe "on"? (any external source is active)
  const globeActive = wikemEnabled || pmcEnabled || litflEnabled;

  // Save ED Universe preferences to localStorage
  const saveUniversePreferences = () => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(UNIVERSE_KEY, JSON.stringify({
        wikemEnabled,
        pmcEnabled,
        litflEnabled,
        selectedJournals: Array.from(selectedJournals),
      }));
      setUniverseDirty(false);
    }
  };

  // Toggle a single PMC journal
  const toggleJournal = (journalKey: string) => {
    setSelectedJournals(prev => {
      const next = new Set(prev);
      if (next.has(journalKey)) {
        next.delete(journalKey);
      } else {
        next.add(journalKey);
      }
      return next;
    });
    setUniverseDirty(true);
  };

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

      // Load ED Universe preferences
      const savedUniverse = localStorage.getItem(UNIVERSE_KEY);
      if (savedUniverse) {
        try {
          const prefs = JSON.parse(savedUniverse);
          if (typeof prefs.wikemEnabled === 'boolean') setWikemEnabled(prefs.wikemEnabled);
          if (typeof prefs.pmcEnabled === 'boolean') setPmcEnabled(prefs.pmcEnabled);
          if (typeof prefs.litflEnabled === 'boolean') setLitflEnabled(prefs.litflEnabled);
          if (Array.isArray(prefs.selectedJournals)) {
            setSelectedJournals(new Set(prefs.selectedJournals));
          }
        } catch (e) {
          console.warn("Failed to load ED Universe preferences", e);
        }
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

  // Fetch enterprise data (EDs + bundles) for logged-in user
  const fetchEnterprise = useCallback(async () => {
    try {
      const token = await getIdToken();
      if (!token) return;
      const res = await fetch(`${API_URL}/enterprise`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data: EnterpriseData = await res.json();
        setEnterprise(data);
        
        // Auto-select EDs from saved or default to all
        const savedEds = localStorage.getItem(ED_KEY);
        if (savedEds) {
          try {
            const parsed: string[] = JSON.parse(savedEds);
            const valid = parsed.filter((id: string) => data.eds.some(ed => ed.id === id));
            setSelectedEds(new Set(valid.length > 0 ? valid : data.eds.map(ed => ed.id)));
          } catch {
            setSelectedEds(new Set(data.eds.map(ed => ed.id)));
          }
        } else {
          setSelectedEds(new Set(data.eds.map(ed => ed.id)));
        }

        // Default all bundles to selected if no saved preference
        const savedBundles = localStorage.getItem(BUNDLE_KEY);
        if (!savedBundles) {
          const allBundleIds = new Set<string>();
          for (const ed of data.eds) {
            for (const b of ed.bundles) {
              allBundleIds.add(b.id);
            }
          }
          setSelectedBundles(allBundleIds);
        }
      }
    } catch (err) {
      console.error("Failed to fetch enterprise:", err);
    }
  }, [getIdToken]);

  // Switch active enterprise (super_admin only)
  const switchEnterprise = (entId: string) => {
    if (!enterprise?.allEnterprises) return;
    const target = enterprise.allEnterprises.find(e => e.id === entId);
    if (!target) return;
    setEnterprise({
      ...enterprise,
      id: target.id,
      name: target.name,
      eds: target.eds,
    });
    // Reset ED and bundle selections to the new enterprise's EDs
    setSelectedEds(new Set(target.eds.map(ed => ed.id)));
    setSelectedBundles(new Set());
  };

  // Load enterprise when user is available
  useEffect(() => {
    if (user && emailVerified) {
      fetchEnterprise();
    }
  }, [user, emailVerified, fetchEnterprise]);

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

  // Save selected EDs to localStorage
  useEffect(() => {
    if (typeof window !== 'undefined' && selectedEds.size > 0) {
      localStorage.setItem(ED_KEY, JSON.stringify(Array.from(selectedEds)));
    }
  }, [selectedEds]);

  // Close lightbox on Escape key
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setLightboxImage(null);
    };
    if (lightboxImage) {
      document.addEventListener("keydown", handleEsc);
      document.body.style.overflow = "hidden"; // prevent background scroll
    }
    return () => {
      document.removeEventListener("keydown", handleEsc);
      document.body.style.overflow = "";
    };
  }, [lightboxImage]);

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
    const iconClass = "w-4 h-4";
    const off = "text-neutral-500";
    
    // Match bundle names to relevant icons
    const nameLower = bundleName.toLowerCase();
    if (nameLower.includes('cardiac') || nameLower.includes('acls') || nameLower.includes('heart')) {
      return <Heart className={`${iconClass} ${isSelected ? 'text-red-500' : off}`} />;
    }
    if (nameLower.includes('trauma') || nameLower.includes('injury')) {
      return <Zap className={`${iconClass} ${isSelected ? 'text-orange-500' : off}`} />;
    }
    if (nameLower.includes('neuro') || nameLower.includes('stroke') || nameLower.includes('brain')) {
      return <Brain className={`${iconClass} ${isSelected ? 'text-purple-500' : off}`} />;
    }
    if (nameLower.includes('ortho') || nameLower.includes('fracture') || nameLower.includes('bone')) {
      return <Bone className={`${iconClass} ${isSelected ? 'text-gray-400' : off}`} />;
    }
    if (nameLower.includes('peds') || nameLower.includes('pediatric')) {
      return <ShieldPlus className={`${iconClass} ${isSelected ? 'text-pink-500' : off}`} />;
    }
    if (nameLower.includes('med') || nameLower.includes('pharm') || nameLower.includes('drug')) {
      return <Pill className={`${iconClass} ${isSelected ? 'text-green-500' : off}`} />;
    }
    if (nameLower.includes('procedure') || nameLower.includes('injection')) {
      return <Syringe className={`${iconClass} ${isSelected ? 'text-cyan-500' : off}`} />;
    }
    
    // Cycle through icons for generic bundles
    const icons = [
      <Activity key="activity" className={`${iconClass} ${isSelected ? 'text-red-500' : off}`} />,
      <Stethoscope key="stethoscope" className={`${iconClass} ${isSelected ? 'text-blue-500' : off}`} />,
      <Heart key="heart" className={`${iconClass} ${isSelected ? 'text-red-500' : off}`} />,
      <Cross key="cross" className={`${iconClass} ${isSelected ? 'text-emerald-500' : off}`} />,
      <Zap key="zap" className={`${iconClass} ${isSelected ? 'text-yellow-500' : off}`} />,
      <Brain key="brain" className={`${iconClass} ${isSelected ? 'text-purple-500' : off}`} />,
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

  // Toggle ED selection
  const toggleEdSelection = (edId: string) => {
    setSelectedEds(prev => {
      const next = new Set(prev);
      if (next.has(edId)) {
        // Don't allow deselecting all — keep at least one
        if (next.size > 1) next.delete(edId);
      } else {
        next.add(edId);
      }
      return next;
    });
  };

  // Get available bundles across all selected EDs (union)
  const getAvailableBundles = (): BundleData[] => {
    if (!enterprise) return [];
    const seen = new Set<string>();
    const bundles: BundleData[] = [];
    for (const ed of enterprise.eds) {
      if (selectedEds.has(ed.id)) {
        for (const b of ed.bundles) {
          if (!seen.has(b.id)) {
            seen.add(b.id);
            bundles.push(b);
          }
        }
      }
    }
    return bundles;
  };

  // Open lightbox and log image click for popularity ranking
  const handleImageClick = (img: { url: string; protocol_id: string; page: number }) => {
    setLightboxImage(img);
    // Fire-and-forget click tracking
    fetch(`${API_URL}/image-click`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        protocol_id: img.protocol_id,
        page: img.page,
        url: img.url,
        query: question,
      }),
    }).catch(() => {}); // silently ignore errors
  };

  const handleSubmit = async () => {
    if (!question.trim() || loading || isStreaming) return;
    
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
    setIsStreaming(false);
    setStreamingAnswer("");
    setResponse(null);
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
          ed_ids: Array.from(selectedEds),
          bundle_ids: selectedBundles.size > 0 ? Array.from(selectedBundles) : ["all"],
          include_images: true,
          sources: getEffectiveSources(),
          pmc_journals: getEffectivePmcJournals(),
          enterprise_id: enterprise?.id || undefined
        }),
      });
      if (!res.ok) {
        if (res.status === 401) {
          throw new Error("Please sign in to search protocols");
        } else if (res.status === 403) {
          const errData = await res.json();
          throw new Error(errData.detail || "Access denied");
        }
        throw new Error(`Error: ${res.status}`);
      }

      // Read SSE stream
      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response body");
      const decoder = new TextDecoder();
      let fullAnswer = "";
      let finalData: QueryResponse | null = null;
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE lines
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // Keep incomplete line in buffer

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const jsonStr = line.slice(6).trim();
          if (!jsonStr) continue;

          try {
            const event = JSON.parse(jsonStr);
            if (event.type === "chunk") {
              // First chunk: switch from loading dots to streaming text
              if (!fullAnswer) {
                setLoading(false);
                setIsStreaming(true);
              }
              fullAnswer += event.text;
              setStreamingAnswer(fullAnswer);
            } else if (event.type === "done") {
              finalData = {
                answer: fullAnswer,
                images: event.images || [],
                citations: event.citations || [],
                query_time_ms: event.query_time_ms || 0
              };
            } else if (event.type === "error") {
              throw new Error(event.message);
            }
          } catch (parseErr) {
            // Skip malformed JSON lines
            if (parseErr instanceof SyntaxError) continue;
            throw parseErr;
          }
        }
      }

      // Stream complete — set final response
      setIsStreaming(false);
      if (finalData) {
        setResponse(finalData);
      } else {
        // Fallback if no done event received
        setResponse({ answer: fullAnswer, images: [], citations: [], query_time_ms: 0 });
      }

      // Save conversation to history
      const savedResponse = finalData || { answer: fullAnswer, images: [], citations: [], query_time_ms: 0 };
      const newConversation: Conversation = {
        id: conversationId,
        title: question.trim().slice(0, 50) + (question.length > 50 ? "..." : ""),
        timestamp: new Date().toISOString(),
        question: question.trim(),
        response: savedResponse,
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
      setStreamingAnswer("");
    } finally {
      setLoading(false);
      setIsStreaming(false);
    }
  };

  const startNewConversation = () => {
    setQuestion("");
    setResponse(null);
    setStreamingAnswer("");
    setIsStreaming(false);
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

          {/* ED Universe — Knowledge Sources */}
          <div className={`mb-4 rounded-xl border ${darkMode ? 'border-neutral-800 bg-neutral-900/50' : 'border-gray-200 bg-gray-50/50'}`}>
            <div className={`px-3 py-2 flex items-center gap-2`}>
              <Globe className={`w-3.5 h-3.5 flex-shrink-0 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`} />
              <span className={`text-xs font-medium tracking-wide ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                Ed Universe
              </span>
            </div>

            <div className={`px-2 pb-2 space-y-1`}>
              {/* WikEM Section */}
              <div>
                <button
                  onClick={() => setWikemExpanded(!wikemExpanded)}
                  className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm transition-colors ${
                    darkMode ? 'hover:bg-neutral-800' : 'hover:bg-gray-100'
                  }`}
                >
                  <div
                    onClick={(e) => {
                      e.stopPropagation();
                      setWikemEnabled(!wikemEnabled);
                      setUniverseDirty(true);
                    }}
                    className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 cursor-pointer ${
                      wikemEnabled
                        ? 'bg-blue-500 border-blue-500'
                        : darkMode ? 'border-neutral-600' : 'border-gray-300'
                    }`}
                  >
                    {wikemEnabled && <Check className="w-3 h-3 text-white" />}
                  </div>
                  <img src="/logos/wikem.jpg" alt="WikEM" className={`w-4 h-4 rounded flex-shrink-0 ${wikemEnabled ? 'opacity-100' : 'opacity-40'}`} />
                  <span className={`flex-1 text-left font-medium ${wikemEnabled ? darkMode ? 'text-gray-200' : 'text-gray-700' : darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                    WikEM
                  </span>
                  <span className={`text-xs ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>1,899</span>
                  {wikemExpanded ? (
                    <ChevronDown className={`w-3.5 h-3.5 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`} />
                  ) : (
                    <ChevronRight className={`w-3.5 h-3.5 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`} />
                  )}
                </button>
                {wikemExpanded && (
                  <div className={`ml-8 mt-1 px-2 py-2 rounded-lg text-xs leading-relaxed ${
                    darkMode ? 'text-gray-400 bg-neutral-800/50' : 'text-gray-500 bg-gray-100/50'
                  }`}>
                    Community-maintained EM knowledge base covering 1,899 clinical topics — diagnoses, procedures, and differentials.
                  </div>
                )}
              </div>

              {/* LITFL Section */}
              <div>
                <button
                  onClick={() => setLitflExpanded(!litflExpanded)}
                  className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm transition-colors ${
                    darkMode ? 'hover:bg-neutral-800' : 'hover:bg-gray-100'
                  }`}
                >
                  <div
                    onClick={(e) => {
                      e.stopPropagation();
                      setLitflEnabled(!litflEnabled);
                      setUniverseDirty(true);
                    }}
                    className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 cursor-pointer ${
                      litflEnabled
                        ? 'bg-emerald-500 border-emerald-500'
                        : darkMode ? 'border-neutral-600' : 'border-gray-300'
                    }`}
                  >
                    {litflEnabled && <Check className="w-3 h-3 text-white" />}
                  </div>
                  <img src="/logos/litfl-logo.png" alt="LITFL" className={`w-4 h-4 rounded flex-shrink-0 ${litflEnabled ? 'opacity-100' : 'opacity-40'}`} />
                  <span className={`flex-1 text-left font-medium ${litflEnabled ? darkMode ? 'text-gray-200' : 'text-gray-700' : darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                    LITFL
                  </span>
                  <span className={`text-xs ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>7,902</span>
                  {litflExpanded ? (
                    <ChevronDown className={`w-3.5 h-3.5 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`} />
                  ) : (
                    <ChevronRight className={`w-3.5 h-3.5 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`} />
                  )}
                </button>
                {litflExpanded && (
                  <div className={`ml-8 mt-1 px-2 py-2 rounded-lg text-xs leading-relaxed ${
                    darkMode ? 'text-gray-400 bg-neutral-800/50' : 'text-gray-500 bg-gray-100/50'
                  }`}>
                    Life in the Fast Lane — 7,902 FOAMed articles covering ECG interpretation, critical care, toxicology, pharmacology, clinical cases, and eponymous medical terms. CC BY-NC-SA 4.0.
                  </div>
                )}
              </div>

              {/* PMC Literature Section */}
              <div>
                <button
                  onClick={() => setPmcExpanded(!pmcExpanded)}
                  className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm transition-colors ${
                    darkMode ? 'hover:bg-neutral-800' : 'hover:bg-gray-100'
                  }`}
                >
                  <div
                    onClick={(e) => {
                      e.stopPropagation();
                      setPmcEnabled(!pmcEnabled);
                      setUniverseDirty(true);
                    }}
                    className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 cursor-pointer ${
                      pmcEnabled
                        ? 'bg-purple-500 border-purple-500'
                        : darkMode ? 'border-neutral-600' : 'border-gray-300'
                    }`}
                  >
                    {pmcEnabled && <Check className="w-3 h-3 text-white" />}
                  </div>
                  <img src="/logos/pmc_logo.png" alt="PMC" className={`w-4 h-4 rounded flex-shrink-0 ${pmcEnabled ? 'opacity-100' : 'opacity-40'}`} />
                  <span className={`flex-1 text-left font-medium ${pmcEnabled ? darkMode ? 'text-gray-200' : 'text-gray-700' : darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                    PMC Literature
                  </span>
                  <span className={`text-xs ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                    {selectedJournals.size === ALL_PMC_JOURNAL_KEYS.length
                      ? TOTAL_PMC_COUNT.toLocaleString()
                      : `${selectedJournals.size}/${PMC_JOURNALS.length}`
                    }
                  </span>
                  {pmcExpanded ? (
                    <ChevronDown className={`w-3.5 h-3.5 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`} />
                  ) : (
                    <ChevronRight className={`w-3.5 h-3.5 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`} />
                  )}
                </button>
                {pmcExpanded && (
                  <div className="ml-4 mt-1">
                    {/* Select All / Clear */}
                    <div className="flex items-center gap-2 px-2 mb-1">
                      <button
                        onClick={() => { setSelectedJournals(new Set(ALL_PMC_JOURNAL_KEYS)); setUniverseDirty(true); }}
                        className={`text-xs transition-colors ${
                          selectedJournals.size === ALL_PMC_JOURNAL_KEYS.length
                            ? darkMode ? 'text-gray-600' : 'text-gray-300'
                            : darkMode ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-700'
                        }`}
                        disabled={selectedJournals.size === ALL_PMC_JOURNAL_KEYS.length}
                      >
                        Select All
                      </button>
                      <span className={`text-xs ${darkMode ? 'text-gray-700' : 'text-gray-300'}`}>·</span>
                      <button
                        onClick={() => { setSelectedJournals(new Set()); setUniverseDirty(true); }}
                        className={`text-xs transition-colors ${
                          selectedJournals.size === 0
                            ? darkMode ? 'text-gray-600' : 'text-gray-300'
                            : darkMode ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-700'
                        }`}
                        disabled={selectedJournals.size === 0}
                      >
                        Clear
                      </button>
                    </div>
                    {/* Journal list */}
                    <div className="space-y-0.5 max-h-48 overflow-y-auto">
                      {PMC_JOURNALS.map((j) => {
                        const isChecked = selectedJournals.has(j.key);
                        return (
                          <button
                            key={j.key}
                            onClick={() => toggleJournal(j.key)}
                            className={`w-full flex items-center gap-2 px-2 py-1 rounded-md text-xs transition-colors ${
                              darkMode ? 'hover:bg-neutral-800' : 'hover:bg-gray-100'
                            }`}
                          >
                            <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center flex-shrink-0 ${
                              isChecked
                                ? 'bg-purple-500 border-purple-500'
                                : darkMode ? 'border-neutral-600' : 'border-gray-300'
                            }`}>
                              {isChecked && <Check className="w-2.5 h-2.5 text-white" />}
                            </div>
                            <span className={`flex-1 text-left ${
                              isChecked
                                ? darkMode ? 'text-gray-300' : 'text-gray-700'
                                : darkMode ? 'text-gray-500' : 'text-gray-400'
                            }`}>
                              {j.label}
                            </span>
                            <span className={`text-xs tabular-nums ${darkMode ? 'text-gray-600' : 'text-gray-400'}`}>
                              {j.count.toLocaleString()}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            </div>

          </div>

          {/* Enterprise + ED Selector */}
          {user && enterprise && (
            <div className={`mb-4 rounded-xl border ${darkMode ? 'border-neutral-800 bg-neutral-900/50' : 'border-gray-200 bg-gray-50/50'}`}>
              <div className="p-3">
              {/* Enterprise selector (super_admin) or name (regular user) */}
              {enterprise.allEnterprises && enterprise.allEnterprises.length > 1 ? (
                <div className="mb-3">
                  <p className={`text-xs font-medium mb-1.5 px-1 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                    Enterprise
                  </p>
                  <div className="relative">
                    <select
                      value={enterprise.id}
                      onChange={(e) => switchEnterprise(e.target.value)}
                      className={`w-full px-3 py-2 rounded-lg text-sm font-semibold appearance-none cursor-pointer pr-8 ${
                        darkMode
                          ? 'bg-neutral-800 text-gray-200 border border-neutral-700 focus:border-blue-500'
                          : 'bg-white text-gray-700 border border-gray-200 focus:border-blue-400'
                      } focus:outline-none transition-colors`}
                    >
                      {enterprise.allEnterprises.map((ent) => (
                        <option key={ent.id} value={ent.id}>{ent.name}</option>
                      ))}
                    </select>
                    <ChevronDown className={`absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none ${darkMode ? 'text-gray-400' : 'text-gray-500'}`} />
                  </div>
                </div>
              ) : (
                <div className={`flex items-center gap-2 px-1 mb-3`}>
                  <Building2 className={`w-4 h-4 flex-shrink-0 ${darkMode ? 'text-blue-400' : 'text-blue-600'}`} />
                  <span className={`text-sm font-semibold ${darkMode ? 'text-gray-200' : 'text-gray-700'}`}>
                    {enterprise.name}
                  </span>
                </div>
              )}
              
              {/* ED multi-select chips */}
              {enterprise.eds.length > 0 && (
                <div>
                  <p className={`text-xs font-medium mb-1.5 px-1 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                    Emergency Departments
                  </p>
                  <div className="flex flex-col gap-0.5">
                    {enterprise.eds.map((ed) => {
                      const isSelected = selectedEds.has(ed.id);
                      return (
                        <button
                          key={ed.id}
                          onClick={() => toggleEdSelection(ed.id)}
                          className={`flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-all ${
                            isSelected
                              ? darkMode
                                ? 'bg-blue-900/40 text-blue-300'
                                : 'bg-blue-50 text-blue-700'
                              : darkMode
                                ? 'text-gray-400 hover:bg-neutral-800'
                                : 'text-gray-500 hover:bg-gray-100'
                          }`}
                        >
                          <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center flex-shrink-0 ${
                            isSelected 
                              ? 'bg-blue-500 border-blue-500' 
                              : darkMode ? 'border-neutral-600' : 'border-gray-300'
                          }`}>
                            {isSelected && <Check className="w-2.5 h-2.5 text-white" />}
                          </div>
                          <span className="flex-1 text-left text-xs font-medium">{ed.name}</span>
                          {ed.location && (
                            <span className={`text-xs ${darkMode ? 'text-gray-600' : 'text-gray-400'}`}>
                              {ed.location}
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
              </div>
            </div>
          )}

          {/* Save Preferences — covers ED Universe + ED selections */}
          {universeDirty && (
            <div className="mb-4">
              <button
                onClick={saveUniversePreferences}
                className={`w-full flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  darkMode
                    ? 'bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 border border-blue-600/30'
                    : 'bg-blue-50 text-blue-600 hover:bg-blue-100 border border-blue-200'
                }`}
              >
                <Save className="w-3 h-3" />
                Save Preferences
              </button>
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
                    {userProfile?.enterpriseName || user.email?.split("@")[0]}
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
                      {userProfile?.enterpriseName && (
                        <p className={`text-xs mt-1 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>{userProfile.enterpriseName}</p>
                      )}
                      {userProfile?.edAccess && userProfile.edAccess.length > 0 && (
                        <p className={`text-xs mt-1 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                          EDs: {userProfile.edAccess.join(", ")}
                        </p>
                      )}
                    </div>
                    {/* Admin Dashboard Links */}
                    {userProfile && (userProfile.role === "admin" || userProfile.role === "super_admin") && (
                      <>
                        {userProfile.role === "super_admin" && (
                          <button
                            onClick={() => router.push("/owner")}
                            className={`w-full flex items-center gap-2 px-4 py-3 text-sm transition-colors ${darkMode ? 'text-gray-300 hover:bg-neutral-800' : 'text-gray-600 hover:bg-gray-50'} border-b ${darkMode ? 'border-neutral-800' : 'border-gray-100'}`}
                          >
                            <Crown className="w-4 h-4" />
                            Owner Dashboard
                          </button>
                        )}
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
              {/* Input Box - Gemini style with source icons inside */}
              <div className={`relative mt-2 border-2 rounded-3xl shadow-lg transition-all duration-200 hover:shadow-xl ${
                darkMode 
                  ? 'bg-neutral-900 border-neutral-700 focus-within:border-blue-500 focus-within:ring-4 focus-within:ring-blue-900' 
                  : 'bg-gray-50 border-gray-300 focus-within:border-blue-400 focus-within:ring-4 focus-within:ring-blue-100'
              }`}>
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
                  className={`w-full p-4 pl-5 pr-28 rounded-t-3xl text-sm resize-none focus:outline-none bg-transparent ${
                    darkMode 
                      ? 'text-gray-100 placeholder-gray-500' 
                      : 'text-gray-800'
                  }`}
                />

                {/* Bottom bar inside search box */}
                <div className={`flex items-center justify-between px-4 pb-3 pt-0`}>
                  {/* Source toggles + ED filters - left side */}
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => toggleSource("wikem")}
                      title="ED Universe — WikEM topics + PMC peer-reviewed literature"
                      className={`p-2 rounded-xl transition-all duration-200 ${
                        globeActive
                          ? darkMode
                            ? 'bg-blue-600/20 text-blue-400'
                            : 'bg-blue-50 text-blue-600'
                          : darkMode
                            ? 'text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800'
                            : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <Globe className="w-5 h-5" />
                    </button>
                    {enterprise?.eds.filter((ed) => selectedEds.has(ed.id)).map((ed) => (
                        <button
                          key={ed.id}
                          onClick={() => toggleEdSelection(ed.id)}
                          title={ed.location ? `${ed.name} — ${ed.location}` : ed.name}
                          className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all duration-200 ${
                            darkMode
                              ? 'bg-blue-600/20 text-blue-400 border border-blue-600/30'
                              : 'bg-blue-50 text-blue-600 border border-blue-200'
                          }`}
                        >
                          {ed.name}
                        </button>
                    ))}
                  </div>

                  {/* Right side - mic & submit */}
                  <div className="flex items-center gap-2">
                    <button
                      title="Voice input"
                      className={`w-9 h-9 flex-shrink-0 rounded-xl flex items-center justify-center transition-all duration-200 ${
                        darkMode 
                          ? 'text-gray-400 hover:bg-neutral-800 hover:text-gray-200' 
                          : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'
                      }`}
                    >
                      <Mic className="w-4 h-4" />
                    </button>
                    <button
                      onClick={handleSubmit}
                      disabled={!question.trim() || loading || isStreaming}
                      title="Submit"
                      className={`w-9 h-9 flex-shrink-0 rounded-xl text-white flex items-center justify-center transition-all duration-200 hover:scale-105 disabled:opacity-50 disabled:hover:scale-100 ${
                        darkMode ? 'bg-blue-600 hover:bg-blue-500' : 'bg-black hover:bg-gray-800'
                      }`}
                    >
                      {loading || isStreaming ? (
                        <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      ) : (
                        <ArrowUp className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>
              </div>

              {/* Bundle Toggle Chips */}
              {getAvailableBundles().length > 0 && (
                <div className="mt-6">
                  <p className={`text-xs font-semibold uppercase tracking-widest mb-3 text-center ${darkMode ? 'text-neutral-400' : 'text-gray-500'}`}>
                    Protocol Bundles
                  </p>
                  <div className="flex flex-wrap gap-3 justify-center">
                    {getAvailableBundles().map((bundle, index) => {
                      const isSelected = selectedBundles.has(bundle.id);
                      return (
                        <button
                          key={bundle.id}
                          onClick={() => toggleBundleSelection(bundle.id)}
                          className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium transition-all duration-200 ${
                            isSelected
                              ? darkMode
                                ? 'bg-neutral-800 text-gray-200 border-2 border-blue-500/60'
                                : 'bg-white text-gray-700 border-2 border-blue-400'
                              : darkMode
                                ? 'bg-neutral-800 text-gray-400 border-2 border-neutral-700 hover:text-gray-300 hover:border-neutral-600'
                                : 'bg-gray-100 text-gray-500 border-2 border-gray-200 hover:text-gray-600 hover:border-gray-300'
                          }`}
                        >
                          {getBundleIcon(bundle.name, index, isSelected)}
                          <span>{bundle.name}</span>
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
            ) : (isStreaming || response) ? (
              <div className="space-y-6">
                {/* Query Time — only after stream finishes */}
                {response && (
                  <div className={`flex items-center gap-2 text-xs ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                    <Sparkles className="w-3 h-3 text-blue-500" />
                    <span>{response.query_time_ms}ms</span>
                  </div>
                )}

                {/* Answer — streaming or final */}
                <div className={`rounded-2xl p-6 shadow-sm ${darkMode ? 'bg-neutral-900 border border-neutral-800' : 'bg-white border border-gray-200'}`}>
                  <div className={`prose prose-sm max-w-none leading-relaxed ${darkMode ? 'prose-invert text-gray-200' : 'text-gray-800'}`}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{response ? response.answer : streamingAnswer}</ReactMarkdown>
                  </div>
                </div>

                {/* Images - Horizontal Scrolling Carousel */}
                {response && response.images.length > 0 && (
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
                            onClick={() => handleImageClick(img)}
                            className={`flex-shrink-0 w-80 rounded-2xl overflow-hidden border shadow-sm snap-start transition-transform hover:scale-[1.02] cursor-pointer ${darkMode ? 'bg-neutral-900 border-neutral-700' : 'bg-white border-gray-200'}`}
                          >
                            <img
                              src={img.url}
                              alt={`Protocol diagram from ${img.protocol_id}, page ${img.page}`}
                              className="w-full h-auto object-contain"
                              loading="lazy"
                            />
                            <div className={`px-4 py-3 text-xs border-t flex items-center justify-between ${darkMode ? 'text-gray-400 border-neutral-700' : 'text-gray-500 border-gray-100'}`}>
                              <span>{img.protocol_id.replace(/_/g, " ")} · Page {img.page}</span>
                              <svg className="w-3.5 h-3.5 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
                              </svg>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Citations */}
                {response && response.citations.length > 0 && (
                  <div className={`rounded-2xl p-5 ${darkMode ? 'bg-neutral-900 border border-neutral-800' : 'bg-gray-50 border border-gray-200'}`}>
                    <h3 className={`text-sm font-semibold mb-4 flex items-center gap-2 ${darkMode ? 'text-gray-200' : 'text-gray-700'}`}>
                      <svg className="w-4 h-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      Sources
                    </h3>
                    <div className="space-y-2">
                      {response.citations.map((cite, idx) => {
                        const isWikEM = cite.source_type === "wikem";
                        const isPMC = cite.source_type === "pmc";
                        const isLITFL = cite.source_type === "litfl";
                        return (
                          <a
                            key={idx}
                            href={cite.source_uri}
                            target="_blank"
                            rel="noopener noreferrer"
                            className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all text-sm ${darkMode ? 'text-blue-400 hover:bg-neutral-800' : 'text-blue-600 hover:bg-white hover:shadow-sm'}`}
                          >
                            <span className={`w-6 h-6 flex items-center justify-center rounded text-xs font-medium ${
                              isPMC
                                ? (darkMode ? 'bg-purple-900/50 text-purple-300' : 'bg-purple-100 text-purple-700')
                                : isLITFL
                                  ? (darkMode ? 'bg-orange-900/50 text-orange-300' : 'bg-orange-100 text-orange-700')
                                  : isWikEM 
                                    ? (darkMode ? 'bg-emerald-900/50 text-emerald-300' : 'bg-emerald-100 text-emerald-700')
                                    : (darkMode ? 'bg-blue-900/50 text-blue-300' : 'bg-blue-100 text-blue-700')
                            }`}>{idx + 1}</span>
                            <span className="flex-1 truncate">{cite.protocol_id.replace(/_/g, " ")}</span>
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider whitespace-nowrap ${
                              isPMC
                                ? (darkMode ? 'bg-purple-900/50 text-purple-400' : 'bg-purple-100 text-purple-700')
                                : isLITFL
                                  ? (darkMode ? 'bg-orange-900/50 text-orange-400' : 'bg-orange-100 text-orange-700')
                                  : isWikEM
                                    ? (darkMode ? 'bg-emerald-900/50 text-emerald-400' : 'bg-emerald-100 text-emerald-700')
                                    : (darkMode ? 'bg-blue-900/50 text-blue-400' : 'bg-blue-100 text-blue-700')
                            }`}>
                              {isPMC ? '📚 PMC' : isLITFL ? '⚡ LITFL' : isWikEM ? 'WikEM' : 'Local'}
                            </span>
                            <svg className="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                            </svg>
                          </a>
                        );
                      })}
                    </div>
                    {response.citations.some(c => c.source_type === "wikem") && (
                      <p className={`mt-3 text-[11px] ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                        WikEM content from <a href="https://wikem.org" target="_blank" rel="noopener noreferrer" className="underline">wikem.org</a> under CC BY-SA 3.0
                      </p>
                    )}
                    {response.citations.some(c => c.source_type === "pmc") && (
                      <p className={`mt-3 text-[11px] ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                        PMC literature from <a href="https://www.ncbi.nlm.nih.gov/pmc/" target="_blank" rel="noopener noreferrer" className="underline">PubMed Central</a> — peer-reviewed EM research
                      </p>
                    )}
                    {response.citations.some(c => c.source_type === "litfl") && (
                      <p className={`mt-3 text-[11px] ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                        LITFL content from <a href="https://litfl.com" target="_blank" rel="noopener noreferrer" className="underline">litfl.com</a> under CC BY-NC-SA 4.0 — FOAMed education resource
                      </p>
                    )}
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
          <div className={`max-w-3xl mx-auto border-2 rounded-3xl shadow-lg transition-all duration-200 ${
            darkMode 
              ? 'bg-neutral-900 border-neutral-700 focus-within:border-blue-500 focus-within:ring-4 focus-within:ring-blue-900' 
              : 'bg-gray-50 border-gray-300 focus-within:border-blue-400 focus-within:ring-4 focus-within:ring-blue-100'
          }`}>
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
              rows={1}
              className={`w-full p-4 pl-5 pr-4 rounded-t-3xl text-sm resize-none focus:outline-none bg-transparent ${
                darkMode 
                  ? 'text-gray-100 placeholder-gray-500' 
                  : 'text-gray-800'
              }`}
            />

            {/* Bottom bar */}
            <div className="flex items-center justify-between px-4 pb-3 pt-0">
              {/* Source toggles + ED filters */}
              <div className="flex items-center gap-1">
                <button
                  onClick={() => toggleSource("wikem")}
                  title="ED Universe — WikEM topics + PMC peer-reviewed literature"
                  className={`p-1.5 rounded-lg transition-all duration-200 ${
                    globeActive
                      ? darkMode
                        ? 'bg-blue-600/20 text-blue-400'
                        : 'bg-blue-50 text-blue-600'
                      : darkMode
                        ? 'text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800'
                        : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <Globe className="w-4 h-4" />
                </button>
                {enterprise?.eds.filter((ed) => selectedEds.has(ed.id)).map((ed) => (
                    <button
                      key={ed.id}
                      onClick={() => toggleEdSelection(ed.id)}
                      title={ed.location ? `${ed.name} — ${ed.location}` : ed.name}
                      className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all duration-200 ${
                        darkMode
                          ? 'bg-blue-600/20 text-blue-400 border border-blue-600/30'
                          : 'bg-blue-50 text-blue-600 border border-blue-200'
                      }`}
                    >
                      {ed.name}
                    </button>
                ))}
              </div>

              {/* Right side */}
              <div className="flex items-center gap-2">
                <button
                  title="Voice input"
                  className={`w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-200 ${
                    darkMode 
                      ? 'text-gray-400 hover:bg-neutral-800 hover:text-gray-200' 
                      : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'
                  }`}
                >
                  <Mic className="w-4 h-4" />
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={!question.trim() || loading || isStreaming}
                  title="Submit"
                  className={`w-8 h-8 rounded-lg text-white flex items-center justify-center transition-all duration-200 hover:scale-105 disabled:opacity-50 disabled:hover:scale-100 ${
                    darkMode ? 'bg-blue-600 hover:bg-blue-500' : 'bg-black hover:bg-gray-800'
                  }`}
                >
                  {loading || isStreaming ? (
                    <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <ArrowUp className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Image Lightbox Modal */}
      {lightboxImage && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm"
          onClick={() => setLightboxImage(null)}
          onKeyDown={(e) => { if (e.key === "Escape") setLightboxImage(null); }}
          tabIndex={0}
          role="dialog"
          aria-modal="true"
        >
          <div className="relative max-w-[90vw] max-h-[90vh]" onClick={(e) => e.stopPropagation()}>
            {/* Close button */}
            <button
              onClick={() => setLightboxImage(null)}
              className="absolute -top-3 -right-3 z-10 w-8 h-8 rounded-full bg-neutral-800 text-white flex items-center justify-center hover:bg-neutral-700 shadow-lg"
            >
              <X className="w-4 h-4" />
            </button>
            {/* Image */}
            <img
              src={lightboxImage.url}
              alt={`Protocol diagram from ${lightboxImage.protocol_id}, page ${lightboxImage.page}`}
              className="max-w-[90vw] max-h-[85vh] object-contain rounded-xl shadow-2xl"
            />
            {/* Caption */}
            <div className="mt-3 text-center text-sm text-gray-300">
              {lightboxImage.protocol_id.replace(/_/g, " ")} · Page {lightboxImage.page}
            </div>
          </div>
        </div>
      )}

      </main>
    </div>
  );
}

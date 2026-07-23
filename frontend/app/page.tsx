"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, LogOut, ChevronDown, ChevronRight, ChevronLeft, ChevronUp, ArrowUp, Plus, MessageSquare, X, Trash2, Building2, Check, Crown, Shield, Globe, FileText, BookOpen, Save, ThumbsUp, ThumbsDown, Upload, FolderOpen, Star, Bookmark } from "lucide-react";
import ReactMarkdown, { Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAuth } from "@/lib/auth-context";
import ProtocolCard, { ProtocolCardData } from "@/components/ProtocolCard";
import { Capacitor } from "@capacitor/core";
import { StatusBar, Style } from "@capacitor/status-bar";
import { Keyboard, KeyboardStyle } from "@capacitor/keyboard";
import { openExternal } from "@/lib/native-links";
import { useSpeechInput } from "@/lib/useSpeechInput";
import MicButton from "@/components/MicButton";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://em-protocol-api-930035889332.us-central1.run.app";
const STORAGE_KEY = "em-protocol-conversations";
const THEME_KEY = "em-protocol-theme";
const BUNDLE_KEY = "em-protocol-selected-bundles";
// Tracks which bundle IDs this client has already seen, so a newly-added bundle
// (e.g. "whiteboard") auto-joins an existing user's selection instead of being
// silently excluded by their stale saved selection. See fetchEnterprise().
const KNOWN_BUNDLE_KEY = "em-protocol-known-bundles";
const ED_KEY = "em-protocol-selected-eds";
const UNIVERSE_KEY = "em-protocol-ed-universe";
const FAVORITES_KEY = "em-protocol-favorites";

// PMC Journal registry — key is the exact string stored in GCS metadata.
// Reflects the CURATED PMC corpus set (docs/pmc-sharding-workstream.md): only
// the 22 journals actually indexed across the 3 curated corpora (pmc-em,
// pmc-critical-care, pmc-high-impact). JAMA Family (all 10), Am J Respir Crit
// Care Med, Ann Intern Med, Lancet Respir Med, Mayo Clin Proc, and Lancet
// Neurol were dropped and are NOT searchable — so they must not be offered as
// filter options here. Counts from the July 2026 manifest.
// (Future: serve this from GET /pmc/journals so re-scrapes don't need a code
// edit; deferred because the backend registry doesn't yet carry display labels.)
interface PmcJournal { key: string; label: string; count: number }
interface PmcJournalGroup { group: string; journals: PmcJournal[] }

const PMC_JOURNAL_GROUPS: PmcJournalGroup[] = [
  {
    group: "Emergency Medicine",
    journals: [
      { key: "The Western Journal of Emergency Medicine", label: "Western J EM", count: 2064 },
      { key: "Journal of the American College of Emergency Physicians Open", label: "JACEP Open", count: 1587 },
      { key: "The American Journal of Emergency Medicine", label: "Am J Emerg Med", count: 877 },
      { key: "Annals of Emergency Medicine", label: "Annals of EM", count: 674 },
      { key: "Acad Emerg Med", label: "Academic EM", count: 590 },
      { key: "The Journal of Emergency Medicine", label: "J Emerg Med", count: 259 },
      { key: "Pediatric Emergency Care", label: "Peds Emerg Care", count: 246 },
      { key: "CJEM", label: "CJEM", count: 212 },
      { key: "Advanced Journal of Emergency Medicine", label: "Adv J Emerg Med", count: 146 },
      { key: "Prehospital Emergency Care", label: "Prehosp Emerg Care", count: 111 },
      { key: "Eur J Emerg Med", label: "Eur J Emerg Med", count: 108 },
      { key: "Air Medical Journal", label: "Air Med Journal", count: 86 },
    ],
  },
  {
    group: "Critical Care & Resuscitation",
    journals: [
      { key: "Chest", label: "CHEST", count: 2838 },
      { key: "Crit Care Med", label: "Crit Care Med", count: 1469 },
      { key: "Resuscitation Plus", label: "Resuscitation Plus", count: 1205 },
      { key: "Shock", label: "Shock", count: 691 },
      { key: "Resuscitation", label: "Resuscitation", count: 525 },
      { key: "J Intensive Care Med", label: "J Intensive Care Med", count: 244 },
    ],
  },
  {
    group: "High-Impact General",
    journals: [
      { key: "Lancet", label: "The Lancet", count: 2667 },
      { key: "BMJ", label: "BMJ", count: 2598 },
      { key: "N Engl J Med", label: "NEJM", count: 1822 },
      { key: "Lancet Infect Dis", label: "Lancet Infect Dis", count: 1619 },
    ],
  },
];

// Flat list + derived constants (backward-compatible)
const PMC_JOURNALS: PmcJournal[] = PMC_JOURNAL_GROUPS.flatMap(g => g.journals);
const ALL_PMC_JOURNAL_KEYS = PMC_JOURNALS.map(j => j.key);
const TOTAL_PMC_COUNT = PMC_JOURNALS.reduce((sum, j) => sum + j.count, 0);

// Helper: get all keys for a group
const getGroupKeys = (group: PmcJournalGroup): string[] => group.journals.map(j => j.key);

interface QueryResponse {
  answer: string;
  images: { page: number; url: string; protocol_id: string }[];
  citations: {
    protocol_id: string;
    source_uri: string;
    relevance_score: number;
    source_type: string;
    source_grade?: string;
    source_grade_label?: string;
    source_domain?: string;
    is_preferred_em_source?: boolean;
  }[];
  query_time_ms: number;
  route?: string;
  sources?: string[];
}

// One completed prior turn in a multi-turn thread (kept compact for the
// transcript + for sending conversation history to the backend).
interface Turn {
  question: string;
  answer: string;
}

interface Conversation {
  id: string;
  title: string;
  timestamp: string; // Changed to string for JSON serialization
  question: string;              // latest (current) turn's question
  response: QueryResponse | null; // latest (current) turn's response
  mode?: string;
  protocolCards?: ProtocolCardData[];
  turns?: Turn[];                // prior turns (before the current one)
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


function getRouteDisplay(route?: string, sources?: string[]) {
  // Base the "restricted search" note on what was ACTUALLY searched (sources),
  // not the keyword route. The word "protocol" no longer forces local-only, so
  // only claim a restricted search when the sources were genuinely limited.
  const only = sources && sources.length === 1 ? sources[0] : null;

  if (only === "personal" || route === "personal") {
    return {
      label: "Your uploaded files",
      detail: "Searched your personal files only.",
    };
  }

  if (only === "local") {
    return {
      label: "Department protocols",
      detail: "Searched your local protocol library only.",
    };
  }

  // Broad, multi-source search (incl. queries containing "protocol"): don't
  // claim local-only — the Sources list shows the mix that was searched.
  return {
    label: "All selected sources",
    detail: "Searched your protocols and selected clinical references.",
  };
}

// Keep at most this many conversations open as full swipeable columns. Older
// ones drop out of the column row but remain in the left drawer's history and
// reopen (as a column) on click.
const MAX_OPEN_PANELS = 5;

export default function Home() {
  const [question, setQuestion] = useState("");
  const { isSupported: micSupported, listening: micListening, permissionDenied: micPermissionDenied, toggle: toggleMic } = useSpeechInput();
  const [submittedQuestion, setSubmittedQuestion] = useState("");
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [streamingAnswer, setStreamingAnswer] = useState<string>("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [searchFocused, setSearchFocused] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  // References/Sources are collapsed by default; expand on demand.
  const [showSources, setShowSources] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  // Prior turns of the active conversation (rendered as a transcript above the
  // current answer, and sent to the backend as history for multi-turn context).
  const [priorTurns, setPriorTurns] = useState<Turn[]>([]);
  // Conversations open as side-by-side columns (patient workspace). Oldest→newest,
  // left→right. The active column (currentConversationId) is live; the rest are
  // static snapshots you can click to resume.
  const [openPanels, setOpenPanels] = useState<string[]>([]);
  // Horizontal columns row — used to center the active conversation column.
  const columnsRowRef = useRef<HTMLDivElement>(null);
  const [darkMode, setDarkMode] = useState(false);
  const [typedPlaceholder, setTypedPlaceholder] = useState("");

  // Protocol cards state
  const [protocolCards, setProtocolCards] = useState<ProtocolCardData[]>([]);
  const [favoriteProtocols, setFavoriteProtocols] = useState<ProtocolCardData[]>([]);
  const [highlightedProtocols, setHighlightedProtocols] = useState<ProtocolCardData[]>([]);
  const [highlightedOpen, setHighlightedOpen] = useState(false);
  const [favoritesOpen, setFavoritesOpen] = useState(false);
  
  // Enterprise/ED/Bundle selection state
  const [enterprise, setEnterprise] = useState<EnterpriseData | null>(null);
  const [selectedEds, setSelectedEds] = useState<Set<string>>(new Set());
  const [selectedBundles, setSelectedBundles] = useState<Set<string>>(new Set());
  // Guards the bundle→localStorage save effect so it doesn't clobber the saved
  // selection with the initial empty set before fetchEnterprise reconciles it.
  const bundlesInitialized = useRef(false);
  const [expandedHospitals, setExpandedHospitals] = useState<Set<string>>(new Set());

  // EM Universe state
  const [settingsCollapsed, setSettingsCollapsed] = useState(false); // settings panel default open
  const [conversationsExpanded, setConversationsExpanded] = useState(false); // collapse long list so settings stay visible
  const [wikemEnabled, setWikemEnabled] = useState(true);
  const [pmcEnabled, setPmcEnabled] = useState(true);
  const [litflEnabled, setLitflEnabled] = useState(true);
  const [rebelemEnabled, setRebelemEnabled] = useState(true);
  const [aliemEnabled, setAliemEnabled] = useState(true);
  const [personalEnabled, setPersonalEnabled] = useState(false);
  const [selectedJournals, setSelectedJournals] = useState<Set<string>>(new Set(ALL_PMC_JOURNAL_KEYS));
  const [wikemExpanded, setWikemExpanded] = useState(false);
  const [pmcExpanded, setPmcExpanded] = useState(false);
  const [litflExpanded, setLitflExpanded] = useState(false);
  const [rebelemExpanded, setRebelemExpanded] = useState(false);
  const [aliemExpanded, setAliemExpanded] = useState(false);
  const [universeDirty, setUniverseDirty] = useState(false); // track unsaved changes

  // Lightbox state for image enlargement
  const [lightboxImage, setLightboxImage] = useState<{ url: string; protocol_id: string; page: number } | null>(null);

  // Feedback state
  const [feedbackRating, setFeedbackRating] = useState<"up" | "down" | null>(null);
  const [feedbackReasons, setFeedbackReasons] = useState<Set<string>>(new Set());
  const [feedbackComment, setFeedbackComment] = useState("");
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);

  // Toggle wikem source on/off (can be turned off if EDs are selected)
  // Globe toggles ALL external sources together
  const toggleSource = (source: string) => {
    if (source === "wikem") {
      const isCurrentlyOn = wikemEnabled || pmcEnabled || litflEnabled || rebelemEnabled || aliemEnabled;
      if (isCurrentlyOn) {
        // Turn off all — only if we have EDs selected (need at least one source)
        if (selectedEds.size > 0) {
          setWikemEnabled(false);
          setPmcEnabled(false);
          setLitflEnabled(false);
          setRebelemEnabled(false);
          setAliemEnabled(false);
        }
      } else {
        // Turn all back on
        setWikemEnabled(true);
        setPmcEnabled(true);
        setLitflEnabled(true);
        setRebelemEnabled(true);
        setAliemEnabled(true);
      }
    }
  };

  // Derive the effective sources array for API calls
  const getEffectiveSources = (): string[] => {
    const sources: string[] = [];
    // Only include local Mayo protocols if user has access
    if (selectedEds.size > 0 && hasAccess) sources.push("local");
    if (wikemEnabled) sources.push("wikem");
    if (pmcEnabled && selectedJournals.size > 0) sources.push("pmc");
    if (litflEnabled) sources.push("litfl");
    if (rebelemEnabled) sources.push("rebelem");
    if (aliemEnabled) sources.push("aliem");
    if (personalEnabled && (user || userProfile)) sources.push("personal");
    return sources;
  };

  // Derive the effective PMC journal filter (null = no filter = all)
  const getEffectivePmcJournals = (): string[] | undefined => {
    if (!pmcEnabled) return undefined;
    if (selectedJournals.size === ALL_PMC_JOURNAL_KEYS.length) return undefined; // all selected = no filter
    return Array.from(selectedJournals);
  };

  // Is the globe "on"? (any external source is active)
  const globeActive = wikemEnabled || pmcEnabled || litflEnabled || rebelemEnabled || aliemEnabled;

  // Display override: the "rochester" ED shows as "RST" in the UI (id/search
  // unchanged). Cosmetic stopgap until Firestore is re-seeded with the new name.
  const edLabel = (ed: { id: string; name: string }) => (ed.id === "rochester" ? "RST" : ed.name);

  // The active conversation column is "empty" (a fresh New conversation) — show
  // the prompt to type into rather than an (empty) answer thread.
  const activeIsEmpty = !submittedQuestion && !response && !isStreaming && !loading && priorTurns.length === 0;

  // Data-source filter chip styling (Figma FILTERS row)
  const sourceChipClass = (active: boolean) =>
    `inline-flex items-center px-3 py-1.5 rounded-[4px] text-xs font-data font-semibold uppercase tracking-wide border-[1.5px] transition-colors ${
      active
        ? 'bg-[#013DED] border-[#013DED] text-white'
        : darkMode
          ? 'bg-transparent border-[#24305C] text-[#6B7699] hover:border-[#013DED] hover:text-[#013DED]'
          : 'bg-white border-gray-300 text-gray-500 hover:border-[#013DED] hover:text-[#013DED]'
    }`;

  // Save EM Universe preferences to localStorage
  const saveUniversePreferences = () => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(UNIVERSE_KEY, JSON.stringify({
        wikemEnabled,
        pmcEnabled,
        litflEnabled,
        rebelemEnabled,
        aliemEnabled,
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

  // Toggle an entire PMC journal group
  const toggleGroup = (group: PmcJournalGroup) => {
    const keys = getGroupKeys(group);
    setSelectedJournals(prev => {
      const next = new Set(prev);
      const allSelected = keys.every(k => next.has(k));
      if (allSelected) {
        keys.forEach(k => next.delete(k));
      } else {
        keys.forEach(k => next.add(k));
      }
      return next;
    });
    setUniverseDirty(true);
  };

  // Track which PMC groups are expanded in the UI
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const toggleGroupExpanded = (groupName: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(groupName)) next.delete(groupName);
      else next.add(groupName);
      return next;
    });
  };

  const { user, userProfile, loading: authLoading, isSignedIn, hasAccess, signOut, getIdToken, submitAccessRequest, refreshProfile } = useAuth();
  const router = useRouter();

  // Mayo access request form state (shown in bundle section for non-approved users)
  const [requestName, setRequestName] = useState("");
  const [requestEmail, setRequestEmail] = useState("");
  const [requestError, setRequestError] = useState<string | null>(null);
  const [requestSuccess, setRequestSuccess] = useState<string | null>(null);
  const [requestLoading, setRequestLoading] = useState(false);
  const [showRequestForm, setShowRequestForm] = useState(false);

  const routeDisplay = getRouteDisplay(response?.route, response?.sources);

  // Load theme from localStorage on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const savedTheme = localStorage.getItem(THEME_KEY);
      if (savedTheme) {
        setDarkMode(savedTheme === 'dark');
      } else {
        // Default to light mode (white + dot grid) for new users
        setDarkMode(false);
      }

      // Load EM Universe preferences
      const savedUniverse = localStorage.getItem(UNIVERSE_KEY);
      if (savedUniverse) {
        try {
          const prefs = JSON.parse(savedUniverse);
          if (typeof prefs.wikemEnabled === 'boolean') setWikemEnabled(prefs.wikemEnabled);
          if (typeof prefs.pmcEnabled === 'boolean') setPmcEnabled(prefs.pmcEnabled);
          if (typeof prefs.litflEnabled === 'boolean') setLitflEnabled(prefs.litflEnabled);
          if (typeof prefs.rebelemEnabled === 'boolean') setRebelemEnabled(prefs.rebelemEnabled);
          if (typeof prefs.aliemEnabled === 'boolean') setAliemEnabled(prefs.aliemEnabled);
          if (Array.isArray(prefs.selectedJournals)) {
            setSelectedJournals(new Set(prefs.selectedJournals));
          }
        } catch (e) {
          console.warn("Failed to load EM Universe preferences", e);
        }
      }

      // Load favorite protocols
      const savedFavorites = localStorage.getItem(FAVORITES_KEY);
      if (savedFavorites) {
        try {
          const favs = JSON.parse(savedFavorites);
          if (Array.isArray(favs)) setFavoriteProtocols(favs);
        } catch (e) {
          console.warn("Failed to load favorite protocols", e);
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

  // Match the native status bar and keyboard to the active theme
  useEffect(() => {
    if (Capacitor.isNativePlatform()) {
      StatusBar.setStyle({ style: darkMode ? Style.Dark : Style.Light });
      StatusBar.setBackgroundColor({ color: darkMode ? '#0B1535' : '#F8F9FA' });
      Keyboard.setStyle({ style: darkMode ? KeyboardStyle.Dark : KeyboardStyle.Light });
    }
  }, [darkMode]);

  // Typewriter effect for the search prompt — signals the field is typeable
  useEffect(() => {
    if (hasSearched) return;
    const full = "What's the emergency?";
    setTypedPlaceholder("");
    let i = 0;
    let timer: ReturnType<typeof setTimeout>;
    const tick = () => {
      i += 1;
      setTypedPlaceholder(full.slice(0, i));
      if (i < full.length) {
        timer = setTimeout(tick, 42);
      }
    };
    timer = setTimeout(tick, 350);
    return () => clearTimeout(timer);
  }, [hasSearched]);

  // Center the active conversation column when it changes (new / resumed).
  useEffect(() => {
    if (!hasSearched) return;
    const t = setTimeout(() => {
      const el = columnsRowRef.current?.querySelector('[data-active-column="true"]') as HTMLElement | null;
      el?.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
    }, 60);
    return () => clearTimeout(t);
  }, [currentConversationId, openPanels.length, hasSearched]);

  // Save favorite protocols to localStorage
  useEffect(() => {
    if (typeof window !== 'undefined' && favoriteProtocols.length > 0) {
      localStorage.setItem(FAVORITES_KEY, JSON.stringify(favoriteProtocols));
    }
  }, [favoriteProtocols]);

  // Toggle a protocol as favorite
  const toggleFavorite = useCallback((card: ProtocolCardData) => {
    setFavoriteProtocols(prev => {
      const exists = prev.some(f => f.protocol_id === card.protocol_id);
      if (exists) {
        const next = prev.filter(f => f.protocol_id !== card.protocol_id);
        // Clear from localStorage if empty
        if (next.length === 0 && typeof window !== 'undefined') {
          localStorage.removeItem(FAVORITES_KEY);
        }
        return next;
      } else {
        return [...prev, card];
      }
    });
  }, []);

  // Check if a protocol is favorited
  const isFavorited = useCallback((protocolId: string) => {
    return favoriteProtocols.some(f => f.protocol_id === protocolId);
  }, [favoriteProtocols]);

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

        // Reconcile bundle selection against the live bundle list. There is no
        // bundle-picker UI, so selectedBundles is otherwise frozen at whatever
        // existed on a user's first load — meaning a later-added bundle (e.g.
        // "whiteboard") would be silently excluded from their queries forever.
        // Fix: auto-include any bundle this client hasn't seen before.
        const allBundleIds = new Set<string>();
        for (const ed of data.eds) {
          for (const b of ed.bundles) {
            allBundleIds.add(b.id);
          }
        }
        const savedBundles = localStorage.getItem(BUNDLE_KEY);
        if (!savedBundles) {
          // First-time user: select everything.
          setSelectedBundles(allBundleIds);
        } else {
          // Existing user: keep their saved selection, but add bundles that are
          // new since we last saw them. "Known" seeds from their saved selection
          // on first migration, so genuinely-new bundles get auto-included.
          const saved: string[] = JSON.parse(savedBundles);
          const knownRaw = localStorage.getItem(KNOWN_BUNDLE_KEY);
          const known = new Set<string>(knownRaw ? JSON.parse(knownRaw) : saved);
          const merged = new Set<string>(saved);
          for (const id of allBundleIds) {
            if (!known.has(id)) merged.add(id);
          }
          setSelectedBundles(merged);
        }
        localStorage.setItem(KNOWN_BUNDLE_KEY, JSON.stringify(Array.from(allBundleIds)));
        bundlesInitialized.current = true;
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
    if ((user || userProfile) && hasAccess) {
      fetchEnterprise();
    }
  }, [user, userProfile, hasAccess, fetchEnterprise]);

  // Fetch highlighted protocols for the user's enterprise
  useEffect(() => {
    if (!enterprise?.id) return;
    const fetchHighlighted = async () => {
      try {
        const token = await getIdToken();
        if (!token) return;
        const res = await fetch(`${API_URL}/enterprise/highlighted?enterprise_id=${encodeURIComponent(enterprise.id)}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setHighlightedProtocols(data.highlighted || []);
        }
      } catch (err) {
        console.error("Failed to fetch highlighted protocols:", err);
      }
    };
    fetchHighlighted();
  }, [enterprise?.id, getIdToken]);

  // (Bundle selection is initialized + reconciled in fetchEnterprise, which has
  // the live bundle list needed to auto-include newly-added bundles. A separate
  // mount effect that loaded the raw saved set used to race with — and clobber —
  // that reconciliation, re-excluding new bundles; it was removed.)

  // Save selected bundles to localStorage (only after fetchEnterprise has
  // reconciled them — otherwise the initial empty set would clobber the saved
  // selection before it's read).
  useEffect(() => {
    if (!bundlesInitialized.current) return;
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
    if (!user && !userProfile) {
      router.push("/login");
      return;
    }

    // Build thread history from the active conversation BEFORE starting the new
    // turn. The active conversation's question/response is the outgoing (current)
    // turn; its `turns` are the turns before that. Together they are the context.
    const activeConv = conversations.find(c => c.id === currentConversationId);
    const threadPriorTurns: Turn[] = activeConv?.turns ? [...activeConv.turns] : [];
    if (activeConv?.response && activeConv?.question) {
      threadPriorTurns.push({ question: activeConv.question, answer: activeConv.response.answer });
    }
    const history = threadPriorTurns.flatMap(t => [
      { role: "user" as const, content: t.question },
      { role: "assistant" as const, content: t.answer },
    ]);
    setPriorTurns(threadPriorTurns);

    // Capture the question and clear the input immediately
    const submittedQuestion = question.trim();
    setSubmittedQuestion(submittedQuestion);
    setQuestion("");

    // Contextualize follow-ups so the retrieval query is self-contained (a bare
    // "for adults" retrieves nothing useful). Anchors on the thread's opening
    // topic; keeps the displayed question as the raw follow-up. This makes
    // multi-turn work even before the history-aware backend is deployed.
    const topic = threadPriorTurns[0]?.question;
    const apiQuery = topic && topic !== submittedQuestion
      ? `${topic}. Follow-up: ${submittedQuestion}`.slice(0, 490)
      : submittedQuestion;
    
    setLoading(true);
    setIsStreaming(false);
    setStreamingAnswer("");
    setResponse(null);
    setProtocolCards([]);
    setError(null);
    setHasSearched(true);
    setFeedbackRating(null);
    setFeedbackReasons(new Set());
    setFeedbackComment("");
    setFeedbackSubmitted(false);

    // Create a new conversation if we don't have one
    const conversationId = currentConversationId || `conv-${Date.now()}`;
    if (!currentConversationId) {
      setCurrentConversationId(conversationId);
    }
    // Ensure this conversation is an open column
    setOpenPanels(prev => prev.includes(conversationId) ? prev : [...prev, conversationId].slice(-MAX_OPEN_PANELS));

    // --- Q&A mode (existing logic) ---
    try {
      const token = await getIdToken();
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      // Fire /query and /protocol-summary in parallel (fusion mode)
      const queryFetch = fetch(`${API_URL}/query`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          query: apiQuery,
          history,
          ed_ids: Array.from(selectedEds),
          bundle_ids: selectedBundles.size > 0 ? Array.from(selectedBundles) : ["all"],
          include_images: true,
          sources: getEffectiveSources(),
          pmc_journals: getEffectivePmcJournals(),
          enterprise_id: enterprise?.id || undefined
        }),
      });

      // Only fetch protocol cards if local protocols are enabled (EDs selected)
      const hasLocalSource = selectedEds.size > 0;
      const protocolFetch = hasLocalSource
        ? fetch(`${API_URL}/protocol-summary`, {
            method: "POST",
            headers,
            body: JSON.stringify({
              query: apiQuery,
              ed_ids: Array.from(selectedEds),
              bundle_ids: selectedBundles.size > 0 ? Array.from(selectedBundles) : ["all"],
              enterprise_id: enterprise?.id || undefined,
            }),
          })
        : null;

      // Process protocol-summary stream in the background (non-blocking)
      const cards: ProtocolCardData[] = [];
      if (protocolFetch) {
        protocolFetch.then(async (protoRes) => {
          if (!protoRes.ok) return; // silently skip on error
          const protoReader = protoRes.body?.getReader();
          if (!protoReader) return;
          const protoDecoder = new TextDecoder();
          let protoBuf = "";
          while (true) {
            const { done, value } = await protoReader.read();
            if (done) break;
            protoBuf += protoDecoder.decode(value, { stream: true });
            const protoLines = protoBuf.split("\n");
            protoBuf = protoLines.pop() || "";
            for (const line of protoLines) {
              if (!line.startsWith("data: ")) continue;
              const jsonStr = line.slice(6).trim();
              if (!jsonStr) continue;
              try {
                const event = JSON.parse(jsonStr);
                if (event.type === "protocol_card") {
                  cards.push(event as ProtocolCardData);
                  setProtocolCards([...cards]);
                }
              } catch { /* skip parse errors */ }
            }
          }
        }).catch(() => {}); // silently ignore protocol-summary errors
      }

      const res = await queryFetch;
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
                query_time_ms: event.query_time_ms || 0,
                route: event.route,
                sources: event.sources,
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

      // Save conversation to history (include protocol cards from fusion)
      const savedResponse = finalData || { answer: fullAnswer, images: [], citations: [], query_time_ms: 0 };
      const newConversation: Conversation = {
        id: conversationId,
        title: (threadPriorTurns[0]?.question || submittedQuestion).slice(0, 50) + ((threadPriorTurns[0]?.question || submittedQuestion).length > 50 ? "..." : ""),
        timestamp: new Date().toISOString(),
        question: submittedQuestion,
        response: savedResponse,
        mode: "qa",
        protocolCards: cards.length > 0 ? cards : undefined,
        turns: threadPriorTurns.length > 0 ? threadPriorTurns : undefined,
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
    // Open a fresh conversation as a new column to the right (don't leave the
    // workspace). The new column shows the empty prompt to type into.
    const newId = `conv-${Date.now()}`;
    setOpenPanels(prev => [...prev, newId].slice(-MAX_OPEN_PANELS));
    setCurrentConversationId(newId);
    setQuestion("");
    setResponse(null);
    setStreamingAnswer("");
    setIsStreaming(false);
    setLoading(false);
    setError(null);
    setProtocolCards([]);
    setPriorTurns([]);
    setSubmittedQuestion("");
    setHasSearched(true);
    setSidebarOpen(false);
  };

  const loadConversation = (conversation: Conversation) => {
    setQuestion("");
    setSubmittedQuestion(conversation.question);
    setResponse(conversation.response);
    setProtocolCards(conversation.protocolCards || []);
    setPriorTurns(conversation.turns || []);
    setHasSearched(true);
    setCurrentConversationId(conversation.id);
    setOpenPanels(prev => prev.includes(conversation.id) ? prev : [...prev, conversation.id].slice(-MAX_OPEN_PANELS));
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
    setStreamingAnswer("");
    setIsStreaming(false);
    setLoading(false);
    setProtocolCards([]);
    setError(null);
    setHasSearched(false);
    setCurrentConversationId(null);
    setPriorTurns([]);
    setSubmittedQuestion("");
  };

  const handleSignOut = async () => {
    await signOut();
    setShowUserMenu(false);
  };

  // ───── Protocol click tracking ─────
  const trackProtocolClick = async (card: ProtocolCardData) => {
    try {
      const token = await user?.getIdToken();
      if (!token) return;
      fetch(`${API_URL}/analytics/protocol-click`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          protocol_id: card.protocol_id,
          title: card.protocol_id.replace(/_/g, " ").replace(/\.pdf$/i, ""),
          enterprise_id: card.enterprise_id || "",
        }),
      }).catch(() => {}); // fire-and-forget
    } catch {
      // never block user navigation
    }
  };

  // ───── Feedback submission ─────
  const FEEDBACK_REASONS = [
    "Incorrect information",
    "Incomplete response",
    "Poor structure",
    "Irrelevant citations",
    "Not clinically useful",
    "Other",
  ];

  const handleFeedbackSubmit = async (ratingOverride?: "up" | "down") => {
    const rating = ratingOverride || feedbackRating;
    if (!rating) return;
    setFeedbackSubmitting(true);
    try {
      await fetch(`${API_URL}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: question || "",
          rating,
          reasons: Array.from(feedbackReasons),
          comment: feedbackComment,
          user_email: user?.email || userProfile?.email || "anonymous",
        }),
      });
      setFeedbackSubmitted(true);
    } catch {
      // Silently fail — feedback is non-critical
    } finally {
      setFeedbackSubmitting(false);
    }
  };

  const toggleFeedbackReason = (reason: string) => {
    setFeedbackReasons(prev => {
      const next = new Set(prev);
      if (next.has(reason)) next.delete(reason);
      else next.add(reason);
      return next;
    });
  };

  // ───── Citation-aware Markdown components ─────
  // Converts inline [N] references into superscript links that scroll to the
  // matching citation and show a tooltip on hover with the source name.
  const citationComponents: Components = {
    table: ({ children, ...props }) => (
      <div className="overflow-x-auto -mx-1 px-1">
        <table {...props}>{children}</table>
      </div>
    ),
    p: ({ children, ...props }) => {
      const citations = response?.citations ?? [];
      const processNode = (node: React.ReactNode): React.ReactNode => {
        if (typeof node !== "string") return node;
        // Split on [N] patterns, keeping the match
        const parts = node.split(/(\[\d+\])/g);
        if (parts.length === 1) return node;
        return parts.map((part, i) => {
          const m = part.match(/^\[(\d+)\]$/);
          if (!m) return part;
          const num = parseInt(m[1], 10);
          const cite = citations[num - 1];
          const label = cite ? cite.protocol_id.replace(/_/g, " ") : `Source ${num}`;
          return (
            <span key={i} className="cite-ref-wrapper">
              <a
                href={cite?.source_uri || `#cite-${num}`}
                target={cite?.source_uri ? "_blank" : undefined}
                rel={cite?.source_uri ? "noopener noreferrer" : undefined}
                onClick={(e) => {
                  if (!cite?.source_uri) {
                    e.preventDefault();
                    document.getElementById(`cite-${num}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
                  }
                }}
                className={`cite-ref ${darkMode ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-500'}`}
              >
                <sup>{num}</sup>
              </a>
              <span className={`cite-tooltip ${darkMode ? 'bg-[#1E1E1E] text-gray-200 border-[#2A2A2A]' : 'bg-white text-gray-800 border-gray-200'}`}>
                {label}
              </span>
            </span>
          );
        });
      };
      return (
        <p {...props}>
          {Array.isArray(children) ? children.map((child, i) => <React.Fragment key={i}>{processNode(child)}</React.Fragment>) : processNode(children)}
        </p>
      );
    },
    li: ({ children, ...props }) => {
      const citations = response?.citations ?? [];
      const processNode = (node: React.ReactNode): React.ReactNode => {
        if (typeof node !== "string") return node;
        const parts = node.split(/(\[\d+\])/g);
        if (parts.length === 1) return node;
        return parts.map((part, i) => {
          const m = part.match(/^\[(\d+)\]$/);
          if (!m) return part;
          const num = parseInt(m[1], 10);
          const cite = citations[num - 1];
          const label = cite ? cite.protocol_id.replace(/_/g, " ") : `Source ${num}`;
          return (
            <span key={i} className="cite-ref-wrapper">
              <a
                href={cite?.source_uri || `#cite-${num}`}
                target={cite?.source_uri ? "_blank" : undefined}
                rel={cite?.source_uri ? "noopener noreferrer" : undefined}
                onClick={(e) => {
                  if (!cite?.source_uri) {
                    e.preventDefault();
                    document.getElementById(`cite-${num}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
                  }
                }}
                className={`cite-ref ${darkMode ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-500'}`}
              >
                <sup>{num}</sup>
              </a>
              <span className={`cite-tooltip ${darkMode ? 'bg-[#1E1E1E] text-gray-200 border-[#2A2A2A]' : 'bg-white text-gray-800 border-gray-200'}`}>
                {label}
              </span>
            </span>
          );
        });
      };
      return (
        <li {...props}>
          {Array.isArray(children) ? children.map((child, i) => <React.Fragment key={i}>{processNode(child)}</React.Fragment>) : processNode(children)}
        </li>
      );
    },
    td: ({ children, ...props }) => {
      const citations = response?.citations ?? [];
      const processNode = (node: React.ReactNode): React.ReactNode => {
        if (typeof node !== "string") return node;
        const parts = node.split(/(\[\d+\])/g);
        if (parts.length === 1) return node;
        return parts.map((part, i) => {
          const m = part.match(/^\[(\d+)\]$/);
          if (!m) return part;
          const num = parseInt(m[1], 10);
          const cite = citations[num - 1];
          const label = cite ? cite.protocol_id.replace(/_/g, " ") : `Source ${num}`;
          return (
            <span key={i} className="cite-ref-wrapper">
              <a
                href={cite?.source_uri || `#cite-${num}`}
                target={cite?.source_uri ? "_blank" : undefined}
                rel={cite?.source_uri ? "noopener noreferrer" : undefined}
                onClick={(e) => {
                  if (!cite?.source_uri) {
                    e.preventDefault();
                    document.getElementById(`cite-${num}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
                  }
                }}
                className={`cite-ref ${darkMode ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-500'}`}
              >
                <sup>{num}</sup>
              </a>
              <span className={`cite-tooltip ${darkMode ? 'bg-[#1E1E1E] text-gray-200 border-[#2A2A2A]' : 'bg-white text-gray-800 border-gray-200'}`}>
                {label}
              </span>
            </span>
          );
        });
      };
      return (
        <td {...props}>
          {Array.isArray(children) ? children.map((child, i) => <React.Fragment key={i}>{processNode(child)}</React.Fragment>) : processNode(children)}
        </td>
      );
    },
  };

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--background)' }}>
        <div className="flex gap-1">
          <div className="w-2 h-2 bg-[#013DED] rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
          <div className="w-2 h-2 bg-[#013DED] rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
          <div className="w-2 h-2 bg-[#013DED] rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
        </div>
      </div>
    );
  }

  return (
    <div className={`min-h-screen font-body flex relative overflow-hidden ${darkMode ? 'bg-[#0A0A0A] text-gray-100' : 'bg-[#F8F9FA] text-gray-900'}`}>
      {/* Sidebar Overlay - mobile only */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/20 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`app-sidebar fixed inset-y-0 left-0 z-50 w-72 border-r transform transition-all duration-300 ease-in-out ${
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      } flex flex-col ${darkMode ? 'bg-[#0B1535] border-[#131E4D]' : 'bg-white border-gray-200'}`}
        style={darkMode ? { boxShadow: 'inset -1px 0 0 rgba(37,99,235,0.08), 4px 0 24px rgba(0,0,0,0.5)' } : {}}
      >
        {/* Sidebar Header */}
        <div className={`p-4 border-b ${darkMode ? 'border-[#24305C]' : 'border-gray-200'}`}>
          <div className="flex items-center justify-between mb-4">
            <h2 className={`text-lg font-title font-semibold tracking-tight ${darkMode ? 'text-gray-100' : 'text-gray-800'}`}>Conversations</h2>
            <button 
              onClick={() => setSidebarOpen(false)}
              className={`p-1 rounded ${darkMode ? 'hover:bg-[#131E4D]' : 'hover:bg-gray-200'}`}
            >
              <X className={`w-5 h-5 ${darkMode ? 'text-gray-400' : 'text-gray-600'}`} />
            </button>
          </div>
          <button
            onClick={startNewConversation}
            className={`w-full flex items-center gap-2 px-4 py-3 rounded-[6px] transition-colors font-medium ${
              darkMode ? 'bg-[#013DED] text-white hover:bg-[#012FB8] ' : 'bg-[#013DED] text-white hover:bg-[#012FB8] shadow-md'
            }`}
          >
            <Plus className="w-5 h-5" />
            <span className="font-medium">New Conversation</span>
          </button>
        </div>

        {/* Scrollable content — conversations then settings/account (one region) */}
        <div className="flex-1 min-h-0 overflow-y-auto">
        {/* Conversation List */}
        <div className="px-2 py-2 space-y-1">
          {conversations.length === 0 ? (
            <div className={`text-center py-6 text-sm ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
              <MessageSquare className="w-7 h-7 mx-auto mb-2 opacity-50" />
              <p>No conversations yet</p>
            </div>
          ) : (
            (conversationsExpanded ? conversations : conversations.slice(0, 5)).map((conv) => (
              <div
                key={conv.id}
                onClick={() => loadConversation(conv)}
                className={`group w-full text-left px-3 py-1.5 rounded-[6px] transition-colors cursor-pointer ${
                  currentConversationId === conv.id
                    ? darkMode ? 'bg-[#131E4D] border border-[#24305C]' : 'bg-blue-50 border border-blue-200'
                    : darkMode ? 'hover:bg-[#131E4D] border border-transparent' : 'hover:bg-gray-50 border border-transparent'
                }`}
              >
                <div className="flex items-center gap-2">
                  <MessageSquare className={`w-3.5 h-3.5 flex-shrink-0 ${
                    currentConversationId === conv.id ? 'text-[#013DED]' : darkMode ? 'text-gray-500' : 'text-gray-400'
                  }`} />
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-medium truncate leading-tight ${
                      currentConversationId === conv.id
                        ? darkMode ? 'text-blue-300' : 'text-blue-900'
                        : darkMode ? 'text-gray-200' : 'text-gray-800'
                    }`}>
                      {conv.title}
                    </p>
                    <p className={`text-[11px] leading-tight ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                      {new Date(conv.timestamp).toLocaleDateString()} {new Date(conv.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </div>
                  <button
                    onClick={(e) => deleteConversation(conv.id, e)}
                    className={`opacity-0 group-hover:opacity-100 p-1 rounded transition-all ${darkMode ? 'hover:bg-[#24305C]' : 'hover:bg-red-100'}`}
                    title="Delete conversation"
                  >
                    <Trash2 className="w-3.5 h-3.5 text-red-500" />
                  </button>
                </div>
              </div>
            ))
          )}

          {/* Show more / less — keeps the list short so settings below stay visible */}
          {conversations.length > 5 && (
            <button
              onClick={() => setConversationsExpanded(!conversationsExpanded)}
              className={`w-full flex items-center justify-center gap-1 px-3 py-1.5 rounded-[6px] text-xs font-medium transition-colors ${
                darkMode ? 'text-gray-400 hover:bg-[#131E4D]' : 'text-gray-500 hover:bg-gray-50'
              }`}
            >
              {conversationsExpanded ? (
                <>Show less <ChevronUp className="w-3.5 h-3.5" /></>
              ) : (
                <>Show all {conversations.length} <ChevronDown className="w-3.5 h-3.5" /></>
              )}
            </button>
          )}
        </div>

        {/* Sidebar Footer — settings/sources/account */}
        <div className={`p-4 border-t ${darkMode ? 'border-[#24305C]' : 'border-gray-200'}`}>
          {/* Settings collapse toggle */}
          <button
            onClick={() => setSettingsCollapsed(!settingsCollapsed)}
            className={`w-full flex items-center justify-between px-1 mb-3 group`}
          >
            <span className={`text-xs font-semibold tracking-wider uppercase ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
              Settings
            </span>
            {settingsCollapsed ? (
              <ChevronRight className={`w-3.5 h-3.5 transition-colors ${darkMode ? 'text-gray-600 group-hover:text-gray-400' : 'text-gray-400 group-hover:text-gray-500'}`} />
            ) : (
              <ChevronDown className={`w-3.5 h-3.5 transition-colors ${darkMode ? 'text-gray-600 group-hover:text-gray-400' : 'text-gray-400 group-hover:text-gray-500'}`} />
            )}
          </button>

          {!settingsCollapsed && (
          <>
          {/* Dark/Light Mode Toggle */}
          <div className="flex items-center justify-between px-1 mb-4">
            <span className={`text-xs ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Light</span>
            <button
              onClick={() => setDarkMode(!darkMode)}
              className={`relative w-12 h-6 rounded-full transition-colors duration-300 ${
                darkMode ? 'bg-[#013DED]' : 'bg-gray-300'
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

          {/* EM Universe — Knowledge Sources */}
          <div className={`mb-4 rounded-[6px] border ${darkMode ? 'border-[#131E4D] bg-[#111111]' : 'border-gray-200 bg-gray-50/50'}`}>
            <div className={`px-3 py-2 flex items-center gap-2`}>
              <Globe className={`w-3.5 h-3.5 flex-shrink-0 ${darkMode ? 'text-blue-400' : 'text-gray-400'}`} />
              <span className={`text-xs font-semibold tracking-wider uppercase ${darkMode ? 'text-gray-300' : 'text-gray-500'}`}>
                EM Universe
              </span>
            </div>

            <div className={`px-2 pb-2 space-y-1`}>
              {/* WikEM Section */}
              <div>
                <button
                  onClick={() => setWikemExpanded(!wikemExpanded)}
                  className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-[6px] text-sm transition-colors ${
                    darkMode ? 'hover:bg-[#131E4D]' : 'hover:bg-gray-100'
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
                        : darkMode ? 'border-[#3A3A3A]' : 'border-gray-300'
                    }`}
                  >
                    {wikemEnabled && <Check className="w-3 h-3 text-white" />}
                  </div>
                  <img src="/logos/wikem.jpg" alt="WikEM" className={`w-4 h-4 rounded flex-shrink-0 ${wikemEnabled ? 'opacity-100' : 'opacity-40'}`} />
                  <span className={`flex-1 text-left font-medium ${wikemEnabled ? darkMode ? 'text-gray-200' : 'text-gray-700' : darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                    WikEM
                  </span>
                  <span className={`text-xs font-data ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>1,899</span>
                  {wikemExpanded ? (
                    <ChevronDown className={`w-3.5 h-3.5 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`} />
                  ) : (
                    <ChevronRight className={`w-3.5 h-3.5 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`} />
                  )}
                </button>
                {wikemExpanded && (
                  <div className={`ml-8 mt-1 px-2 py-2 rounded-[6px] text-xs leading-relaxed ${
                    darkMode ? 'text-gray-400 bg-[#131E4D]/50' : 'text-gray-500 bg-gray-100/50'
                  }`}>
                    Community-maintained EM knowledge base covering 1,899 clinical topics — diagnoses, procedures, and differentials.
                  </div>
                )}
              </div>

              {/* LITFL Section */}
              <div>
                <button
                  onClick={() => setLitflExpanded(!litflExpanded)}
                  className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-[6px] text-sm transition-colors ${
                    darkMode ? 'hover:bg-[#131E4D]' : 'hover:bg-gray-100'
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
                        : darkMode ? 'border-[#3A3A3A]' : 'border-gray-300'
                    }`}
                  >
                    {litflEnabled && <Check className="w-3 h-3 text-white" />}
                  </div>
                  <img src="/logos/litfl-logo.png" alt="LITFL" className={`w-4 h-4 rounded flex-shrink-0 ${litflEnabled ? 'opacity-100' : 'opacity-40'}`} />
                  <span className={`flex-1 text-left font-medium ${litflEnabled ? darkMode ? 'text-gray-200' : 'text-gray-700' : darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                    LITFL
                  </span>
                  <span className={`text-xs font-data ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>7,902</span>
                  {litflExpanded ? (
                    <ChevronDown className={`w-3.5 h-3.5 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`} />
                  ) : (
                    <ChevronRight className={`w-3.5 h-3.5 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`} />
                  )}
                </button>
                {litflExpanded && (
                  <div className={`ml-8 mt-1 px-2 py-2 rounded-[6px] text-xs leading-relaxed ${
                    darkMode ? 'text-gray-400 bg-[#131E4D]/50' : 'text-gray-500 bg-gray-100/50'
                  }`}>
                    Life in the Fast Lane — 7,902 FOAMed articles covering ECG interpretation, critical care, toxicology, pharmacology, clinical cases, and eponymous medical terms. CC BY-NC-SA 4.0.
                  </div>
                )}
              </div>

              {/* REBEL EM Section */}
              <div>
                <button
                  onClick={() => setRebelemExpanded(!rebelemExpanded)}
                  className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-[6px] text-sm transition-colors ${
                    darkMode ? 'hover:bg-[#131E4D]' : 'hover:bg-gray-100'
                  }`}
                >
                  <div
                    onClick={(e) => {
                      e.stopPropagation();
                      setRebelemEnabled(!rebelemEnabled);
                      setUniverseDirty(true);
                    }}
                    className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 cursor-pointer ${
                      rebelemEnabled
                        ? 'bg-rose-500 border-rose-500'
                        : darkMode ? 'border-[#3A3A3A]' : 'border-gray-300'
                    }`}
                  >
                    {rebelemEnabled && <Check className="w-3 h-3 text-white" />}
                  </div>
                  <img src="/logos/rebelem-logo.png" alt="REBEL EM" className={`w-4 h-4 rounded flex-shrink-0 ${rebelemEnabled ? 'opacity-100' : 'opacity-40'}`} />
                  <span className={`flex-1 text-left font-medium ${rebelemEnabled ? darkMode ? 'text-gray-200' : 'text-gray-700' : darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                    REBEL EM
                  </span>
                  <span className={`text-xs font-data ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>1,245</span>
                  {rebelemExpanded ? (
                    <ChevronDown className={`w-3.5 h-3.5 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`} />
                  ) : (
                    <ChevronRight className={`w-3.5 h-3.5 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`} />
                  )}
                </button>
                {rebelemExpanded && (
                  <div className={`ml-8 mt-1 px-2 py-2 rounded-[6px] text-xs leading-relaxed ${
                    darkMode ? 'text-gray-400 bg-[#131E4D]/50' : 'text-gray-500 bg-gray-100/50'
                  }`}>
                    REBEL EM — 1,245 evidence-based reviews of recent emergency medicine literature with clinical bottom lines and critical appraisals. CC BY-NC-ND 4.0.
                  </div>
                )}
              </div>

              {/* ALiEM Section */}
              <div>
                <button
                  onClick={() => setAliemExpanded(!aliemExpanded)}
                  className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-[6px] text-sm transition-colors ${
                    darkMode ? 'hover:bg-[#131E4D]' : 'hover:bg-gray-100'
                  }`}
                >
                  <div
                    onClick={(e) => {
                      e.stopPropagation();
                      setAliemEnabled(!aliemEnabled);
                      setUniverseDirty(true);
                    }}
                    className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 cursor-pointer ${
                      aliemEnabled
                        ? 'bg-cyan-500 border-cyan-500'
                        : darkMode ? 'border-[#3A3A3A]' : 'border-gray-300'
                    }`}
                  >
                    {aliemEnabled && <Check className="w-3 h-3 text-white" />}
                  </div>
                  <img src="/logos/aliem-logo.png" alt="ALiEM" className={`w-4 h-4 rounded flex-shrink-0 ${aliemEnabled ? 'opacity-100' : 'opacity-40'}`} />
                  <span className={`flex-1 text-left font-medium ${aliemEnabled ? darkMode ? 'text-gray-200' : 'text-gray-700' : darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                    ALiEM
                  </span>
                  <span className={`text-xs font-data ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>258</span>
                  {aliemExpanded ? (
                    <ChevronDown className={`w-3.5 h-3.5 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`} />
                  ) : (
                    <ChevronRight className={`w-3.5 h-3.5 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`} />
                  )}
                </button>
                {aliemExpanded && (
                  <div className={`ml-8 mt-1 px-2 py-2 rounded-[6px] text-xs leading-relaxed ${
                    darkMode ? 'text-gray-400 bg-[#131E4D]/50' : 'text-gray-500 bg-gray-100/50'
                  }`}>
                    ALiEM — 258 PV Cards and MEdIC cases covering emergency medicine education, clinical decision-making, and academic development. CC BY-NC-ND 3.0.
                  </div>
                )}
              </div>

              {/* PMC Literature Section */}
              <div>
                <button
                  onClick={() => setPmcExpanded(!pmcExpanded)}
                  className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-[6px] text-sm transition-colors ${
                    darkMode ? 'hover:bg-[#131E4D]' : 'hover:bg-gray-100'
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
                        : darkMode ? 'border-[#3A3A3A]' : 'border-gray-300'
                    }`}
                  >
                    {pmcEnabled && <Check className="w-3 h-3 text-white" />}
                  </div>
                  <img src="/logos/pmc_logo.png" alt="PMC" className={`w-4 h-4 rounded flex-shrink-0 ${pmcEnabled ? 'opacity-100' : 'opacity-40'}`} />
                  <span className={`flex-1 text-left font-medium ${pmcEnabled ? darkMode ? 'text-gray-200' : 'text-gray-700' : darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                    PMC Literature
                  </span>
                  <span className={`text-xs font-data ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
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
                    {/* Grouped journal list */}
                    <div className="space-y-1 max-h-64 overflow-y-auto">
                      {PMC_JOURNAL_GROUPS.map((group) => {
                        const groupKeys = getGroupKeys(group);
                        const selectedInGroup = groupKeys.filter(k => selectedJournals.has(k)).length;
                        const allInGroupSelected = selectedInGroup === groupKeys.length;
                        const someInGroupSelected = selectedInGroup > 0 && !allInGroupSelected;
                        const isExpanded = expandedGroups.has(group.group);
                        const groupCount = group.journals.reduce((s, j) => s + j.count, 0);
                        return (
                          <div key={group.group}>
                            {/* Group header row */}
                            <button
                              onClick={() => toggleGroupExpanded(group.group)}
                              className={`w-full flex items-center gap-2 px-2 py-1 rounded-md text-xs font-medium transition-colors ${
                                darkMode ? 'hover:bg-[#131E4D]' : 'hover:bg-gray-100'
                              }`}
                            >
                              <div
                                onClick={(e) => { e.stopPropagation(); toggleGroup(group); }}
                                className={`w-3.5 h-3.5 rounded border flex items-center justify-center flex-shrink-0 cursor-pointer ${
                                  allInGroupSelected
                                    ? 'bg-purple-500 border-purple-500'
                                    : someInGroupSelected
                                      ? 'bg-purple-500/40 border-purple-500'
                                      : darkMode ? 'border-[#3A3A3A]' : 'border-gray-300'
                                }`}
                              >
                                {allInGroupSelected && <Check className="w-2.5 h-2.5 text-white" />}
                                {someInGroupSelected && <div className="w-1.5 h-0.5 bg-white rounded-full" />}
                              </div>
                              <span className={`flex-1 text-left ${
                                selectedInGroup > 0
                                  ? darkMode ? 'text-gray-200' : 'text-gray-700'
                                  : darkMode ? 'text-gray-500' : 'text-gray-400'
                              }`}>
                                {group.group}
                              </span>
                              <span className={`text-xs font-data tabular-nums ${darkMode ? 'text-gray-600' : 'text-gray-400'}`}>
                                {selectedInGroup === groupKeys.length
                                  ? groupCount.toLocaleString()
                                  : `${selectedInGroup}/${groupKeys.length}`
                                }
                              </span>
                              {isExpanded ? (
                                <ChevronDown className={`w-3 h-3 ${darkMode ? 'text-gray-600' : 'text-gray-400'}`} />
                              ) : (
                                <ChevronRight className={`w-3 h-3 ${darkMode ? 'text-gray-600' : 'text-gray-400'}`} />
                              )}
                            </button>
                            {/* Individual journals within group */}
                            {isExpanded && (
                              <div className="ml-4 space-y-0">
                                {group.journals.map((j) => {
                                  const isChecked = selectedJournals.has(j.key);
                                  return (
                                    <button
                                      key={j.key}
                                      onClick={() => toggleJournal(j.key)}
                                      className={`w-full flex items-center gap-2 px-2 py-0.5 rounded-md text-xs transition-colors ${
                                        darkMode ? 'hover:bg-[#131E4D]' : 'hover:bg-gray-100'
                                      }`}
                                    >
                                      <div className={`w-3 h-3 rounded border flex items-center justify-center flex-shrink-0 ${
                                        isChecked
                                          ? 'bg-purple-500 border-purple-500'
                                          : darkMode ? 'border-[#3A3A3A]' : 'border-gray-300'
                                      }`}>
                                        {isChecked && <Check className="w-2 h-2 text-white" />}
                                      </div>
                                      <span className={`flex-1 text-left ${
                                        isChecked
                                          ? darkMode ? 'text-gray-300' : 'text-gray-700'
                                          : darkMode ? 'text-gray-500' : 'text-gray-400'
                                      }`}>
                                        {j.label}
                                      </span>
                                      <span className={`text-xs font-data tabular-nums ${darkMode ? 'text-gray-600' : 'text-gray-400'}`}>
                                        {j.count.toLocaleString()}
                                      </span>
                                    </button>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            </div>

          </div>

          {/* My Files — Personal RAG toggle */}
          {isSignedIn && (
            <div className={`mb-4 rounded-[6px] border ${darkMode ? 'border-[#131E4D] bg-[#111111]' : 'border-gray-200 bg-gray-50/50'}`}>
              <div className="p-3">
                <div className="flex items-center gap-2 px-1 mb-2">
                  <FolderOpen className={`w-4 h-4 flex-shrink-0 ${darkMode ? 'text-violet-400' : 'text-violet-600'}`} />
                  <span className={`text-xs font-semibold tracking-wider uppercase ${darkMode ? 'text-gray-300' : 'text-gray-500'}`}>
                    My Files
                  </span>
                </div>

                <button
                  onClick={() => setPersonalEnabled(!personalEnabled)}
                  className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-[6px] text-sm transition-colors ${
                    darkMode ? 'hover:bg-[#131E4D]' : 'hover:bg-gray-100'
                  }`}
                >
                  <div
                    className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 cursor-pointer ${
                      personalEnabled
                        ? 'bg-violet-500 border-violet-500'
                        : darkMode ? 'border-[#3A3A3A]' : 'border-gray-300'
                    }`}
                  >
                    {personalEnabled && <Check className="w-3 h-3 text-white" />}
                  </div>
                  <span className={`flex-1 text-left font-medium ${personalEnabled ? darkMode ? 'text-gray-200' : 'text-gray-700' : darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                    Include in search
                  </span>
                </button>

                <a
                  href="/personal"
                  className={`mt-2 w-full flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-[6px] text-xs font-medium transition-colors ${
                    darkMode
                      ? 'bg-violet-600/20 text-violet-400 hover:bg-violet-600/30 border border-violet-600/30'
                      : 'bg-violet-50 text-violet-600 hover:bg-violet-100 border border-violet-200'
                  }`}
                >
                  <Upload className="w-3.5 h-3.5" />
                  Manage Files
                </a>
              </div>
            </div>
          )}

          {/* Mayo Protocols — Request Access (sidebar) */}
          {isSignedIn && !hasAccess && (
            <div className={`mb-4 rounded-[6px] border ${darkMode ? 'border-[#24305C] bg-[#0E173D]/50' : 'border-gray-200 bg-gray-50/50'}`}>
              <div className="p-3">
                <div className="flex items-center gap-2 px-1 mb-2">
                  <Building2 className={`w-4 h-4 flex-shrink-0 ${darkMode ? 'text-blue-400' : 'text-blue-600'}`} />
                  <span className={`text-xs font-medium tracking-wide ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                    Mayo Clinic Protocols
                  </span>
                </div>

                {userProfile?.accessStatus === "pending" ? (
                  <div className="px-1">
                    <div className="flex items-center gap-2 mb-1">
                      <div className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
                      <p className={`text-xs font-medium ${darkMode ? 'text-yellow-400' : 'text-yellow-600'}`}>
                        Pending
                      </p>
                    </div>
                    <p className={`text-xs ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                      Please allow 3-5 business days.
                    </p>
                  </div>
                ) : userProfile?.accessStatus === "denied" ? (
                  <div className="px-1">
                    <p className={`text-xs ${darkMode ? 'text-red-400' : 'text-red-600'}`}>
                      Access denied. Contact an administrator.
                    </p>
                  </div>
                ) : !showRequestForm ? (
                  <div className="px-1">
                    <p className={`text-xs mb-2 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                      Department-specific protocol bundles
                    </p>
                    <button
                      onClick={() => setShowRequestForm(true)}
                      className={`w-full flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-[6px] text-xs font-medium transition-colors ${
                        darkMode
                          ? 'bg-[#013DED]/20 text-blue-400 hover:bg-[#013DED]/30 border border-blue-600/30'
                          : 'bg-blue-50 text-blue-600 hover:bg-blue-100 border border-blue-200'
                      }`}
                    >
                      Request Access
                    </button>
                  </div>
                ) : (
                  <form
                    onSubmit={async (e) => {
                      e.preventDefault();
                      setRequestError(null);
                      if (!requestEmail.toLowerCase().trim().endsWith("@mayo.edu")) {
                        setRequestError("Must be a @mayo.edu email");
                        return;
                      }
                      if (!requestName.trim()) {
                        setRequestError("Please enter your name");
                        return;
                      }
                      setRequestLoading(true);
                      try {
                        const result = await submitAccessRequest(requestName.trim(), requestEmail.trim());
                        setRequestSuccess(result.message || "Submitted! Please allow 3-5 business days.");
                        setShowRequestForm(false);
                        setRequestName("");
                        setRequestEmail("");
                        await refreshProfile();
                      } catch (err) {
                        setRequestError(err instanceof Error ? err.message : "Failed to submit");
                      } finally {
                        setRequestLoading(false);
                      }
                    }}
                    className="px-1 space-y-2"
                  >
                    {requestError && (
                      <p className="text-xs text-red-400">{requestError}</p>
                    )}
                    <input
                      type="text"
                      value={requestName}
                      onChange={(e) => setRequestName(e.target.value)}
                      placeholder="Full Name"
                      required
                      className={`w-full px-2.5 py-1.5 rounded-[6px] text-xs ${
                        darkMode
                          ? 'bg-[#131E4D] border border-[#3A3A3A] text-white placeholder-[#6B7280]'
                          : 'bg-white border border-gray-300 text-gray-800 placeholder-gray-400'
                      } focus:outline-none focus:border-blue-500`}
                    />
                    <input
                      type="email"
                      value={requestEmail}
                      onChange={(e) => setRequestEmail(e.target.value)}
                      placeholder="your.name@mayo.edu"
                      required
                      className={`w-full px-2.5 py-1.5 rounded-[6px] text-xs ${
                        darkMode
                          ? 'bg-[#131E4D] border border-[#3A3A3A] text-white placeholder-[#6B7280]'
                          : 'bg-white border border-gray-300 text-gray-800 placeholder-gray-400'
                      } focus:outline-none focus:border-blue-500`}
                    />
                    <div className="flex gap-2">
                      <button
                        type="submit"
                        disabled={requestLoading}
                        className="flex-1 px-3 py-1.5 bg-[#013DED] hover:bg-blue-700 disabled:bg-[#013DED]/50 text-white text-xs font-medium rounded-[6px] transition-colors"
                      >
                        {requestLoading ? "Submitting..." : "Submit"}
                      </button>
                      <button
                        type="button"
                        onClick={() => { setShowRequestForm(false); setRequestError(null); }}
                        className={`px-3 py-1.5 text-xs rounded-[6px] transition-colors ${
                          darkMode ? 'text-[#9CA3AF] hover:text-white' : 'text-gray-500 hover:text-gray-700'
                        }`}
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                )}

                {requestSuccess && (
                  <p className={`text-xs mt-2 px-1 ${darkMode ? 'text-green-400' : 'text-green-600'}`}>
                    {requestSuccess}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Enterprise + ED Selector */}
          {isSignedIn && hasAccess && enterprise && (
            <div className={`mb-4 rounded-[6px] border ${darkMode ? 'border-[#131E4D] bg-[#111111]' : 'border-gray-200 bg-gray-50/50'}`}>
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
                      className={`w-full px-3 py-2 rounded-[6px] text-sm font-semibold appearance-none cursor-pointer pr-8 ${
                        darkMode
                          ? 'bg-[#131E4D] text-gray-200 border border-[#24305C] focus:border-blue-500'
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
                  <span className={`text-sm font-title font-semibold ${darkMode ? 'text-gray-200' : 'text-gray-700'}`}>
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
                                ? 'text-gray-400 hover:bg-[#131E4D]'
                                : 'text-gray-500 hover:bg-gray-100'
                          }`}
                        >
                          <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center flex-shrink-0 ${
                            isSelected 
                              ? 'bg-blue-500 border-blue-500' 
                              : darkMode ? 'border-[#3A3A3A]' : 'border-gray-300'
                          }`}>
                            {isSelected && <Check className="w-2.5 h-2.5 text-white" />}
                          </div>
                          <span className="flex-1 text-left text-xs font-medium">{edLabel(ed)}</span>
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

          {/* Save Preferences — covers EM Universe + ED selections */}
          {universeDirty && (
            <div className="mb-4">
              <button
                onClick={saveUniversePreferences}
                className={`w-full flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-[6px] text-xs font-medium transition-colors ${
                  darkMode
                    ? 'bg-[#013DED]/20 text-blue-400 hover:bg-[#013DED]/30 border border-blue-600/30'
                    : 'bg-blue-50 text-blue-600 hover:bg-blue-100 border border-blue-200'
                }`}
              >
                <Save className="w-3 h-3" />
                Save Preferences
              </button>
            </div>
          )}
          </>
          )}

          {/* User Auth - at bottom */}
          {isSignedIn ? (
            <div className="relative">
              <button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-[6px] transition-colors ${darkMode ? 'hover:bg-[#131E4D]' : 'hover:bg-gray-100'}`}
              >
                {user?.photoURL ? (
                  <img 
                    src={user.photoURL} 
                    alt="Profile" 
                    className="w-10 h-10 rounded-full flex-shrink-0"
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-sm font-medium flex-shrink-0">
                    {(user?.email || userProfile?.email || "?").charAt(0).toUpperCase()}
                  </div>
                )}
                <div className="flex-1 min-w-0 text-left">
                  <p className={`text-sm font-medium truncate ${darkMode ? 'text-gray-100' : 'text-gray-900'}`}>
                    {userProfile?.enterpriseName || (user?.email || userProfile?.email || "").split("@")[0]}
                  </p>
                  <p className={`text-xs truncate ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>{user?.email || userProfile?.email}</p>
                </div>
                <ChevronDown className={`w-4 h-4 transition-transform flex-shrink-0 ${darkMode ? 'text-gray-500' : 'text-gray-400'} ${showUserMenu ? 'rotate-180' : ''}`} />
              </button>
              
              {showUserMenu && (
                <>
                  <div 
                    className="fixed inset-0 z-10" 
                    onClick={() => setShowUserMenu(false)}
                  />
                  <div className={`absolute bottom-full left-0 right-0 mb-2 border rounded-[6px] shadow-lg z-20 ${darkMode ? 'bg-[#0E173D] border-[#24305C]' : 'bg-white border-gray-200'}`}>
                    <div className={`px-4 py-3 border-b ${darkMode ? 'border-[#24305C]' : 'border-gray-100'}`}>
                      <p className={`text-sm font-medium truncate ${darkMode ? 'text-gray-100' : 'text-gray-900'}`}>{user?.email || userProfile?.email}</p>
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
                            className={`w-full flex items-center gap-2 px-4 py-3 text-sm transition-colors ${darkMode ? 'text-gray-300 hover:bg-[#131E4D]' : 'text-gray-600 hover:bg-gray-50'} border-b ${darkMode ? 'border-[#24305C]' : 'border-gray-100'}`}
                          >
                            <Crown className="w-4 h-4" />
                            Owner Dashboard
                          </button>
                        )}
                        <button
                          onClick={() => router.push("/admin")}
                          className={`w-full flex items-center gap-2 px-4 py-3 text-sm transition-colors ${darkMode ? 'text-gray-300 hover:bg-[#131E4D]' : 'text-gray-600 hover:bg-gray-50'} border-b ${darkMode ? 'border-[#24305C]' : 'border-gray-100'}`}
                        >
                          <Shield className="w-4 h-4" />
                          Upload Protocols
                        </button>
                      </>
                    )}
                    <button
                      onClick={handleSignOut}
                      className={`w-full flex items-center gap-2 px-4 py-3 text-sm transition-colors rounded-b-lg ${darkMode ? 'text-gray-300 hover:bg-[#131E4D]' : 'text-gray-600 hover:bg-gray-50'}`}
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
              className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-[6px] border transition-colors ${darkMode ? 'border-[#24305C] hover:bg-[#131E4D]' : 'border-gray-200 hover:bg-gray-100'}`}
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
        </div>
      </aside>

      {/* Main Content */}
      <main className={`app-main flex-1 min-w-0 flex flex-col min-h-screen transition-all duration-300 ${sidebarOpen ? 'ml-72' : 'ml-0'}`}>
        {/* Header */}
        <div className="app-header sticky top-0 z-30 w-full px-4 pt-4 pb-3 bg-transparent">
          <div className="flex items-center gap-3">
            {/* Hamburger — opens the left drawer (conversations, settings, files) */}
            <button
              onClick={() => setSidebarOpen(true)}
              title="Menu"
              aria-label="Open menu"
              className={`flex-shrink-0 p-2 rounded-lg transition-colors ${darkMode ? 'hover:bg-[#131E4D]' : 'hover:bg-gray-100'}`}
            >
              <div className="flex flex-col gap-1.5">
                <span className={`block w-5 h-0.5 rounded-full ${darkMode ? 'bg-gray-300' : 'bg-[#0E173D]'}`} />
                <span className={`block w-5 h-0.5 rounded-full ${darkMode ? 'bg-gray-300' : 'bg-[#0E173D]'}`} />
                <span className={`block w-5 h-0.5 rounded-full ${darkMode ? 'bg-gray-300' : 'bg-[#0E173D]'}`} />
              </div>
            </button>

            {/* EMA logo — returns to the main screen */}
            <button
              onClick={resetSearch}
              title="Home"
              aria-label="Home — EMA"
              className="flex-shrink-0 p-1 rounded-lg transition-transform duration-200 hover:scale-105"
            >
              <img
                src={darkMode ? "/ema-logo-dark.svg" : "/ema-logo.svg"}
                alt="EMA — home"
                className={`w-auto transition-all duration-300 ${hasSearched ? "h-7" : "h-9"}`}
              />
            </button>

            <div className="flex-1" />
          </div>
        </div>

      {/* Main Content */}
      <div className={`w-full px-4 py-8 ${hasSearched ? '' : 'max-w-5xl mx-auto'}`}>
        {!hasSearched ? (
          /* Initial Search View */
          <div className="flex flex-col items-center justify-center min-h-[60vh]">
            <div className="w-full max-w-3xl px-4 flex flex-col items-center">
              {/* Query box — EMA MainDash minimalist prompt (centered as a unit) */}
              <div className="relative mt-2 w-fit max-w-full">
                <div className="flex items-baseline gap-1.5">
                  {/* Blue caret — the "|" glyph in brand blue, blinking, inline with the text */}
                  <span
                    aria-hidden="true"
                    className={`font-title font-medium text-4xl md:text-5xl select-none flex-shrink-0 ${!question ? 'animate-caret' : ''}`}
                    style={{ letterSpacing: 0, lineHeight: 1.19, color: '#013DED', transform: 'translateY(-0.09em)' }}
                  >
                    |
                  </span>
                  <textarea
                    placeholder={typedPlaceholder}
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onFocus={() => setSearchFocused(true)}
                    onBlur={() => setSearchFocused(false)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSubmit();
                      }
                    }}
                    rows={1}
                    style={{ letterSpacing: 0, lineHeight: 1.19, caretColor: 'transparent', fieldSizing: 'content', whiteSpace: 'nowrap' } as React.CSSProperties}
                    className={`p-0 min-w-[18rem] md:min-w-[30rem] max-w-full font-title font-medium bg-transparent resize-none overflow-hidden focus:outline-none text-4xl md:text-5xl placeholder:opacity-100 focus:placeholder:text-transparent ${
                      darkMode
                        ? 'text-white placeholder:text-white'
                        : 'text-[#0E173D] placeholder:text-[#0E173D]'
                    }`}
                  />
                </div>

                {/* Data sources — filled if active, outline if inactive */}
                <div className="mt-4 flex items-center gap-2 flex-wrap">
                  {/* EM Universe (WikEM, PMC, LITFL, REBEL EM, ALiEM) */}
                  <button
                    onClick={() => toggleSource("wikem")}
                    title="EM Universe — WikEM, PMC, LITFL, REBEL EM, ALiEM"
                    className={sourceChipClass(globeActive)}
                  >
                    EM Universe
                  </button>

                  {/* Enterprise EDs — e.g. Mayo Protocols, MCHS, RST */}
                  {enterprise?.eds.map((ed) => {
                    const active = selectedEds.has(ed.id);
                    return (
                      <button
                        key={ed.id}
                        onClick={() => toggleEdSelection(ed.id)}
                        title={ed.location ? `${edLabel(ed)} — ${ed.location}` : edLabel(ed)}
                        className={sourceChipClass(active)}
                      >
                        {edLabel(ed)}
                      </button>
                    );
                  })}

                  {/* My uploaded files */}
                  {(user || userProfile) && (
                    <button
                      onClick={() => setPersonalEnabled(!personalEnabled)}
                      title="Search your uploaded files"
                      className={sourceChipClass(personalEnabled)}
                    >
                      My Files
                    </button>
                  )}

                  <MicButton
                    isSupported={micSupported}
                    listening={micListening}
                    permissionDenied={micPermissionDenied}
                    onToggle={() => toggleMic(question, setQuestion)}
                    darkMode={darkMode}
                    size="sm"
                  />

                  <button
                    onClick={handleSubmit}
                    disabled={!question.trim() || loading || isStreaming}
                    title="Submit (or press Enter)"
                    className="inline-flex items-center justify-center w-7 h-7 rounded-[4px] text-white bg-[#013DED] hover:bg-[#012FB8] transition-all duration-200 disabled:opacity-40"
                  >
                    {loading || isStreaming ? (
                      <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <ArrowUp className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>
              </div>

              {/* Pinned Protocols — combined highlighted + favorites */}
              {(highlightedProtocols.length > 0 || favoriteProtocols.length > 0) && (
                <div className="mt-10 w-full max-w-2xl mx-auto flex flex-col gap-2">

                  {/* Highlighted section */}
                  {highlightedProtocols.length > 0 && (
                    <div className={`rounded-xl overflow-hidden ${
                      darkMode
                        ? 'bg-[#141414] border border-red-900/30'
                        : 'bg-white border border-red-200'
                    }`}>
                      <button
                        onClick={() => setHighlightedOpen(!highlightedOpen)}
                        className={`w-full flex items-center justify-between px-4 py-2 cursor-pointer transition-colors ${
                          darkMode ? 'bg-red-950/20 hover:bg-red-950/30' : 'bg-red-50/50 hover:bg-red-50'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <Bookmark className={`w-3.5 h-3.5 ${darkMode ? 'text-red-400' : 'text-red-500'} fill-current`} />
                          <span className={`text-xs font-semibold ${darkMode ? 'text-red-300' : 'text-red-700'}`}>
                            Highlighted by Your Practice
                          </span>
                          <span className={`text-xs ${darkMode ? 'text-red-400/50' : 'text-red-400/70'}`}>
                            {highlightedProtocols.length}
                          </span>
                        </div>
                        <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-200 ${
                          darkMode ? 'text-red-400/60' : 'text-red-400/60'
                        } ${highlightedOpen ? 'rotate-180' : ''}`} />
                      </button>
                      {highlightedOpen && (
                        <div className={`${darkMode ? 'border-t border-red-900/30' : 'border-t border-red-100'}`}>
                          {highlightedProtocols.map((card, idx) => {
                            const name = card.protocol_id
                              .replace(/_/g, " ")
                              .replace(/\.pdf$/i, "")
                              .replace(/\b\w/g, (c) => c.toUpperCase());
                            return (
                              <a
                                key={`hl-${card.protocol_id}`}
                                href={card.pdf_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className={`w-full flex items-center justify-between px-4 py-2 text-left transition-colors duration-150 ${
                                  idx < highlightedProtocols.length - 1
                                    ? darkMode ? 'border-b border-[#2A2A2A]/50' : 'border-b border-gray-100'
                                    : ''
                                } ${
                                  darkMode
                                    ? 'hover:bg-red-950/30 text-gray-300'
                                    : 'hover:bg-red-50/50 text-gray-600'
                                }`}
                              >
                                <span className="text-sm">{name}</span>
                                <ChevronRight className={`w-3.5 h-3.5 flex-shrink-0 ${
                                  darkMode ? 'text-red-400/70' : 'text-red-400/70'
                                }`} />
                              </a>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Favorites section */}
                  {favoriteProtocols.length > 0 && (
                    <div className={`rounded-xl overflow-hidden ${
                      darkMode
                        ? 'bg-[#141414] border border-[#2A2A2A]'
                        : 'bg-white border border-gray-200'
                    }`}>
                      <button
                        onClick={() => setFavoritesOpen(!favoritesOpen)}
                        className={`w-full flex items-center justify-between px-4 py-2 cursor-pointer transition-colors ${
                          darkMode ? 'hover:bg-[#1E1E1E]/50' : 'hover:bg-gray-50'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <Star className={`w-3.5 h-3.5 ${darkMode ? 'text-yellow-400' : 'text-yellow-500'} fill-current`} />
                          <span className={`text-xs font-semibold ${darkMode ? 'text-gray-200' : 'text-gray-700'}`}>
                            Favorited Protocols
                          </span>
                          <span className={`text-xs ${darkMode ? 'text-[#6B7280]' : 'text-gray-400'}`}>
                            {favoriteProtocols.length}
                          </span>
                        </div>
                        <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-200 ${
                          darkMode ? 'text-[#6B7280]' : 'text-gray-400'
                        } ${favoritesOpen ? 'rotate-180' : ''}`} />
                      </button>
                      {favoritesOpen && (
                        <div className={`${darkMode ? 'border-t border-[#2A2A2A]' : 'border-t border-gray-200'}`}>
                          {favoriteProtocols.map((card, idx) => {
                            const name = card.protocol_id
                              .replace(/_/g, " ")
                              .replace(/\.pdf$/i, "")
                              .replace(/\b\w/g, (c) => c.toUpperCase());
                            return (
                              <a
                                key={`fav-${card.protocol_id}`}
                                href={card.pdf_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className={`w-full flex items-center justify-between px-4 py-2 text-left transition-colors duration-150 ${
                                  idx < favoriteProtocols.length - 1
                                    ? darkMode ? 'border-b border-[#2A2A2A]/50' : 'border-b border-gray-100'
                                    : ''
                                } ${
                                  darkMode
                                    ? 'hover:bg-[#1E1E1E]/60 text-gray-300'
                                    : 'hover:bg-gray-50 text-gray-600'
                                }`}
                              >
                                <span className="text-sm">{name}</span>
                                <ChevronRight className={`w-3.5 h-3.5 flex-shrink-0 ${
                                  darkMode ? 'text-[#6B7280]' : 'text-gray-400'
                                }`} />
                              </a>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}

                </div>
              )}

            </div>
          </div>
        ) : (
          /* Results View — conversation columns; New conversation opens a column to the right */
          <div ref={columnsRowRef} className="flex items-start gap-6 overflow-x-auto pb-8 scroll-smooth">
            {/* leading spacer so the first/active column can center in the window */}
            <div className="flex-shrink-0 w-[calc(50vw-350px)] max-[820px]:hidden" aria-hidden="true" />
            {openPanels.map((pid) => {
              const pconv = conversations.find((c) => c.id === pid);
              const isActive = pid === currentConversationId;

              // Inactive column — full, readable transcript (read-only). Stays
              // open so you can swipe between conversations; click anywhere to
              // make it active and reply.
              if (!isActive) {
                if (!pconv) return null;
                return (
                  <div
                    key={pid}
                    onClick={() => loadConversation(pconv)}
                    title="Click to make active and reply"
                    className={`flex-shrink-0 w-[86vw] max-w-[560px] max-h-[82vh] overflow-y-auto rounded-[6px] border-2 p-5 space-y-4 cursor-pointer transition-colors ${darkMode ? 'border-[#24305C] bg-[#0B1535] hover:border-[#33407A]' : 'border-gray-300 bg-white hover:border-[#013DED]'}`}
                  >
                    {(pconv.turns || []).map((t, ti) => (
                      <div key={`snap-turn-${ti}`} className={`rounded-[6px] overflow-hidden border ${darkMode ? 'border-[#24305C]' : 'border-[#013DED]/40'}`}>
                        <div className="px-5 py-3" style={{ backgroundColor: '#013DED' }}>
                          <p className="text-white font-medium">{t.question}</p>
                        </div>
                        <div className={`p-6 ${darkMode ? 'bg-[#0E173D]' : 'bg-white'}`}>
                          <div className={`prose prose-sm max-w-none leading-relaxed font-data ${darkMode ? 'prose-invert text-gray-200' : 'text-gray-800'}`}>
                            <ReactMarkdown remarkPlugins={[remarkGfm]} components={citationComponents}>{t.answer}</ReactMarkdown>
                          </div>
                        </div>
                      </div>
                    ))}
                    <div className="rounded-[6px] px-5 py-3" style={{ backgroundColor: '#013DED' }}>
                      <p className="text-white font-medium">{pconv.question}</p>
                    </div>
                    {pconv.response?.answer && (
                      <div className={`rounded-[6px] p-6 border ${darkMode ? 'border-[#24305C] bg-[#0E173D]' : 'border-[#013DED]/40 bg-white'}`}>
                        <div className={`prose prose-sm max-w-none leading-relaxed font-data ${darkMode ? 'prose-invert text-gray-200' : 'text-gray-800'}`}>
                          <ReactMarkdown remarkPlugins={[remarkGfm]} components={citationComponents}>{pconv.response.answer}</ReactMarkdown>
                        </div>
                      </div>
                    )}
                    <p className="text-[11px] font-data uppercase tracking-wide text-[#013DED]">Click to reply →</p>
                  </div>
                );
              }

              // Active (live) column — renders in its own position (resume in place),
              // tall with internal scroll so multiple answers are readable at once.
              return (
                <div key={pid} data-active-column="true" className={`flex-shrink-0 w-full max-w-[680px] max-h-[82vh] overflow-y-auto rounded-[6px] border-2 p-5 space-y-5 ${darkMode ? 'border-[#24305C] bg-[#0B1535]' : 'border-[#013DED] bg-white'}`}>
            {activeIsEmpty ? (
              <div className="py-6">
                <div className="flex items-baseline gap-1.5">
                  <span
                    aria-hidden="true"
                    className={`font-title font-medium text-3xl md:text-4xl select-none flex-shrink-0 ${!question ? 'animate-caret' : ''}`}
                    style={{ letterSpacing: 0, lineHeight: 1.19, color: '#013DED', transform: 'translateY(-0.09em)' }}
                  >
                    |
                  </span>
                  <textarea
                    placeholder="What's the emergency?"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSubmit(); } }}
                    rows={1}
                    style={{ letterSpacing: 0, lineHeight: 1.19, caretColor: 'transparent' }}
                    className={`flex-1 p-0 font-title font-medium bg-transparent resize-none focus:outline-none text-3xl md:text-4xl placeholder:opacity-100 focus:placeholder:text-transparent ${darkMode ? 'text-white placeholder:text-white' : 'text-[#0E173D] placeholder:text-[#0E173D]'}`}
                  />
                  <MicButton
                    isSupported={micSupported}
                    listening={micListening}
                    permissionDenied={micPermissionDenied}
                    onToggle={() => toggleMic(question, setQuestion)}
                    darkMode={darkMode}
                    size="md"
                  />
                  <button
                    onClick={handleSubmit}
                    disabled={!question.trim() || loading || isStreaming}
                    title="Submit (or press Enter)"
                    className="self-center inline-flex items-center justify-center w-8 h-8 flex-shrink-0 rounded-[4px] text-white bg-[#013DED] hover:bg-[#012FB8] disabled:opacity-40"
                  >
                    <ArrowUp className="w-4 h-4" />
                  </button>
                </div>
                <div className="mt-4 flex items-center gap-2 flex-wrap">
                  <button onClick={() => toggleSource("wikem")} title="EM Universe — WikEM, PMC, LITFL, REBEL EM, ALiEM" className={sourceChipClass(globeActive)}>
                    EM Universe
                  </button>
                  {enterprise?.eds.map((ed) => (
                    <button key={ed.id} onClick={() => toggleEdSelection(ed.id)} title={ed.location ? `${edLabel(ed)} — ${ed.location}` : edLabel(ed)} className={sourceChipClass(selectedEds.has(ed.id))}>
                      {edLabel(ed)}
                    </button>
                  ))}
                  {(user || userProfile) && (
                    <button onClick={() => setPersonalEnabled(!personalEnabled)} title="Search your uploaded files" className={sourceChipClass(personalEnabled)}>
                      My Files
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <>
            {/* Prior turns transcript (multi-turn thread context) */}
            {priorTurns.map((t, ti) => (
              <div key={`turn-${ti}`} className={`rounded-[6px] overflow-hidden border ${darkMode ? 'border-[#24305C]' : 'border-[#013DED]/40'}`}>
                {/* Question banner (solid brand blue) */}
                <div className="px-5 py-3" style={{ backgroundColor: '#013DED' }}>
                  <p className="text-white font-medium">{t.question}</p>
                </div>
                {/* Answer */}
                <div className={`p-6 ${darkMode ? 'bg-[#0E173D]' : 'bg-white'}`}>
                  <div className={`prose prose-sm max-w-none leading-relaxed font-data ${darkMode ? 'prose-invert text-gray-200' : 'text-gray-800'}`}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={citationComponents}>{t.answer}</ReactMarkdown>
                  </div>
                </div>
              </div>
            ))}

            {/* User Question (current turn) — solid brand blue banner */}
            <div className="rounded-[6px] px-5 py-3" style={{ backgroundColor: '#013DED' }}>
              <p className="text-white font-medium">{submittedQuestion}</p>
            </div>

            {/* Response */}
            {loading ? (
              <div className="flex items-center gap-3 p-4">
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
                <span className={`text-sm ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                  Searching protocols...
                </span>
              </div>
            ) : error ? (
              <div className={`rounded-[6px] px-5 py-4 ${darkMode ? 'bg-red-950 border border-red-900' : 'bg-red-50 border border-red-100'}`}>
                <p className={darkMode ? 'text-red-300' : 'text-red-700'}>{error}</p>
              </div>
            ) : (isStreaming || response) ? (
              <div className="space-y-8">
                {/* Query Time — only after stream finishes */}
                {response && (
                  <div className={`flex flex-wrap items-center gap-2 text-xs ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                    <Sparkles className="w-3 h-3 text-blue-500" />
                    <span>{response.query_time_ms}ms</span>
                    {routeDisplay && (
                      <span className={`px-2 py-1 rounded-full font-medium ${darkMode ? 'bg-[#1E1E1E] text-gray-300 border border-[#2A2A2A]' : 'bg-gray-100 text-gray-600 border border-gray-200'}`}>
                        Searched: {routeDisplay.label}
                      </span>
                    )}
                  </div>
                )}

                {routeDisplay && (
                  <div className={`rounded-[6px] px-4 py-3 text-sm border ${darkMode ? 'bg-[#0E173D] border-[#24305C] text-gray-300' : 'bg-white border-[#013DED] text-[#0E173D]'}`}>
                    <span className="font-semibold text-[#013DED]">
                      Searched: {routeDisplay.label}
                    </span>
                    <span className="ml-2">{routeDisplay.detail}</span>
                  </div>
                )}

                {/* Local Protocol Cards — highlighted box above answer */}
                {protocolCards.length > 0 && (
                  <div className={`rounded-[6px] overflow-hidden border-l-4 border-l-[#013DED] border ${
                    darkMode
                      ? 'bg-[#0E173D] border-[#24305C]'
                      : 'bg-white border-[#013DED]'
                  }`}>
                    <div className="px-5 pt-4 pb-2">
                      <h3 className={`text-sm font-semibold flex items-center gap-2 ${darkMode ? 'text-blue-300' : 'text-blue-700'}`}>
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        Your Local Protocols
                        <span className={`text-xs font-normal ${darkMode ? 'text-blue-400/60' : 'text-blue-500/60'}`}>
                          {protocolCards.length} match{protocolCards.length !== 1 ? 'es' : ''}
                        </span>
                      </h3>
                    </div>
                    {/* Carousel with scroll arrows */}
                    <div className="relative group/protocols px-2 pb-4">
                      {/* Left arrow */}
                      <button
                        onClick={(e) => {
                          const container = (e.currentTarget as HTMLElement).parentElement?.querySelector('[data-protocol-carousel]');
                          if (container) container.scrollBy({ left: -340, behavior: 'smooth' });
                        }}
                        className={`absolute left-0 top-1/2 -translate-y-1/2 z-10 w-10 h-10 rounded-full flex items-center justify-center opacity-0 group-hover/protocols:opacity-100 transition-all duration-200 shadow-lg backdrop-blur-sm ${
                          darkMode ? 'bg-[#1E1E1E]/90 text-white hover:bg-[#2A2A2A]' : 'bg-white/90 text-gray-700 hover:bg-white'
                        }`}
                      >
                        <ChevronLeft className="w-5 h-5" />
                      </button>
                      {/* Right arrow */}
                      <button
                        onClick={(e) => {
                          const container = (e.currentTarget as HTMLElement).parentElement?.querySelector('[data-protocol-carousel]');
                          if (container) container.scrollBy({ left: 340, behavior: 'smooth' });
                        }}
                        className={`absolute right-0 top-1/2 -translate-y-1/2 z-10 w-10 h-10 rounded-full flex items-center justify-center opacity-0 group-hover/protocols:opacity-100 transition-all duration-200 shadow-lg backdrop-blur-sm ${
                          darkMode ? 'bg-[#1E1E1E]/90 text-white hover:bg-[#2A2A2A]' : 'bg-white/90 text-gray-700 hover:bg-white'
                        }`}
                      >
                        <ChevronRight className="w-5 h-5" />
                      </button>
                      {/* Fade edges */}
                      <div className={`absolute left-0 top-0 bottom-0 w-8 z-[5] pointer-events-none bg-gradient-to-r ${darkMode ? 'from-blue-950/30' : 'from-blue-50/70'} to-transparent rounded-l-xl`} />
                      <div className={`absolute right-0 top-0 bottom-0 w-8 z-[5] pointer-events-none bg-gradient-to-l ${darkMode ? 'from-blue-950/30' : 'from-blue-50/70'} to-transparent rounded-r-xl`} />
                      {/* Scroll container */}
                      <div
                        data-protocol-carousel
                        className="flex gap-4 overflow-x-auto px-2 py-1 snap-x snap-mandatory scroll-smooth"
                        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
                      >
                        {protocolCards.map((card, idx) => (
                          <div key={`qa-${card.protocol_id}-${idx}`} className="flex-shrink-0 w-72 snap-start">
                            <ProtocolCard
                              card={card}
                              darkMode={darkMode}
                              compact
                              isStarred={isFavorited(card.protocol_id)}
                              onToggleStar={toggleFavorite}
                              onClickProtocol={trackProtocolClick}
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Answer — streaming or final */}
                <div className={`rounded-[6px] p-6 ${darkMode ? 'bg-[#0E173D] border border-[#24305C]' : 'bg-white border border-[#013DED]/40'}`}>
                  <div className={`prose prose-sm max-w-none leading-relaxed font-data ${darkMode ? 'prose-invert text-gray-200' : 'text-gray-800'}`}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={citationComponents}>{response ? response.answer : streamingAnswer}</ReactMarkdown>
                  </div>

                  {/* Feedback thumbs — bottom-right of answer card */}
                  {response && !isStreaming && (
                    <div className="mt-4 flex flex-col items-end gap-3">
                      {feedbackSubmitted ? (
                        <span className={`text-xs flex items-center gap-1.5 ${darkMode ? 'text-green-400' : 'text-green-600'}`}>
                          <Check className="w-3.5 h-3.5" /> Thanks for your feedback
                        </span>
                      ) : (
                        <>
                          <div className="flex items-center gap-1.5">
                            <button
                              onClick={() => {
                                setFeedbackRating(feedbackRating === "up" ? null : "up");
                                if (feedbackRating !== "up") {
                                  // Auto-submit thumbs up
                                  setFeedbackRating("up");
                                  setFeedbackReasons(new Set());
                                  setFeedbackComment("");
                                  handleFeedbackSubmit("up");
                                }
                              }}
                              className={`p-1.5 rounded-lg transition-all ${
                                feedbackRating === "up"
                                  ? (darkMode ? 'bg-green-900/50 text-green-400' : 'bg-green-100 text-green-600')
                                  : (darkMode ? 'text-gray-500 hover:text-gray-300 hover:bg-[#1E1E1E]' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100')
                              }`}
                              title="Helpful"
                            >
                              <ThumbsUp className="w-4 h-4" fill={feedbackRating === "up" ? "currentColor" : "none"} />
                            </button>
                            <button
                              onClick={() => setFeedbackRating(feedbackRating === "down" ? null : "down")}
                              className={`p-1.5 rounded-lg transition-all ${
                                feedbackRating === "down"
                                  ? (darkMode ? 'bg-red-900/50 text-red-400' : 'bg-red-100 text-red-600')
                                  : (darkMode ? 'text-gray-500 hover:text-gray-300 hover:bg-[#1E1E1E]' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100')
                              }`}
                              title="Not helpful"
                            >
                              <ThumbsDown className="w-4 h-4" fill={feedbackRating === "down" ? "currentColor" : "none"} />
                            </button>
                          </div>

                          {/* Feedback panel — shown when thumbs down */}
                          {feedbackRating === "down" && (
                            <div className={`w-full rounded-xl p-4 space-y-3 border transition-all ${
                              darkMode ? 'bg-[#1E1E1E] border-[#2A2A2A]' : 'bg-gray-50 border-gray-200'
                            }`}>
                              <p className={`text-xs font-medium ${darkMode ? 'text-gray-300' : 'text-gray-600'}`}>
                                What went wrong?
                              </p>
                              <div className="flex flex-wrap gap-2">
                                {FEEDBACK_REASONS.map((reason) => (
                                  <button
                                    key={reason}
                                    onClick={() => toggleFeedbackReason(reason)}
                                    className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all border ${
                                      feedbackReasons.has(reason)
                                        ? (darkMode ? 'bg-red-900/50 text-red-300 border-red-800' : 'bg-red-100 text-red-700 border-red-200')
                                        : (darkMode ? 'bg-[#2A2A2A] text-gray-300 border-[#3A3A3A] hover:border-[#4A4A4A]' : 'bg-white text-gray-600 border-gray-200 hover:border-gray-300')
                                    }`}
                                  >
                                    {reason}
                                  </button>
                                ))}
                              </div>
                              <textarea
                                value={feedbackComment}
                                onChange={(e) => setFeedbackComment(e.target.value)}
                                placeholder="Additional details (optional)"
                                rows={2}
                                className={`w-full rounded-lg px-3 py-2 text-sm resize-none border transition-all ${
                                  darkMode
                                    ? 'bg-[#141414] border-[#2A2A2A] text-gray-200 placeholder-gray-500 focus:border-blue-500'
                                    : 'bg-white border-gray-200 text-gray-800 placeholder-gray-400 focus:border-blue-400'
                                }`}
                              />
                              <div className="flex justify-end">
                                <button
                                  onClick={() => handleFeedbackSubmit()}
                                  disabled={feedbackSubmitting || feedbackReasons.size === 0}
                                  className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${
                                    feedbackSubmitting || feedbackReasons.size === 0
                                      ? (darkMode ? 'bg-[#2A2A2A] text-gray-500 cursor-not-allowed' : 'bg-gray-100 text-gray-400 cursor-not-allowed')
                                      : (darkMode ? 'bg-blue-600 text-white hover:bg-blue-500' : 'bg-blue-500 text-white hover:bg-blue-600')
                                  }`}
                                >
                                  {feedbackSubmitting ? "Submitting..." : "Submit feedback"}
                                </button>
                              </div>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>

                {/* Images - Horizontal Scrolling Carousel */}
                {response && response.images.length > 0 && (
                  <div className="space-y-3">
                    <h3 className={`text-sm font-semibold flex items-center gap-2 ${darkMode ? 'text-gray-200' : 'text-gray-700'}`}>
                      <svg className="w-4 h-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      Related Diagrams
                      <span className={`text-xs font-normal ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                        {response.images.length} image{response.images.length !== 1 ? 's' : ''}
                      </span>
                    </h3>
                    {/* Carousel with scroll arrows */}
                    <div className="relative group/carousel">
                      {/* Left arrow */}
                      <button
                        onClick={(e) => {
                          const container = (e.currentTarget as HTMLElement).parentElement?.querySelector('[data-carousel]');
                          if (container) container.scrollBy({ left: -340, behavior: 'smooth' });
                        }}
                        className={`absolute left-0 top-1/2 -translate-y-1/2 z-10 w-10 h-10 rounded-full flex items-center justify-center opacity-0 group-hover/carousel:opacity-100 transition-all duration-200 shadow-lg backdrop-blur-sm ${
                          darkMode ? 'bg-[#1E1E1E]/90 text-white hover:bg-[#2A2A2A]' : 'bg-white/90 text-gray-700 hover:bg-white'
                        }`}
                      >
                        <ChevronLeft className="w-5 h-5" />
                      </button>
                      {/* Right arrow */}
                      <button
                        onClick={(e) => {
                          const container = (e.currentTarget as HTMLElement).parentElement?.querySelector('[data-carousel]');
                          if (container) container.scrollBy({ left: 340, behavior: 'smooth' });
                        }}
                        className={`absolute right-0 top-1/2 -translate-y-1/2 z-10 w-10 h-10 rounded-full flex items-center justify-center opacity-0 group-hover/carousel:opacity-100 transition-all duration-200 shadow-lg backdrop-blur-sm ${
                          darkMode ? 'bg-[#1E1E1E]/90 text-white hover:bg-[#2A2A2A]' : 'bg-white/90 text-gray-700 hover:bg-white'
                        }`}
                      >
                        <ChevronRight className="w-5 h-5" />
                      </button>
                      {/* Fade edges */}
                      <div className={`absolute left-0 top-0 bottom-0 w-8 z-[5] pointer-events-none bg-gradient-to-r ${darkMode ? 'from-[#0A0A0A]' : 'from-gray-50'} to-transparent rounded-l-xl`} />
                      <div className={`absolute right-0 top-0 bottom-0 w-8 z-[5] pointer-events-none bg-gradient-to-l ${darkMode ? 'from-[#0A0A0A]' : 'from-gray-50'} to-transparent rounded-r-xl`} />
                      {/* Scroll container */}
                      <div
                        data-carousel
                        className={`flex gap-4 overflow-x-auto px-2 py-3 snap-x snap-mandatory scroll-smooth rounded-xl ${
                          darkMode ? 'bg-[#141414]/50' : 'bg-gray-100/50'
                        }`}
                        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
                      >
                        {response.images.map((img, idx) => (
                          <div 
                            key={idx} 
                            onClick={() => handleImageClick(img)}
                            className={`flex-shrink-0 w-80 rounded-xl overflow-hidden border-2 snap-start transition-all duration-200 hover:scale-[1.03] hover:shadow-xl cursor-pointer ${
                              darkMode
                                ? 'bg-[#1E1E1E] border-[#3A3A3A] hover:border-blue-500/50 shadow-md shadow-black/20'
                                : 'bg-white border-gray-200 hover:border-blue-400/50 shadow-md shadow-gray-200/50'
                            }`}
                          >
                            <img
                              src={img.url}
                              alt={`Protocol diagram from ${img.protocol_id}, page ${img.page}`}
                              className="w-full h-auto object-contain"
                              loading="lazy"
                            />
                            <div className={`px-4 py-3 text-xs border-t flex items-center justify-between ${darkMode ? 'text-gray-300 border-[#3A3A3A] bg-[#1E1E1E]' : 'text-gray-600 border-gray-100 bg-gray-50'}`}>
                              <span className="font-medium">{img.protocol_id.replace(/_/g, " ")} · Page {img.page}</span>
                              <svg className={`w-4 h-4 ${darkMode ? 'text-blue-400' : 'text-blue-500'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
                  <div className={`rounded-[6px] p-5 ${darkMode ? 'bg-[#141414] border border-[#2A2A2A]' : 'bg-gray-50 border border-gray-200'}`}>
                    <button
                      onClick={() => setShowSources(v => !v)}
                      title={showSources ? "Hide sources" : "Show sources"}
                      className={`w-full text-sm font-semibold flex items-center gap-2 ${darkMode ? 'text-gray-200' : 'text-gray-700'}`}
                    >
                      <svg className="w-4 h-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      Sources
                      <span className={`text-xs font-normal ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>({response.citations.length})</span>
                      <svg className={`w-4 h-4 ml-auto transition-transform ${showSources ? 'rotate-180' : ''} ${darkMode ? 'text-gray-400' : 'text-gray-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>
                    {showSources && (<>
                    <div className="space-y-2 mt-4">
                      {response.citations.map((cite, idx) => {
                        const isWikEM = cite.source_type === "wikem";
                        const isPMC = cite.source_type === "pmc";
                        const isLITFL = cite.source_type === "litfl";
                        const isREBELEM = cite.source_type === "rebelem";
                        const isALiEM = cite.source_type === "aliem";
                        const isPersonal = cite.source_type === "personal";
                        const isWeb = cite.source_type === "web";
                        const citationLinkClass = isPersonal
                          ? `cursor-pointer hover:opacity-80 ${darkMode ? 'text-violet-400 bg-[#1E1E1E]/50 hover:bg-[#2A2A2A]/50' : 'text-violet-600 bg-violet-50/50 hover:bg-violet-100/50'}`
                          : isWeb
                            ? (darkMode ? 'text-sky-300 hover:bg-[#1E1E1E]' : 'text-sky-700 hover:bg-white hover:shadow-sm')
                            : (darkMode ? 'text-blue-400 hover:bg-[#1E1E1E]' : 'text-blue-600 hover:bg-white hover:shadow-sm');
                        const citationBadgeClass = isPersonal
                          ? (darkMode ? 'bg-violet-900/50 text-violet-300' : 'bg-violet-100 text-violet-700')
                          : isWeb
                            ? (darkMode ? 'bg-sky-900/50 text-sky-300' : 'bg-sky-100 text-sky-700')
                            : isPMC
                              ? (darkMode ? 'bg-purple-900/50 text-purple-300' : 'bg-purple-100 text-purple-700')
                              : isLITFL
                                ? (darkMode ? 'bg-orange-900/50 text-orange-300' : 'bg-orange-100 text-orange-700')
                                : isREBELEM
                                  ? (darkMode ? 'bg-rose-900/50 text-rose-300' : 'bg-rose-100 text-rose-700')
                                  : isALiEM
                                    ? (darkMode ? 'bg-cyan-900/50 text-cyan-300' : 'bg-cyan-100 text-cyan-700')
                                    : isWikEM
                                      ? (darkMode ? 'bg-emerald-900/50 text-emerald-300' : 'bg-emerald-100 text-emerald-700')
                                      : (darkMode ? 'bg-blue-900/50 text-blue-300' : 'bg-blue-100 text-blue-700');
                        const citationPillClass = isPersonal
                          ? (darkMode ? 'bg-violet-900/50 text-violet-400' : 'bg-violet-100 text-violet-700')
                          : isWeb
                            ? (darkMode ? 'bg-sky-900/50 text-sky-400' : 'bg-sky-100 text-sky-700')
                            : isPMC
                              ? (darkMode ? 'bg-purple-900/50 text-purple-400' : 'bg-purple-100 text-purple-700')
                              : isLITFL
                                ? (darkMode ? 'bg-orange-900/50 text-orange-400' : 'bg-orange-100 text-orange-700')
                                : isREBELEM
                                  ? (darkMode ? 'bg-rose-900/50 text-rose-400' : 'bg-rose-100 text-rose-700')
                                  : isALiEM
                                    ? (darkMode ? 'bg-cyan-900/50 text-cyan-400' : 'bg-cyan-100 text-cyan-700')
                                    : isWikEM
                                      ? (darkMode ? 'bg-emerald-900/50 text-emerald-400' : 'bg-emerald-100 text-emerald-700')
                                      : (darkMode ? 'bg-blue-900/50 text-blue-400' : 'bg-blue-100 text-blue-700');
                        const citationSourceLabel = isPersonal
                          ? 'My File'
                          : isWeb
                            ? (cite.source_grade_label || 'Web')
                            : isPMC
                              ? 'PMC'
                              : isLITFL
                                ? 'LITFL'
                                : isREBELEM
                                  ? 'REBEL'
                                  : isALiEM
                                    ? 'ALiEM'
                                    : isWikEM
                                      ? 'WikEM'
                                      : 'Local';

                        const handlePersonalClick = async (e: React.MouseEvent) => {
                          if (!isPersonal || !cite.source_uri) return;
                          e.preventDefault();
                          try {
                            const token = await getIdToken();
                            const res = await fetch(`${API_URL}${cite.source_uri}`, {
                              headers: { Authorization: `Bearer ${token}` },
                            });
                            if (res.ok) {
                              const data = await res.json();
                              if (data.url) openExternal(data.url);
                            }
                          } catch (e) {
                            console.error("Failed to get download URL:", e);
                          }
                        };

                        return (
                          <a
                            key={idx}
                            id={`cite-${idx + 1}`}
                            href={isPersonal ? "#" : cite.source_uri}
                            target={isPersonal ? undefined : "_blank"}
                            rel={isPersonal ? undefined : "noopener noreferrer"}
                            onClick={isPersonal ? handlePersonalClick : undefined}
                            style={isPersonal ? { cursor: "pointer" } : undefined}
                            className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all text-sm w-full text-left ${citationLinkClass}`}
                          >
                            <span className={`w-6 h-6 flex items-center justify-center rounded text-xs font-medium ${citationBadgeClass}`}>{idx + 1}</span>
                            <div className="flex-1 min-w-0">
                              <span className="block truncate">{cite.protocol_id.replace(/_/g, " ")}</span>
                              {cite.source_domain && (
                                <span className={`block truncate text-[11px] ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                                  {cite.source_domain}
                                  {cite.is_preferred_em_source ? ' · preferred EM source' : ''}
                                </span>
                              )}
                            </div>
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider whitespace-nowrap ${citationPillClass}`}>
                              {citationSourceLabel}
                            </span>
                            {isPersonal ? (
                              <svg className="w-4 h-4 text-violet-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                              </svg>
                            ) : (
                              <svg className="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                              </svg>
                            )}
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
                    {response.citations.some(c => c.source_type === "rebelem") && (
                      <p className={`mt-3 text-[11px] ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                        REBEL EM content from <a href="https://rebelem.com" target="_blank" rel="noopener noreferrer" className="underline">rebelem.com</a> under CC BY-NC-ND 4.0 — evidence-based reviews
                      </p>
                    )}
                    {response.citations.some(c => c.source_type === "aliem") && (
                      <p className={`mt-3 text-[11px] ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                        ALiEM content from <a href="https://www.aliem.com" target="_blank" rel="noopener noreferrer" className="underline">aliem.com</a> under CC BY-NC-ND 3.0 — PV Cards &amp; MEdIC Series
                      </p>
                    )}
                    {response.citations.some(c => c.source_type === "web") && (
                      <p className={`mt-3 text-[11px] ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                        Web citations are external sources returned by the current search path for this answer.
                      </p>
                    )}
                    </>)}
                  </div>
                )}
              </div>
            ) : null}

            {/* Follow-up reply — matches the "| Anything else?" prompt */}
            <div className="mt-2 pt-2">
              <div className="flex items-baseline gap-1.5">
                <span
                  aria-hidden="true"
                  className={`font-title font-medium text-2xl md:text-3xl select-none flex-shrink-0 ${!question ? 'animate-caret' : ''}`}
                  style={{ letterSpacing: 0, lineHeight: 1.19, color: '#013DED', transform: 'translateY(-0.09em)' }}
                >
                  |
                </span>
                <textarea
                  placeholder="Anything else?"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSubmit();
                    }
                  }}
                  rows={1}
                  style={{ letterSpacing: 0, lineHeight: 1.19, caretColor: 'transparent' }}
                  className={`flex-1 p-0 font-title font-medium bg-transparent resize-none focus:outline-none text-2xl md:text-3xl placeholder:opacity-100 focus:placeholder:text-transparent ${
                    darkMode ? 'text-white placeholder:text-white' : 'text-[#0E173D] placeholder:text-[#0E173D]'
                  }`}
                />
                <MicButton
                  isSupported={micSupported}
                  listening={micListening}
                  permissionDenied={micPermissionDenied}
                  onToggle={() => toggleMic(question, setQuestion)}
                  darkMode={darkMode}
                  size="md"
                />
                <button
                  onClick={handleSubmit}
                  disabled={!question.trim() || loading || isStreaming}
                  title="Submit (or press Enter)"
                  className="self-center inline-flex items-center justify-center w-8 h-8 flex-shrink-0 rounded-[4px] text-white bg-[#013DED] hover:bg-[#012FB8] transition-all duration-200 disabled:opacity-40"
                >
                  {loading || isStreaming ? (
                    <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <ArrowUp className="w-4 h-4" />
                  )}
                </button>
              </div>
              {/* Source chips */}
              <div className="mt-3 flex items-center gap-2 flex-wrap">
                <button onClick={() => toggleSource("wikem")} title="EM Universe — WikEM, PMC, LITFL, REBEL EM, ALiEM" className={sourceChipClass(globeActive)}>
                  EM Universe
                </button>
                {enterprise?.eds.map((ed) => (
                  <button key={ed.id} onClick={() => toggleEdSelection(ed.id)} title={ed.location ? `${edLabel(ed)} — ${ed.location}` : edLabel(ed)} className={sourceChipClass(selectedEds.has(ed.id))}>
                    {edLabel(ed)}
                  </button>
                ))}
                {(user || userProfile) && (
                  <button onClick={() => setPersonalEnabled(!personalEnabled)} title="Search your uploaded files" className={sourceChipClass(personalEnabled)}>
                    My Files
                  </button>
                )}
              </div>
            </div>
            </>
            )}
            </div>
              );
            })}

            {/* New conversation — opens a column to the right */}
            <button
              onClick={startNewConversation}
              title="Start a new conversation"
              className="flex-shrink-0 inline-flex items-center gap-2"
            >
              <span className="w-9 h-9 rounded-[6px] flex items-center justify-center text-white" style={{ backgroundColor: '#013DED' }}>
                <Plus className="w-5 h-5" />
              </span>
              <span className={`font-data text-sm font-bold uppercase tracking-wide whitespace-nowrap ${darkMode ? 'text-gray-200' : 'text-[#0E173D]'}`}>New conversation</span>
            </button>

            {/* trailing spacer so the last/active column can center in the window */}
            <div className="flex-shrink-0 w-[calc(50vw-350px)] max-[820px]:hidden" aria-hidden="true" />
          </div>
        )}
      </div>

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
              className="absolute -top-3 -right-3 z-10 w-8 h-8 rounded-full bg-[#1E1E1E] text-white flex items-center justify-center hover:bg-[#2A2A2A] shadow-lg"
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

      {/* Footer */}
      <footer className={`mt-auto w-full py-2 text-center text-xs ${
        darkMode ? 'text-gray-600' : 'text-gray-400'
      }`}>
        <p className="mb-1">Pilot: AI-generated content may contain errors and may change as we evaluate the tool. Always verify with primary sources and clinical judgment.</p>
        <p className="mb-1">
          For a walkthrough of the app{' '}
          <a
            href="https://youtu.be/wgF-d99_u6s"
            target="_blank"
            rel="noopener noreferrer"
            className={`hover:underline ${darkMode ? 'text-blue-500 hover:text-blue-400' : 'text-blue-600 hover:text-blue-500'}`}
          >
            click here
          </a>
        </p>
        <a href="/legal" target="_blank" rel="noopener noreferrer" className={`hover:underline ${darkMode ? 'hover:text-gray-300' : 'hover:text-gray-600'}`}>Legal</a>
        <span className="mx-2">·</span>
        <a href="/about" target="_blank" rel="noopener noreferrer" className={`hover:underline ${darkMode ? 'hover:text-gray-300' : 'hover:text-gray-600'}`}>About</a>
      </footer>

      </main>
    </div>
  );
}

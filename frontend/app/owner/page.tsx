"use client";

import { useState, useEffect, useCallback } from "react";
import { Users, Building2, FolderOpen, FileText, Shield, Crown, Mail, Plus, Trash2, RefreshCw, ChevronDown, ChevronRight, ArrowLeft, Check, X, Database, MapPin, Palette, Clock, Bell, UserCheck, UserX, BarChart3, TrendingUp, TrendingDown, ThumbsUp, ThumbsDown, Activity, Search, MousePointerClick } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://em-protocol-api-930035889332.us-central1.run.app";

interface Admin {
  uid: string;
  email: string;
  role: string;
  edAccess: string[];
  enterpriseId: string;
  accessStatus: string;
  createdAt: string;
}

interface AccessRequest {
  id: string;
  google_email: string;
  google_uid: string;
  mayo_email: string;
  name: string;
  status: "pending" | "approved" | "denied";
  requested_at: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
}

interface NotificationData {
  id: string;
  type: string;
  message: string;
  target_role: string;
  read: boolean;
  created_at: string;
  reference_id: string;
}

interface BundleData {
  id: string;
  name: string;
  slug?: string;
  description?: string;
  icon?: string;
  color?: string;
}

interface EDData {
  id: string;
  name: string;
  slug?: string;
  location?: string;
  bundles: BundleData[];
}

interface EnterpriseData {
  id: string;
  name: string;
  slug?: string;
  allowed_domains?: string[];
  eds: EDData[];
}

export default function OwnerDashboard() {
  const { user, userProfile, loading: authLoading } = useAuth();
  const router = useRouter();
  
  const [view, setView] = useState<"admins" | "hierarchy" | "requests" | "analytics">("hierarchy");
  const [admins, setAdmins] = useState<Admin[]>([]);
  const [enterprises, setEnterprises] = useState<EnterpriseData[]>([]);
  const [expandedEnterprises, setExpandedEnterprises] = useState<Set<string>>(new Set());
  const [expandedEDs, setExpandedEDs] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [showAddAdmin, setShowAddAdmin] = useState(false);
  const [newAdminEmail, setNewAdminEmail] = useState("");
  const [newAdminRole, setNewAdminRole] = useState<"admin" | "super_admin">("admin");
  const [newAdminEnterprise, setNewAdminEnterprise] = useState("");
  const [newAdminBundles, setNewAdminBundles] = useState<string[]>([]);
  const [availableEDs, setAvailableEDs] = useState<string[]>([]);
  const [allUsers, setAllUsers] = useState<Admin[]>([]);
  const [userSearch, setUserSearch] = useState("");
  const [showUserDropdown, setShowUserDropdown] = useState(false);

  // Access requests state
  const [allAccessRequests, setAllAccessRequests] = useState<AccessRequest[]>([]);
  const [requestsFilter, setRequestsFilter] = useState<"pending" | "approved" | "denied" | "all">("pending");
  const [requestsLoading, setRequestsLoading] = useState(false);
  const [processingRequest, setProcessingRequest] = useState<string | null>(null);

  // Derived: filter access requests client-side
  const accessRequests = requestsFilter === "all"
    ? allAccessRequests
    : allAccessRequests.filter((r) => r.status === requestsFilter);

  // Notifications state
  const [notifications, setNotifications] = useState<NotificationData[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  // Analytics state
  const [analyticsRange, setAnalyticsRange] = useState("7d");
  const [analyticsSummary, setAnalyticsSummary] = useState<{
    users: number;
    usersChange: number;
    queries: number;
    queriesChange: number;
    avgPerUser: number;
    feedbackUp: number;
    feedbackDown: number;
    feedbackScore: number;
    totalFeedback: number;
  } | null>(null);
  const [analyticsTrend, setAnalyticsTrend] = useState<{ period: string; users: number; queries: number }[]>([]);
  const [analyticsUsers, setAnalyticsUsers] = useState<{ email: string; queries: number; lastActive: string; feedbackUp: number; feedbackDown: number }[]>([]);
  const [analyticsFeedback, setAnalyticsFeedback] = useState<{ feedback: { id: string; query: string; rating: string; reasons: string[]; comment: string; user_email: string; date: string }[]; total: number; page: number; pageSize: number; totalPages: number }>({ feedback: [], total: 0, page: 1, pageSize: 20, totalPages: 0 });
  const [analyticsProtocolClicks, setAnalyticsProtocolClicks] = useState<{ protocolId: string; title: string; clicks: number }[]>([]);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [feedbackFilter, setFeedbackFilter] = useState<"all" | "up" | "down">("all");
  const [feedbackPage, setFeedbackPage] = useState(1);

  // Create modals
  const [showCreateEnterprise, setShowCreateEnterprise] = useState(false);
  const [showCreateED, setShowCreateED] = useState<string | null>(null); // enterprise_id or null
  const [showCreateBundle, setShowCreateBundle] = useState<{ enterpriseId: string; edId: string } | null>(null);

  // Form state
  const [newEnterprise, setNewEnterprise] = useState({ id: "", name: "", domains: "" });
  const [newED, setNewED] = useState({ id: "", name: "", location: "" });
  const [newBundle, setNewBundle] = useState({ id: "", name: "", description: "", color: "#3B82F6" });
  const [creating, setCreating] = useState(false);

  // Check if user is owner or super_admin — only super_admins can access
  useEffect(() => {
    if (!authLoading && ((!user && !userProfile) || userProfile?.role !== "super_admin")) {
      router.push("/");
    }
  }, [user, userProfile, authLoading, router]);

  const isSuperAdmin = userProfile?.role === "super_admin";

  // Fetch admins for the enterprise
  const fetchAdmins = async () => {
    if (!userProfile?.enterpriseId && !isSuperAdmin) return;
    
    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const url = userProfile?.enterpriseId
        ? `${API_URL}/admin/users?enterprise_id=${userProfile.enterpriseId}`
        : `${API_URL}/admin/users`;
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      });
      
      if (res.ok) {
        const data = await res.json();
        setAdmins(data.users || []);
      }
    } catch (err) {
      console.error("Failed to fetch admins:", err);
    } finally {
      setLoading(false);
    }
  };

  // Fetch enterprises hierarchy from Firestore
  const fetchEnterprises = async () => {
    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const res = await fetch(`${API_URL}/admin/enterprises`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setEnterprises(data.enterprises || []);
        
        // Extract available EDs for admin form
        if (userProfile?.enterpriseId) {
          const ent = (data.enterprises || []).find((e: EnterpriseData) => e.id === userProfile.enterpriseId);
          if (ent) {
            setAvailableEDs(ent.eds.map((ed: EDData) => ed.id));
          }
        }
      }
    } catch (err) {
      console.error("Failed to fetch enterprises:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (userProfile?.role === "super_admin") {
      fetchAdmins();
      fetchEnterprises();
      fetchAllUsers();
      fetchAccessRequests();
      fetchNotifications();
    }
  }, [userProfile]);

  // Fetch all users (for user picker)
  const fetchAllUsers = async () => {
    try {
      const token = await user?.getIdToken();
      const res = await fetch(`${API_URL}/admin/users`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setAllUsers(data.users || []);
      }
    } catch (err) {
      console.error("Failed to fetch all users:", err);
    }
  };

  // Fetch access requests (always fetch all, filter client-side)
  const fetchAccessRequests = async () => {
    setRequestsLoading(true);
    try {
      const token = await user?.getIdToken();
      const res = await fetch(`${API_URL}/access-requests`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setAllAccessRequests(data.requests || []);
      }
    } catch (err) {
      console.error("Failed to fetch access requests:", err);
    } finally {
      setRequestsLoading(false);
    }
  };

  // Fetch notifications
  const fetchNotifications = async () => {
    try {
      const token = await user?.getIdToken();
      const res = await fetch(`${API_URL}/notifications`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setNotifications(data.notifications || []);
        setUnreadCount(data.unread_count || 0);
      }
    } catch (err) {
      console.error("Failed to fetch notifications:", err);
    }
  };

  // Fetch analytics data
  const fetchAnalytics = useCallback(async (range: string) => {
    setAnalyticsLoading(true);
    try {
      const token = await user?.getIdToken();
      const headers = { Authorization: `Bearer ${token}` };
      const [summaryRes, trendRes, usersRes, feedbackRes, clicksRes] = await Promise.all([
        fetch(`${API_URL}/analytics/summary?range=${range}`, { headers }),
        fetch(`${API_URL}/analytics/trend?range=${range}`, { headers }),
        fetch(`${API_URL}/analytics/users?range=${range}`, { headers }),
        fetch(`${API_URL}/analytics/feedback?range=${range}&rating=${feedbackFilter}&page=${feedbackPage}`, { headers }),
        fetch(`${API_URL}/analytics/protocol-clicks?range=${range}`, { headers }),
      ]);
      if (summaryRes.ok) setAnalyticsSummary(await summaryRes.json());
      if (trendRes.ok) setAnalyticsTrend((await trendRes.json()).data || []);
      if (usersRes.ok) setAnalyticsUsers((await usersRes.json()).users || []);
      if (feedbackRes.ok) setAnalyticsFeedback(await feedbackRes.json());
      if (clicksRes.ok) setAnalyticsProtocolClicks((await clicksRes.json()).protocols || []);
    } catch (err) {
      console.error("Failed to fetch analytics:", err);
    } finally {
      setAnalyticsLoading(false);
    }
  }, [user, feedbackFilter, feedbackPage]);

  // Reload analytics when range, filter, or page changes
  useEffect(() => {
    if (view === "analytics" && userProfile?.role === "super_admin") {
      fetchAnalytics(analyticsRange);
    }
  }, [view, analyticsRange, feedbackFilter, feedbackPage, fetchAnalytics, userProfile]);

  // Handle approve/deny access request
  const handleAccessRequestAction = async (requestId: string, action: "approve" | "deny") => {
    setProcessingRequest(requestId);
    try {
      const token = await user?.getIdToken();
      const res = await fetch(`${API_URL}/access-requests/${requestId}?action=${action}`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        // Refresh requests and notifications
        await fetchAccessRequests();
        await fetchNotifications();
      } else {
        const err = await res.json();
        alert(err.detail || `Failed to ${action} request`);
      }
    } catch (err) {
      console.error(`Failed to ${action} request:`, err);
      alert(`Failed to ${action} request`);
    } finally {
      setProcessingRequest(null);
    }
  };

  const handleAddAdmin = async () => {
    if (!newAdminEmail.trim()) return;
    // For admin role, need an enterprise
    if (newAdminRole === "admin" && !newAdminEnterprise && !userProfile?.enterpriseId) return;
    
    try {
      const token = await user?.getIdToken();
      const enterpriseId = newAdminRole === "super_admin" 
        ? "" 
        : (newAdminEnterprise || userProfile?.enterpriseId || "");
      
      const res = await fetch(`${API_URL}/admin/users`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          email: newAdminEmail,
          enterprise_id: enterpriseId,
          role: newAdminRole,
          ed_access: newAdminRole === "super_admin" ? [] : newAdminBundles,
        }),
      });
      
      if (res.ok) {
        setShowAddAdmin(false);
        setNewAdminEmail("");
        setNewAdminRole("admin");
        setNewAdminEnterprise("");
        setNewAdminBundles([]);
        setUserSearch("");
        setShowUserDropdown(false);
        fetchAdmins();
        fetchAllUsers();
      } else {
        alert("Failed to add admin");
      }
    } catch (err) {
      console.error("Failed to add admin:", err);
      alert("Failed to add admin");
    }
  };

  const handleRemoveAdmin = async (uid: string) => {
    if (!confirm("Remove this admin?")) return;
    
    try {
      const token = await user?.getIdToken();
      const res = await fetch(`${API_URL}/admin/users/${uid}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      
      if (res.ok) {
        fetchAdmins();
      } else {
        alert("Failed to remove admin");
      }
    } catch (err) {
      console.error("Failed to remove admin:", err);
      alert("Failed to remove admin");
    }
  };

  const handleCreateEnterprise = async () => {
    if (!newEnterprise.id.trim() || !newEnterprise.name.trim()) return;
    setCreating(true);
    try {
      const token = await user?.getIdToken();
      const res = await fetch(`${API_URL}/admin/enterprises`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          id: newEnterprise.id.toLowerCase().replace(/\s+/g, "-"),
          name: newEnterprise.name,
          allowed_domains: newEnterprise.domains
            .split(",")
            .map((d) => d.trim())
            .filter(Boolean),
        }),
      });
      
      if (res.ok) {
        setShowCreateEnterprise(false);
        setNewEnterprise({ id: "", name: "", domains: "" });
        fetchEnterprises();
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to create enterprise");
      }
    } catch (err) {
      console.error("Failed to create enterprise:", err);
      alert("Failed to create enterprise");
    } finally {
      setCreating(false);
    }
  };

  const handleCreateED = async () => {
    if (!showCreateED || !newED.id.trim() || !newED.name.trim()) return;
    setCreating(true);
    try {
      const token = await user?.getIdToken();
      const res = await fetch(`${API_URL}/admin/enterprises/${showCreateED}/eds`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          id: newED.id.toLowerCase().replace(/\s+/g, "-"),
          name: newED.name,
          location: newED.location,
        }),
      });
      
      if (res.ok) {
        setShowCreateED(null);
        setNewED({ id: "", name: "", location: "" });
        fetchEnterprises();
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to create ED");
      }
    } catch (err) {
      console.error("Failed to create ED:", err);
      alert("Failed to create ED");
    } finally {
      setCreating(false);
    }
  };

  const handleCreateBundle = async () => {
    if (!showCreateBundle || !newBundle.id.trim() || !newBundle.name.trim()) return;
    setCreating(true);
    try {
      const token = await user?.getIdToken();
      const res = await fetch(
        `${API_URL}/admin/enterprises/${showCreateBundle.enterpriseId}/eds/${showCreateBundle.edId}/bundles`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            id: newBundle.id.toLowerCase().replace(/\s+/g, "-"),
            name: newBundle.name,
            description: newBundle.description,
            color: newBundle.color,
          }),
        }
      );
      
      if (res.ok) {
        setShowCreateBundle(null);
        setNewBundle({ id: "", name: "", description: "", color: "#3B82F6" });
        fetchEnterprises();
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to create bundle");
      }
    } catch (err) {
      console.error("Failed to create bundle:", err);
      alert("Failed to create bundle");
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteBundle = async (enterpriseId: string, edId: string, bundleId: string) => {
    if (!confirm(`Delete bundle "${bundleId}"? This only removes the Firestore record, not uploaded protocols.`)) return;
    try {
      const token = await user?.getIdToken();
      const res = await fetch(`${API_URL}/admin/enterprises/${enterpriseId}/eds/${edId}/bundles/${bundleId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        fetchEnterprises();
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to delete bundle");
      }
    } catch (err) {
      console.error("Failed to delete bundle:", err);
      alert("Failed to delete bundle");
    }
  };

  const handleDeleteED = async (enterpriseId: string, edId: string) => {
    if (!confirm(`Delete ED "${edId}" and all its bundles? This only removes Firestore records, not uploaded protocols.`)) return;
    try {
      const token = await user?.getIdToken();
      const res = await fetch(`${API_URL}/admin/enterprises/${enterpriseId}/eds/${edId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        fetchEnterprises();
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to delete ED");
      }
    } catch (err) {
      console.error("Failed to delete ED:", err);
      alert("Failed to delete ED");
    }
  };

  const handleDeleteEnterprise = async (enterpriseId: string) => {
    if (!confirm(`Delete enterprise "${enterpriseId}" and ALL its EDs and bundles? This only removes Firestore records, not uploaded protocols.`)) return;
    try {
      const token = await user?.getIdToken();
      const res = await fetch(`${API_URL}/admin/enterprises/${enterpriseId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        fetchEnterprises();
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to delete enterprise");
      }
    } catch (err) {
      console.error("Failed to delete enterprise:", err);
      alert("Failed to delete enterprise");
    }
  };

  const toggleEnterprise = (id: string) => {
    const next = new Set(expandedEnterprises);
    next.has(id) ? next.delete(id) : next.add(id);
    setExpandedEnterprises(next);
  };

  const toggleED = (key: string) => {
    const next = new Set(expandedEDs);
    next.has(key) ? next.delete(key) : next.add(key);
    setExpandedEDs(next);
  };

  const toggleEDSelection = (ed: string) => {
    setNewAdminBundles((prev) =>
      prev.includes(ed) ? prev.filter((b) => b !== ed) : [...prev, ed]
    );
  };

  if (authLoading || !userProfile || userProfile.role !== "super_admin") {
    return (
      <div className="min-h-screen bg-[#131314] text-white flex items-center justify-center">
        <RefreshCw className="w-8 h-8 animate-spin text-[#8ab4f8]" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#131314] text-white flex">
      {/* Sidebar */}
      <div className="w-16 flex-shrink-0 flex flex-col items-center py-4 border-r border-white/10">
        <Link href="/" className="w-10 h-10 flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/10 rounded-full transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </Link>
      </div>

      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="h-16 flex items-center justify-between px-6 border-b border-white/5">
          <div className="flex items-center gap-3">
            <Crown className="w-6 h-6 text-yellow-500" />
            <span className="text-xl font-normal text-white">Owner Dashboard</span>
            <span className="text-xs text-[#9aa0a6]">•</span>
            <span className="text-sm text-[#8ab4f8]">{userProfile.enterpriseName || userProfile.enterpriseId || "System Admin"}</span>
          </div>
          <Link
            href="/admin"
            className="text-sm text-[#9aa0a6] hover:text-white px-4 py-2 rounded-full border border-[#3c4043] hover:bg-[#3c4043] transition-colors"
          >
            Admin Upload
          </Link>
        </header>

        {/* View Toggle */}
        <div className="px-6 pt-4">
          <div className="flex gap-2">
            <button
              onClick={() => setView("hierarchy")}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-colors flex items-center gap-2 ${
                view === "hierarchy"
                  ? "bg-[#8ab4f8] text-[#131314]"
                  : "text-[#9aa0a6] hover:text-white hover:bg-white/10"
              }`}
            >
              <Building2 className="w-4 h-4" />
              Enterprises & EDs
            </button>
            <button
              onClick={() => setView("requests")}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-colors flex items-center gap-2 relative ${
                view === "requests"
                  ? "bg-[#8ab4f8] text-[#131314]"
                  : "text-[#9aa0a6] hover:text-white hover:bg-white/10"
              }`}
            >
              <UserCheck className="w-4 h-4" />
              Access Requests
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center font-bold">
                  {unreadCount}
                </span>
              )}
            </button>
            <button
              onClick={() => setView("admins")}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-colors flex items-center gap-2 ${
                view === "admins"
                  ? "bg-[#8ab4f8] text-[#131314]"
                  : "text-[#9aa0a6] hover:text-white hover:bg-white/10"
              }`}
            >
              <Users className="w-4 h-4" />
              Admin Users
            </button>
            <button
              onClick={() => setView("analytics")}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-colors flex items-center gap-2 ${
                view === "analytics"
                  ? "bg-[#8ab4f8] text-[#131314]"
                  : "text-[#9aa0a6] hover:text-white hover:bg-white/10"
              }`}
            >
              <BarChart3 className="w-4 h-4" />
              Analytics
            </button>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 overflow-auto p-6">
          <div className="max-w-5xl mx-auto space-y-6">

            {/* ===== Hierarchy View ===== */}
            {view === "hierarchy" && (
              <div className="bg-[#1e1f20] rounded-[28px] border border-[#3c4043] overflow-hidden">
                <div className="flex items-center justify-between p-5 border-b border-[#3c4043]">
                  <h2 className="text-lg font-medium text-white flex items-center gap-2">
                    <Building2 className="w-5 h-5 text-[#8ab4f8]" />
                    Enterprises → EDs → Bundles
                  </h2>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={fetchEnterprises}
                      disabled={loading}
                      className="text-sm text-[#8ab4f8] hover:text-[#aecbfa] flex items-center gap-2 px-4 py-2 rounded-full hover:bg-[#8ab4f8]/10 transition-colors"
                    >
                      <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                      Refresh
                    </button>
                    {isSuperAdmin && (
                      <button
                        onClick={() => setShowCreateEnterprise(true)}
                        className="bg-[#8ab4f8] text-[#131314] px-4 py-2 rounded-full text-sm font-medium hover:bg-[#aecbfa] transition-colors flex items-center gap-2"
                      >
                        <Plus className="w-4 h-4" />
                        New Enterprise
                      </button>
                    )}
                  </div>
                </div>

                {enterprises.length === 0 ? (
                  <div className="p-8 text-center">
                    <Building2 className="w-12 h-12 mx-auto text-[#5f6368] mb-3" />
                    <p className="text-[#9aa0a6]">No enterprises found</p>
                    <p className="text-sm text-[#5f6368]">Create an enterprise to get started</p>
                  </div>
                ) : (
                  <div className="divide-y divide-[#3c4043]">
                    {enterprises.map((enterprise) => (
                      <div key={enterprise.id}>
                        {/* Enterprise row */}
                        <div className="flex items-center hover:bg-[#2c2d2e] transition-colors">
                          <button
                            onClick={() => toggleEnterprise(enterprise.id)}
                            className="flex-1 px-5 py-4 flex items-center gap-3"
                          >
                            {expandedEnterprises.has(enterprise.id) ? (
                              <ChevronDown className="w-4 h-4 text-[#9aa0a6]" />
                            ) : (
                              <ChevronRight className="w-4 h-4 text-[#9aa0a6]" />
                            )}
                            <Building2 className="w-5 h-5 text-[#8ab4f8]" />
                            <div className="text-left">
                              <span className="font-medium text-white">{enterprise.name}</span>
                              <span className="text-xs text-[#5f6368] ml-2">{enterprise.id}</span>
                            </div>
                            {enterprise.allowed_domains && enterprise.allowed_domains.length > 0 && (
                              <span className="text-xs text-[#5f6368] ml-2">
                                {enterprise.allowed_domains.join(", ")}
                              </span>
                            )}
                            <span className="text-xs text-[#5f6368] ml-auto">
                              {enterprise.eds.length} ED(s)
                            </span>
                          </button>
                          {isSuperAdmin && (
                            <button
                              onClick={() => handleDeleteEnterprise(enterprise.id)}
                              className="p-2 mr-3 text-[#5f6368] hover:text-red-400 hover:bg-red-400/10 rounded-full transition-colors"
                              title="Delete enterprise"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </div>

                        {/* EDs under enterprise */}
                        {expandedEnterprises.has(enterprise.id) && (
                          <div className="bg-[#1a1a1b]">
                            {enterprise.eds.map((ed) => {
                              const edKey = `${enterprise.id}/${ed.id}`;
                              return (
                                <div key={edKey}>
                                  {/* ED row */}
                                  <div className="flex items-center hover:bg-[#2c2d2e] transition-colors">
                                    <button
                                      onClick={() => toggleED(edKey)}
                                      className="flex-1 pl-12 pr-2 py-3 flex items-center gap-3"
                                    >
                                      {expandedEDs.has(edKey) ? (
                                        <ChevronDown className="w-4 h-4 text-[#9aa0a6]" />
                                      ) : (
                                        <ChevronRight className="w-4 h-4 text-[#9aa0a6]" />
                                      )}
                                      <MapPin className="w-4 h-4 text-green-400" />
                                      <div className="text-left">
                                        <span className="text-[#e8eaed]">{ed.name}</span>
                                        <span className="text-xs text-[#5f6368] ml-2">{ed.id}</span>
                                      </div>
                                      {ed.location && (
                                        <span className="text-xs text-[#5f6368] ml-2">{ed.location}</span>
                                      )}
                                      <span className="text-xs text-[#5f6368] ml-auto">
                                        {ed.bundles.length} bundle(s)
                                      </span>
                                    </button>
                                    {isSuperAdmin && (
                                      <button
                                        onClick={() => handleDeleteED(enterprise.id, ed.id)}
                                        className="p-2 mr-3 text-[#5f6368] hover:text-red-400 hover:bg-red-400/10 rounded-full transition-colors"
                                        title="Delete ED"
                                      >
                                        <Trash2 className="w-3.5 h-3.5" />
                                      </button>
                                    )}
                                  </div>

                                  {/* Bundles under ED */}
                                  {expandedEDs.has(edKey) && (
                                    <div className="bg-[#131314]">
                                      {ed.bundles.map((bundle) => (
                                        <div
                                          key={`${edKey}/${bundle.id}`}
                                          className="pl-20 pr-5 py-3 flex items-center gap-3 hover:bg-[#2c2d2e] transition-colors"
                                        >
                                          <div
                                            className="w-3 h-3 rounded-full flex-shrink-0"
                                            style={{ backgroundColor: bundle.color || "#3B82F6" }}
                                          />
                                          <FolderOpen className="w-4 h-4 text-yellow-500" />
                                          <div className="flex-1">
                                            <span className="text-[#e8eaed]">{bundle.name}</span>
                                            <span className="text-xs text-[#5f6368] ml-2">{bundle.id}</span>
                                            {bundle.description && (
                                              <p className="text-xs text-[#5f6368] mt-0.5">{bundle.description}</p>
                                            )}
                                          </div>
                                          {isSuperAdmin && (
                                            <button
                                              onClick={() => handleDeleteBundle(enterprise.id, ed.id, bundle.id)}
                                              className="p-1.5 text-[#5f6368] hover:text-red-400 hover:bg-red-400/10 rounded-full transition-colors"
                                              title="Delete bundle"
                                            >
                                              <Trash2 className="w-3.5 h-3.5" />
                                            </button>
                                          )}
                                        </div>
                                      ))}

                                      {/* Add Bundle button */}
                                      {isSuperAdmin && (
                                        <button
                                          onClick={() => setShowCreateBundle({ enterpriseId: enterprise.id, edId: ed.id })}
                                          className="pl-20 pr-5 py-3 w-full flex items-center gap-3 text-[#8ab4f8] hover:bg-[#8ab4f8]/10 transition-colors"
                                        >
                                          <Plus className="w-4 h-4" />
                                          <span className="text-sm">Add Bundle</span>
                                        </button>
                                      )}
                                    </div>
                                  )}
                                </div>
                              );
                            })}

                            {/* Add ED button */}
                            {isSuperAdmin && (
                              <button
                                onClick={() => setShowCreateED(enterprise.id)}
                                className="pl-12 pr-5 py-3 w-full flex items-center gap-3 text-[#8ab4f8] hover:bg-[#8ab4f8]/10 transition-colors border-t border-[#3c4043]/50"
                              >
                                <Plus className="w-4 h-4" />
                                <span className="text-sm">Add ED</span>
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* ===== Create Enterprise Modal ===== */}
            {showCreateEnterprise && (
              <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                <div className="bg-[#1e1f20] rounded-[28px] border border-[#3c4043] p-6 w-full max-w-md mx-4">
                  <h3 className="text-xl font-medium text-white mb-4 flex items-center gap-2">
                    <Building2 className="w-5 h-5 text-[#8ab4f8]" />
                    New Enterprise
                  </h3>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm text-[#9aa0a6] mb-2">Enterprise Name</label>
                      <input
                        type="text"
                        value={newEnterprise.name}
                        onChange={(e) => {
                          const name = e.target.value;
                          setNewEnterprise({
                            ...newEnterprise,
                            name,
                            id: name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""),
                          });
                        }}
                        placeholder="Mayo Clinic"
                        className="w-full px-4 py-3 bg-[#131314] border border-[#3c4043] rounded-full text-white placeholder-[#5f6368] focus:outline-none focus:border-[#8ab4f8]"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-[#9aa0a6] mb-2">ID (URL-safe)</label>
                      <input
                        type="text"
                        value={newEnterprise.id}
                        onChange={(e) => setNewEnterprise({ ...newEnterprise, id: e.target.value })}
                        placeholder="mayo-clinic"
                        className="w-full px-4 py-3 bg-[#131314] border border-[#3c4043] rounded-full text-white placeholder-[#5f6368] focus:outline-none focus:border-[#8ab4f8]"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-[#9aa0a6] mb-2">Allowed Domains (comma-separated)</label>
                      <input
                        type="text"
                        value={newEnterprise.domains}
                        onChange={(e) => setNewEnterprise({ ...newEnterprise, domains: e.target.value })}
                        placeholder="mayo.edu, mayo.org"
                        className="w-full px-4 py-3 bg-[#131314] border border-[#3c4043] rounded-full text-white placeholder-[#5f6368] focus:outline-none focus:border-[#8ab4f8]"
                      />
                    </div>
                  </div>
                  <div className="flex gap-3 mt-6">
                    <button
                      onClick={() => { setShowCreateEnterprise(false); setNewEnterprise({ id: "", name: "", domains: "" }); }}
                      className="flex-1 px-4 py-3 bg-[#3c4043] text-white rounded-full hover:bg-[#5f6368] transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleCreateEnterprise}
                      disabled={!newEnterprise.id.trim() || !newEnterprise.name.trim() || creating}
                      className="flex-1 px-4 py-3 bg-[#8ab4f8] text-[#131314] rounded-full font-medium hover:bg-[#aecbfa] disabled:bg-[#3c4043] disabled:text-[#5f6368] disabled:cursor-not-allowed transition-colors"
                    >
                      {creating ? "Creating..." : "Create Enterprise"}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* ===== Create ED Modal ===== */}
            {showCreateED && (
              <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                <div className="bg-[#1e1f20] rounded-[28px] border border-[#3c4043] p-6 w-full max-w-md mx-4">
                  <h3 className="text-xl font-medium text-white mb-4 flex items-center gap-2">
                    <MapPin className="w-5 h-5 text-green-400" />
                    New ED in <span className="text-[#8ab4f8]">{showCreateED}</span>
                  </h3>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm text-[#9aa0a6] mb-2">ED Name</label>
                      <input
                        type="text"
                        value={newED.name}
                        onChange={(e) => {
                          const name = e.target.value;
                          setNewED({
                            ...newED,
                            name,
                            id: name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""),
                          });
                        }}
                        placeholder="Rochester"
                        className="w-full px-4 py-3 bg-[#131314] border border-[#3c4043] rounded-full text-white placeholder-[#5f6368] focus:outline-none focus:border-[#8ab4f8]"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-[#9aa0a6] mb-2">ID (URL-safe)</label>
                      <input
                        type="text"
                        value={newED.id}
                        onChange={(e) => setNewED({ ...newED, id: e.target.value })}
                        placeholder="rochester"
                        className="w-full px-4 py-3 bg-[#131314] border border-[#3c4043] rounded-full text-white placeholder-[#5f6368] focus:outline-none focus:border-[#8ab4f8]"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-[#9aa0a6] mb-2">Location</label>
                      <input
                        type="text"
                        value={newED.location}
                        onChange={(e) => setNewED({ ...newED, location: e.target.value })}
                        placeholder="Rochester, MN"
                        className="w-full px-4 py-3 bg-[#131314] border border-[#3c4043] rounded-full text-white placeholder-[#5f6368] focus:outline-none focus:border-[#8ab4f8]"
                      />
                    </div>
                  </div>
                  <div className="flex gap-3 mt-6">
                    <button
                      onClick={() => { setShowCreateED(null); setNewED({ id: "", name: "", location: "" }); }}
                      className="flex-1 px-4 py-3 bg-[#3c4043] text-white rounded-full hover:bg-[#5f6368] transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleCreateED}
                      disabled={!newED.id.trim() || !newED.name.trim() || creating}
                      className="flex-1 px-4 py-3 bg-[#8ab4f8] text-[#131314] rounded-full font-medium hover:bg-[#aecbfa] disabled:bg-[#3c4043] disabled:text-[#5f6368] disabled:cursor-not-allowed transition-colors"
                    >
                      {creating ? "Creating..." : "Create ED"}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* ===== Create Bundle Modal ===== */}
            {showCreateBundle && (
              <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                <div className="bg-[#1e1f20] rounded-[28px] border border-[#3c4043] p-6 w-full max-w-md mx-4">
                  <h3 className="text-xl font-medium text-white mb-4 flex items-center gap-2">
                    <FolderOpen className="w-5 h-5 text-yellow-500" />
                    New Bundle in <span className="text-[#8ab4f8]">{showCreateBundle.edId}</span>
                  </h3>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm text-[#9aa0a6] mb-2">Bundle Name</label>
                      <input
                        type="text"
                        value={newBundle.name}
                        onChange={(e) => {
                          const name = e.target.value;
                          setNewBundle({
                            ...newBundle,
                            name,
                            id: name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""),
                          });
                        }}
                        placeholder="ACLS"
                        className="w-full px-4 py-3 bg-[#131314] border border-[#3c4043] rounded-full text-white placeholder-[#5f6368] focus:outline-none focus:border-[#8ab4f8]"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-[#9aa0a6] mb-2">ID (URL-safe)</label>
                      <input
                        type="text"
                        value={newBundle.id}
                        onChange={(e) => setNewBundle({ ...newBundle, id: e.target.value })}
                        placeholder="acls"
                        className="w-full px-4 py-3 bg-[#131314] border border-[#3c4043] rounded-full text-white placeholder-[#5f6368] focus:outline-none focus:border-[#8ab4f8]"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-[#9aa0a6] mb-2">Description</label>
                      <input
                        type="text"
                        value={newBundle.description}
                        onChange={(e) => setNewBundle({ ...newBundle, description: e.target.value })}
                        placeholder="Advanced Cardiac Life Support algorithms"
                        className="w-full px-4 py-3 bg-[#131314] border border-[#3c4043] rounded-full text-white placeholder-[#5f6368] focus:outline-none focus:border-[#8ab4f8]"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-[#9aa0a6] mb-2">Color</label>
                      <div className="flex items-center gap-3">
                        <input
                          type="color"
                          value={newBundle.color}
                          onChange={(e) => setNewBundle({ ...newBundle, color: e.target.value })}
                          className="w-10 h-10 rounded-full border border-[#3c4043] bg-transparent cursor-pointer"
                        />
                        <span className="text-sm text-[#9aa0a6]">{newBundle.color}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-3 mt-6">
                    <button
                      onClick={() => { setShowCreateBundle(null); setNewBundle({ id: "", name: "", description: "", color: "#3B82F6" }); }}
                      className="flex-1 px-4 py-3 bg-[#3c4043] text-white rounded-full hover:bg-[#5f6368] transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleCreateBundle}
                      disabled={!newBundle.id.trim() || !newBundle.name.trim() || creating}
                      className="flex-1 px-4 py-3 bg-[#8ab4f8] text-[#131314] rounded-full font-medium hover:bg-[#aecbfa] disabled:bg-[#3c4043] disabled:text-[#5f6368] disabled:cursor-not-allowed transition-colors"
                    >
                      {creating ? "Creating..." : "Create Bundle"}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* ===== Access Requests View ===== */}
            {view === "requests" && (
              <div className="bg-[#1e1f20] rounded-[28px] border border-[#3c4043] overflow-hidden">
                <div className="flex items-center justify-between p-5 border-b border-[#3c4043]">
                  <h2 className="text-lg font-medium text-white flex items-center gap-2">
                    <UserCheck className="w-5 h-5 text-[#8ab4f8]" />
                    Access Requests
                    {unreadCount > 0 && (
                      <span className="text-xs bg-red-500 text-white px-2 py-0.5 rounded-full">
                        {unreadCount} new
                      </span>
                    )}
                  </h2>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => { fetchAccessRequests(); fetchNotifications(); }}
                      disabled={requestsLoading}
                      className="text-sm text-[#8ab4f8] hover:text-[#aecbfa] flex items-center gap-2 px-4 py-2 rounded-full hover:bg-[#8ab4f8]/10 transition-colors"
                    >
                      <RefreshCw className={`w-4 h-4 ${requestsLoading ? "animate-spin" : ""}`} />
                      Refresh
                    </button>
                  </div>
                </div>

                {/* Filter Tabs */}
                <div className="px-5 pt-4 flex gap-2">
                  {(["pending", "approved", "denied", "all"] as const).map((filter) => (
                    <button
                      key={filter}
                      onClick={() => setRequestsFilter(filter)}
                      className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors capitalize ${
                        requestsFilter === filter
                          ? filter === "pending" ? "bg-yellow-500/20 text-yellow-400"
                            : filter === "approved" ? "bg-green-500/20 text-green-400"
                            : filter === "denied" ? "bg-red-500/20 text-red-400"
                            : "bg-[#8ab4f8]/20 text-[#8ab4f8]"
                          : "text-[#9aa0a6] hover:text-white hover:bg-white/10"
                      }`}
                    >
                      {filter}
                    </button>
                  ))}
                </div>

                {/* Requests List */}
                {requestsLoading ? (
                  <div className="p-8 text-center">
                    <RefreshCw className="w-8 h-8 mx-auto text-[#5f6368] animate-spin mb-3" />
                    <p className="text-[#9aa0a6]">Loading requests...</p>
                  </div>
                ) : accessRequests.length === 0 ? (
                  <div className="p-8 text-center">
                    <UserCheck className="w-12 h-12 mx-auto text-[#5f6368] mb-3" />
                    <p className="text-[#9aa0a6]">No {requestsFilter !== "all" ? requestsFilter : ""} access requests</p>
                  </div>
                ) : (
                  <ul className="divide-y divide-[#3c4043]">
                    {accessRequests.map((req) => (
                      <li key={req.id} className="p-5 hover:bg-[#2c2d2e] transition-colors">
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex items-start gap-4 flex-1 min-w-0">
                            <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                              req.status === "pending" ? "bg-yellow-500/20" :
                              req.status === "approved" ? "bg-green-500/20" : "bg-red-500/20"
                            }`}>
                              {req.status === "pending" ? <Clock className="w-5 h-5 text-yellow-400" /> :
                               req.status === "approved" ? <Check className="w-5 h-5 text-green-400" /> :
                               <X className="w-5 h-5 text-red-400" />}
                            </div>
                            <div className="flex-1 min-w-0">
                              <h3 className="font-medium text-white">{req.name}</h3>
                              <div className="mt-1 space-y-1">
                                <div className="flex items-center gap-2 text-sm">
                                  <span className="text-[#9aa0a6]">Google:</span>
                                  <span className="text-[#e8eaed]">{req.google_email}</span>
                                </div>
                                <div className="flex items-center gap-2 text-sm">
                                  <span className="text-[#9aa0a6]">Mayo:</span>
                                  <span className="text-[#8ab4f8]">{req.mayo_email}</span>
                                </div>
                                <div className="text-xs text-[#5f6368]">
                                  Requested: {req.requested_at ? new Date(req.requested_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" }) : "Unknown"}
                                </div>
                                {req.reviewed_at && (
                                  <div className="text-xs text-[#5f6368]">
                                    Reviewed: {new Date(req.reviewed_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" })}
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>

                          {/* Actions */}
                          <div className="flex items-center gap-2 flex-shrink-0">
                            {req.status === "pending" ? (
                              <>
                                <button
                                  onClick={() => handleAccessRequestAction(req.id, "approve")}
                                  disabled={processingRequest === req.id}
                                  className="flex items-center gap-1.5 px-3 py-2 bg-green-500/20 text-green-400 hover:bg-green-500/30 rounded-full text-sm font-medium transition-colors disabled:opacity-50"
                                >
                                  <Check className="w-4 h-4" />
                                  Approve
                                </button>
                                <button
                                  onClick={() => handleAccessRequestAction(req.id, "deny")}
                                  disabled={processingRequest === req.id}
                                  className="flex items-center gap-1.5 px-3 py-2 bg-red-500/20 text-red-400 hover:bg-red-500/30 rounded-full text-sm font-medium transition-colors disabled:opacity-50"
                                >
                                  <X className="w-4 h-4" />
                                  Deny
                                </button>
                              </>
                            ) : (
                              <span className={`text-xs px-2 py-1 rounded-full ${
                                req.status === "approved"
                                  ? "bg-green-500/20 text-green-400"
                                  : "bg-red-500/20 text-red-400"
                              }`}>
                                {req.status}
                              </span>
                            )}
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {/* ===== Admins View ===== */}
            {view === "admins" && (
              <div className="bg-[#1e1f20] rounded-[28px] border border-[#3c4043] overflow-hidden">
                <div className="flex items-center justify-between p-5 border-b border-[#3c4043]">
                  <h2 className="text-lg font-medium text-white flex items-center gap-2">
                    <Shield className="w-5 h-5 text-[#8ab4f8]" />
                    Admin Users
                  </h2>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={fetchAdmins}
                      disabled={loading}
                      className="text-sm text-[#8ab4f8] hover:text-[#aecbfa] flex items-center gap-2 px-4 py-2 rounded-full hover:bg-[#8ab4f8]/10 transition-colors"
                    >
                      <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                      Refresh
                    </button>
                    <button
                      onClick={() => setShowAddAdmin(true)}
                      className="bg-[#8ab4f8] text-[#131314] px-4 py-2 rounded-full text-sm font-medium hover:bg-[#aecbfa] transition-colors flex items-center gap-2"
                    >
                      <Plus className="w-4 h-4" />
                      Add Admin
                    </button>
                  </div>
                </div>

                {/* Add Admin Modal */}
                {showAddAdmin && (
                  <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-[#1e1f20] rounded-[28px] border border-[#3c4043] p-6 w-full max-w-md mx-4">
                      <h3 className="text-xl font-medium text-white mb-4">Add New Admin</h3>
                      
                      <div className="space-y-4">
                        <div>
                          <label className="block text-sm text-[#9aa0a6] mb-2">Select User</label>
                          <div className="relative">
                            <input
                              type="text"
                              value={newAdminEmail || userSearch}
                              onChange={(e) => {
                                setUserSearch(e.target.value);
                                setNewAdminEmail("");
                                setShowUserDropdown(true);
                              }}
                              onFocus={() => setShowUserDropdown(true)}
                              placeholder="Search users by email..."
                              className="w-full px-4 py-3 bg-[#131314] border border-[#3c4043] rounded-full text-white placeholder-[#5f6368] focus:outline-none focus:border-[#8ab4f8] transition-colors"
                            />
                            {newAdminEmail && (
                              <button
                                onClick={() => {
                                  setNewAdminEmail("");
                                  setUserSearch("");
                                }}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#9aa0a6] hover:text-white"
                              >
                                <X className="w-4 h-4" />
                              </button>
                            )}
                            {showUserDropdown && !newAdminEmail && (
                              <div className="absolute z-10 mt-2 w-full bg-[#1e1f20] border border-[#3c4043] rounded-2xl shadow-xl max-h-60 overflow-y-auto">
                                {allUsers
                                  .filter(u => {
                                    const search = userSearch.toLowerCase();
                                    return u.email.toLowerCase().includes(search);
                                  })
                                  .sort((a, b) => {
                                    // Sort: users first, then admins, then super_admins
                                    const roleOrder: Record<string, number> = { user: 0, admin: 1, super_admin: 2 };
                                    return (roleOrder[a.role] ?? 0) - (roleOrder[b.role] ?? 0);
                                  })
                                  .map((u) => (
                                    <button
                                      key={u.uid}
                                      onClick={() => {
                                        setNewAdminEmail(u.email);
                                        setUserSearch("");
                                        setShowUserDropdown(false);
                                        // Pre-fill enterprise from their existing data
                                        if (u.enterpriseId) {
                                          setNewAdminEnterprise(u.enterpriseId);
                                        }
                                      }}
                                      className="w-full px-4 py-3 flex items-center justify-between hover:bg-[#2c2d2e] transition-colors first:rounded-t-2xl last:rounded-b-2xl"
                                    >
                                      <div className="flex items-center gap-3">
                                        <div className="w-8 h-8 rounded-full bg-[#8ab4f8]/20 flex items-center justify-center flex-shrink-0">
                                          <Mail className="w-4 h-4 text-[#8ab4f8]" />
                                        </div>
                                        <div className="text-left">
                                          <p className="text-sm text-white">{u.email}</p>
                                          {u.enterpriseId && (
                                            <p className="text-xs text-[#5f6368]">{u.enterpriseId}</p>
                                          )}
                                        </div>
                                      </div>
                                      <span className={`text-xs px-2 py-1 rounded-full flex-shrink-0 ${
                                        u.role === "super_admin"
                                          ? "bg-yellow-500/20 text-yellow-400"
                                          : u.role === "admin"
                                          ? "bg-blue-500/20 text-blue-400"
                                          : "bg-green-500/20 text-green-400"
                                      }`}>
                                        {u.role}
                                      </span>
                                    </button>
                                  ))}
                                {allUsers.filter(u => u.email.toLowerCase().includes(userSearch.toLowerCase())).length === 0 && (
                                  <div className="px-4 py-3 text-sm text-[#5f6368]">No users found</div>
                                )}
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Role Selector */}
                        {isSuperAdmin && (
                          <div>
                            <label className="block text-sm text-[#9aa0a6] mb-2">Role</label>
                            <div className="flex gap-2">
                              <button
                                onClick={() => setNewAdminRole("admin")}
                                className={`flex-1 px-4 py-3 rounded-full text-sm font-medium transition-colors flex items-center justify-center gap-2 ${
                                  newAdminRole === "admin"
                                    ? "bg-[#8ab4f8] text-[#131314]"
                                    : "bg-[#131314] border border-[#3c4043] text-[#9aa0a6] hover:border-[#8ab4f8]"
                                }`}
                              >
                                <Shield className="w-4 h-4" />
                                Admin
                              </button>
                              <button
                                onClick={() => setNewAdminRole("super_admin")}
                                className={`flex-1 px-4 py-3 rounded-full text-sm font-medium transition-colors flex items-center justify-center gap-2 ${
                                  newAdminRole === "super_admin"
                                    ? "bg-yellow-500 text-[#131314]"
                                    : "bg-[#131314] border border-[#3c4043] text-[#9aa0a6] hover:border-yellow-500"
                                }`}
                              >
                                <Crown className="w-4 h-4" />
                                Super Admin
                              </button>
                            </div>
                            {newAdminRole === "super_admin" && (
                              <p className="text-xs text-yellow-400/70 mt-2 px-1">
                                Super admins have access to all enterprises and full system control.
                              </p>
                            )}
                          </div>
                        )}

                        {/* Enterprise Selector (only for admin role) */}
                        {newAdminRole === "admin" && isSuperAdmin && (
                          <div>
                            <label className="block text-sm text-[#9aa0a6] mb-2">Enterprise</label>
                            <select
                              value={newAdminEnterprise}
                              onChange={(e) => {
                                setNewAdminEnterprise(e.target.value);
                                setNewAdminBundles([]);
                              }}
                              className="w-full px-4 py-3 bg-[#131314] border border-[#3c4043] rounded-full text-white focus:outline-none focus:border-[#8ab4f8] transition-colors appearance-none cursor-pointer"
                            >
                              <option value="">Select enterprise...</option>
                              {enterprises.map((ent) => (
                                <option key={ent.id} value={ent.id}>{ent.name}</option>
                              ))}
                            </select>
                          </div>
                        )}

                        {/* ED Access (only for admin role) */}
                        {newAdminRole === "admin" && (
                          <div>
                            <label className="block text-sm text-[#9aa0a6] mb-2">ED Access</label>
                            <div className="space-y-2">
                              {(isSuperAdmin
                                ? (enterprises.find(e => e.id === newAdminEnterprise)?.eds || []).map(ed => ed.id)
                                : availableEDs
                              ).map((ed) => (
                                <label key={ed} className="flex items-center gap-3 px-4 py-2 bg-[#131314] rounded-full cursor-pointer hover:bg-[#2c2d2e] transition-colors">
                                  <input
                                    type="checkbox"
                                    checked={newAdminBundles.includes(ed)}
                                    onChange={() => toggleEDSelection(ed)}
                                    className="w-4 h-4"
                                  />
                                  <span className="text-white">{ed}</span>
                                </label>
                              ))}
                              {isSuperAdmin && !newAdminEnterprise && (
                                <p className="text-sm text-[#5f6368] px-1">Select an enterprise first</p>
                              )}
                            </div>
                          </div>
                        )}
                      </div>

                      <div className="flex gap-3 mt-6">
                        <button
                          onClick={() => {
                            setShowAddAdmin(false);
                            setNewAdminEmail("");
                            setNewAdminRole("admin");
                            setNewAdminEnterprise("");
                            setNewAdminBundles([]);
                            setUserSearch("");
                            setShowUserDropdown(false);
                          }}
                          className="flex-1 px-4 py-3 bg-[#3c4043] text-white rounded-full hover:bg-[#5f6368] transition-colors"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={handleAddAdmin}
                          disabled={!newAdminEmail.trim() || (newAdminRole === "admin" && !newAdminEnterprise && !userProfile?.enterpriseId)}
                          className="flex-1 px-4 py-3 bg-[#8ab4f8] text-[#131314] rounded-full font-medium hover:bg-[#aecbfa] disabled:bg-[#3c4043] disabled:text-[#5f6368] disabled:cursor-not-allowed transition-colors"
                        >
                          {newAdminRole === "super_admin" ? "Add Super Admin" : "Add Admin"}
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Admins List */}
                {admins.length === 0 ? (
                  <div className="p-8 text-center">
                    <Users className="w-12 h-12 mx-auto text-[#5f6368] mb-3" />
                    <p className="text-[#9aa0a6]">No admins yet</p>
                    <p className="text-sm text-[#5f6368]">Add admins to manage protocols</p>
                  </div>
                ) : (
                  <div>
                    {/* Table header */}
                    <div className="grid grid-cols-[1fr_180px_48px] items-center px-5 py-3 border-b border-[#3c4043] text-xs text-[#9aa0a6] uppercase tracking-wider">
                      <span>User</span>
                      <span className="text-center">Mayo Protocol Access</span>
                      <span></span>
                    </div>
                    <ul className="divide-y divide-[#3c4043]">
                      {admins.map((admin) => (
                        <li key={admin.uid} className="grid grid-cols-[1fr_180px_48px] items-center px-5 py-4 hover:bg-[#2c2d2e] transition-colors">
                          {/* User info */}
                          <div className="flex items-center gap-4">
                            <div className="w-10 h-10 rounded-full bg-[#8ab4f8]/20 flex items-center justify-center shrink-0">
                              <Mail className="w-5 h-5 text-[#8ab4f8]" />
                            </div>
                            <div className="min-w-0">
                              <h3 className="font-medium text-white truncate">{admin.email}</h3>
                              <div className="flex items-center gap-2 mt-1">
                                <span className={`text-xs px-2 py-0.5 rounded-full ${
                                  admin.role === "super_admin" 
                                    ? "bg-yellow-500/20 text-yellow-400"
                                    : admin.role === "admin"
                                    ? "bg-blue-500/20 text-blue-400"
                                    : "bg-green-500/20 text-green-400"
                                }`}>
                                  {admin.role}
                                </span>
                                {admin.edAccess && admin.edAccess.length > 0 && (
                                  <span className="text-xs text-[#9aa0a6]">
                                    {admin.edAccess.length} ED(s)
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                          {/* Mayo Protocol Access column */}
                          <div className="flex justify-center">
                            {admin.email?.endsWith("@mayo.edu") ? (
                              <span className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1 rounded-full bg-emerald-500/15 text-emerald-400">
                                <Check className="w-3.5 h-3.5" /> Yes
                              </span>
                            ) : admin.enterpriseId ? (
                              <span className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1 rounded-full bg-amber-500/15 text-amber-400">
                                <Check className="w-3.5 h-3.5" /> Approved (Gmail)
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1 rounded-full bg-red-500/15 text-red-400">
                                <X className="w-3.5 h-3.5" /> No
                              </span>
                            )}
                          </div>
                          {/* Actions */}
                          <div className="flex justify-end">
                            {admin.role !== "super_admin" && (
                              <button
                                onClick={() => handleRemoveAdmin(admin.uid)}
                                className="p-2 text-[#9aa0a6] hover:text-red-400 hover:bg-red-400/10 rounded-full transition-colors"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            )}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* ===== Analytics View ===== */}
            {view === "analytics" && (
              <div className="space-y-6">
                {/* Range Selector */}
                <div className="flex items-center gap-2">
                  {[
                    { label: "Today", value: "today" },
                    { label: "7 Days", value: "7d" },
                    { label: "30 Days", value: "30d" },
                    { label: "90 Days", value: "90d" },
                    { label: "1 Year", value: "1y" },
                    { label: "All Time", value: "all" },
                  ].map((r) => (
                    <button
                      key={r.value}
                      onClick={() => setAnalyticsRange(r.value)}
                      className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                        analyticsRange === r.value
                          ? "bg-[#8ab4f8] text-[#131314]"
                          : "text-[#9aa0a6] hover:text-white hover:bg-white/10 border border-[#3c4043]"
                      }`}
                    >
                      {r.label}
                    </button>
                  ))}
                  <button
                    onClick={() => fetchAnalytics(analyticsRange)}
                    disabled={analyticsLoading}
                    className="ml-auto p-2 text-[#9aa0a6] hover:text-white hover:bg-white/10 rounded-full transition-colors"
                  >
                    <RefreshCw className={`w-4 h-4 ${analyticsLoading ? "animate-spin" : ""}`} />
                  </button>
                </div>

                {analyticsLoading && !analyticsSummary ? (
                  <div className="flex items-center justify-center py-20">
                    <RefreshCw className="w-8 h-8 animate-spin text-[#8ab4f8]" />
                  </div>
                ) : (
                  <>
                    {/* Stat Cards */}
                    {analyticsSummary && (
                      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                        {[
                          {
                            label: "Active Users",
                            value: analyticsSummary.users,
                            change: analyticsSummary.usersChange,
                            icon: <Users className="w-5 h-5 text-[#8ab4f8]" />,
                          },
                          {
                            label: "Total Queries",
                            value: analyticsSummary.queries,
                            change: analyticsSummary.queriesChange,
                            icon: <Search className="w-5 h-5 text-purple-400" />,
                          },
                          {
                            label: "Queries / User",
                            value: analyticsSummary.avgPerUser,
                            change: 0,
                            icon: <Activity className="w-5 h-5 text-cyan-400" />,
                            decimals: 1,
                          },
                          {
                            label: "Feedback Score",
                            value: analyticsSummary.feedbackScore,
                            change: 0,
                            icon: <ThumbsUp className="w-5 h-5 text-emerald-400" />,
                            suffix: "%",
                            detail: `${analyticsSummary.feedbackUp}↑ ${analyticsSummary.feedbackDown}↓`,
                          },
                        ].map((card) => {
                          const isPositive = card.change >= 0;
                          return (
                            <div
                              key={card.label}
                              className="bg-[#1e1f20] rounded-2xl border border-[#3c4043] p-5"
                            >
                              <div className="flex items-center justify-between mb-3">
                                <span className="text-xs text-[#9aa0a6] uppercase tracking-wider">{card.label}</span>
                                {card.icon}
                              </div>
                              <div className="flex items-end gap-2">
                                <span className="text-3xl font-semibold text-white font-[family-name:var(--font-mono)]">
                                  {card.decimals
                                    ? card.value.toFixed(card.decimals)
                                    : card.value.toLocaleString()}
                                  {card.suffix || ""}
                                </span>
                                {analyticsRange !== "all" && card.change !== 0 && (
                                  <span
                                    className={`text-xs font-medium flex items-center gap-0.5 mb-1 ${
                                      isPositive ? "text-emerald-400" : "text-red-400"
                                    }`}
                                  >
                                    {isPositive ? (
                                      <TrendingUp className="w-3 h-3" />
                                    ) : (
                                      <TrendingDown className="w-3 h-3" />
                                    )}
                                    {Math.abs(card.change).toFixed(0)}%
                                  </span>
                                )}
                              </div>
                              {card.detail && (
                                <span className="text-xs text-[#9aa0a6] mt-1 block">{card.detail}</span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {/* Trend Chart */}
                    {analyticsTrend.length > 0 && (
                      <div className="bg-[#1e1f20] rounded-2xl border border-[#3c4043] p-5">
                        <h3 className="text-sm font-medium text-white mb-4 flex items-center gap-2">
                          <Activity className="w-4 h-4 text-[#8ab4f8]" />
                          Usage Trend
                        </h3>
                        <div className="h-72">
                          <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={analyticsTrend}>
                              <CartesianGrid strokeDasharray="3 3" stroke="#3c4043" />
                              <XAxis
                                dataKey="period"
                                stroke="#9aa0a6"
                                tick={{ fontSize: 11 }}
                                tickFormatter={(v) => {
                                  if (v.length === 10) return v.slice(5); // MM-DD
                                  return v;
                                }}
                              />
                              <YAxis stroke="#9aa0a6" tick={{ fontSize: 11 }} />
                              <Tooltip
                                contentStyle={{
                                  backgroundColor: "#1e1f20",
                                  border: "1px solid #3c4043",
                                  borderRadius: "12px",
                                  color: "#fff",
                                  fontSize: 12,
                                }}
                              />
                              <Legend />
                              <Line type="monotone" dataKey="queries" stroke="#a78bfa" strokeWidth={2} dot={false} name="Queries" />
                              <Line type="monotone" dataKey="users" stroke="#8ab4f8" strokeWidth={2} dot={false} name="Users" />
                            </LineChart>
                          </ResponsiveContainer>
                        </div>
                      </div>
                    )}

                    {/* Two-column: Users & Protocol Clicks */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      {/* Users Table */}
                      <div className="bg-[#1e1f20] rounded-2xl border border-[#3c4043] overflow-hidden">
                        <div className="p-4 border-b border-[#3c4043]">
                          <h3 className="text-sm font-medium text-white flex items-center gap-2">
                            <Users className="w-4 h-4 text-[#8ab4f8]" />
                            Top Users
                          </h3>
                        </div>
                        {analyticsUsers.length === 0 ? (
                          <div className="p-8 text-center text-[#9aa0a6] text-sm">No user data yet</div>
                        ) : (
                          <div className="divide-y divide-[#3c4043] max-h-80 overflow-auto">
                            {/* Header row */}
                            <div className="grid grid-cols-[1fr_60px_80px] gap-2 px-4 py-2 text-xs text-[#9aa0a6] uppercase tracking-wider">
                              <span>Email</span>
                              <span className="text-right">Queries</span>
                              <span className="text-right">Last Active</span>
                            </div>
                            {analyticsUsers.slice(0, 20).map((u) => (
                              <div key={u.email} className="grid grid-cols-[1fr_60px_80px] gap-2 px-4 py-3 hover:bg-[#2c2d2e] transition-colors items-center">
                                <span className="text-sm text-white truncate">{u.email}</span>
                                <span className="text-sm text-[#8ab4f8] text-right font-[family-name:var(--font-mono)]">{u.queries}</span>
                                <span className="text-xs text-[#9aa0a6] text-right">{u.lastActive}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Protocol Clicks */}
                      <div className="bg-[#1e1f20] rounded-2xl border border-[#3c4043] overflow-hidden">
                        <div className="p-4 border-b border-[#3c4043]">
                          <h3 className="text-sm font-medium text-white flex items-center gap-2">
                            <MousePointerClick className="w-4 h-4 text-purple-400" />
                            Top Protocol Clicks
                          </h3>
                        </div>
                        {analyticsProtocolClicks.length === 0 ? (
                          <div className="p-8 text-center text-[#9aa0a6] text-sm">No click data yet</div>
                        ) : (
                          <div className="divide-y divide-[#3c4043] max-h-80 overflow-auto">
                            {analyticsProtocolClicks.map((p, i) => (
                              <div key={p.protocolId} className="flex items-center gap-3 px-4 py-3 hover:bg-[#2c2d2e] transition-colors">
                                <span className="text-xs text-[#9aa0a6] w-5 text-right">{i + 1}.</span>
                                <span className="text-sm text-white flex-1 truncate">{p.title}</span>
                                <span className="text-sm text-purple-400 font-[family-name:var(--font-mono)]">{p.clicks}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Feedback Feed */}
                    <div className="bg-[#1e1f20] rounded-2xl border border-[#3c4043] overflow-hidden">
                      <div className="flex items-center justify-between p-4 border-b border-[#3c4043]">
                        <h3 className="text-sm font-medium text-white flex items-center gap-2">
                          <ThumbsUp className="w-4 h-4 text-emerald-400" />
                          Feedback ({analyticsFeedback.total})
                        </h3>
                        <div className="flex gap-1">
                          {(["all", "up", "down"] as const).map((f) => (
                            <button
                              key={f}
                              onClick={() => { setFeedbackFilter(f); setFeedbackPage(1); }}
                              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                                feedbackFilter === f
                                  ? "bg-[#8ab4f8] text-[#131314]"
                                  : "text-[#9aa0a6] hover:text-white hover:bg-white/10"
                              }`}
                            >
                              {f === "all" ? "All" : f === "up" ? "👍 Up" : "👎 Down"}
                            </button>
                          ))}
                        </div>
                      </div>
                      {analyticsFeedback.feedback.length === 0 ? (
                        <div className="p-8 text-center text-[#9aa0a6] text-sm">No feedback yet</div>
                      ) : (
                        <div className="divide-y divide-[#3c4043]">
                          {analyticsFeedback.feedback.map((fb: { id: string; query: string; rating: string; reasons: string[]; comment: string; user_email: string; date: string }) => (
                            <div
                              key={fb.id}
                              className={`px-5 py-4 border-l-4 ${
                                fb.rating === "up"
                                  ? "border-l-emerald-500/60"
                                  : "border-l-red-500/60"
                              }`}
                            >
                              <div className="flex items-start justify-between gap-4">
                                <div className="flex-1 min-w-0">
                                  <p className="text-sm text-white mb-1 line-clamp-2">
                                    <span className="text-[#9aa0a6]">Q:</span> {fb.query}
                                  </p>
                                  {fb.reasons && fb.reasons.length > 0 && (
                                    <div className="flex flex-wrap gap-1 mb-1">
                                      {fb.reasons.map((r) => (
                                        <span
                                          key={r}
                                          className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 text-[#9aa0a6]"
                                        >
                                          {r}
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                  {fb.comment && (
                                    <p className="text-xs text-[#9aa0a6] italic mt-1">&ldquo;{fb.comment}&rdquo;</p>
                                  )}
                                </div>
                                <div className="text-right shrink-0">
                                  <span className="text-lg">{fb.rating === "up" ? "👍" : "👎"}</span>
                                  <p className="text-[10px] text-[#9aa0a6] mt-0.5">{fb.user_email}</p>
                                  <p className="text-[10px] text-[#5f6368]">{fb.date}</p>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                      {/* Pagination */}
                      {analyticsFeedback.total > analyticsFeedback.pageSize && (
                        <div className="flex items-center justify-center gap-2 p-3 border-t border-[#3c4043]">
                          <button
                            onClick={() => setFeedbackPage((p) => Math.max(1, p - 1))}
                            disabled={feedbackPage <= 1}
                            className="px-3 py-1 text-xs rounded-full text-[#9aa0a6] hover:text-white hover:bg-white/10 disabled:opacity-30 transition-colors"
                          >
                            ← Prev
                          </button>
                          <span className="text-xs text-[#9aa0a6]">
                            Page {analyticsFeedback.page} of {analyticsFeedback.totalPages}
                          </span>
                          <button
                            onClick={() => setFeedbackPage((p) => p + 1)}
                            disabled={feedbackPage >= analyticsFeedback.totalPages}
                            className="px-3 py-1 text-xs rounded-full text-[#9aa0a6] hover:text-white hover:bg-white/10 disabled:opacity-30 transition-colors"
                          >
                            Next →
                          </button>
                        </div>
                      )}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

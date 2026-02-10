"use client";

import { useState, useEffect } from "react";
import { Users, Building2, FolderOpen, FileText, Shield, Crown, Mail, Plus, Trash2, RefreshCw, ChevronDown, ChevronRight, ArrowLeft, Check, X, Database, MapPin, Palette } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://em-protocol-api-930035889332.us-central1.run.app";

interface Admin {
  uid: string;
  email: string;
  role: string;
  edAccess: string[];
  enterpriseId: string;
  createdAt: string;
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
  
  const [view, setView] = useState<"admins" | "hierarchy">("hierarchy");
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

  // Create modals
  const [showCreateEnterprise, setShowCreateEnterprise] = useState(false);
  const [showCreateED, setShowCreateED] = useState<string | null>(null); // enterprise_id or null
  const [showCreateBundle, setShowCreateBundle] = useState<{ enterpriseId: string; edId: string } | null>(null);

  // Form state
  const [newEnterprise, setNewEnterprise] = useState({ id: "", name: "", domains: "" });
  const [newED, setNewED] = useState({ id: "", name: "", location: "" });
  const [newBundle, setNewBundle] = useState({ id: "", name: "", description: "", color: "#3B82F6" });
  const [creating, setCreating] = useState(false);

  // Check if user is owner or super_admin
  useEffect(() => {
    if (!authLoading && (!user || (userProfile?.role !== "super_admin" && userProfile?.role !== "admin"))) {
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
    if (userProfile?.role === "super_admin" || userProfile?.role === "admin") {
      fetchAdmins();
      fetchEnterprises();
    }
  }, [userProfile]);

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
        fetchAdmins();
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

  if (authLoading || !userProfile || (userProfile.role !== "super_admin" && userProfile.role !== "admin")) {
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
                          <label className="block text-sm text-[#9aa0a6] mb-2">Email Address</label>
                          <input
                            type="email"
                            value={newAdminEmail}
                            onChange={(e) => setNewAdminEmail(e.target.value)}
                            placeholder="admin@example.com"
                            className="w-full px-4 py-3 bg-[#131314] border border-[#3c4043] rounded-full text-white placeholder-[#5f6368] focus:outline-none focus:border-[#8ab4f8] transition-colors"
                          />
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
                  <ul className="divide-y divide-[#3c4043]">
                    {admins.map((admin) => (
                      <li key={admin.uid} className="p-5 hover:bg-[#2c2d2e] transition-colors">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            <div className="w-10 h-10 rounded-full bg-[#8ab4f8]/20 flex items-center justify-center">
                              <Mail className="w-5 h-5 text-[#8ab4f8]" />
                            </div>
                            <div>
                              <h3 className="font-medium text-white">{admin.email}</h3>
                              <div className="flex items-center gap-2 mt-1">
                                <span className={`text-xs px-2 py-1 rounded-full ${
                                  admin.role === "super_admin" 
                                    ? "bg-yellow-500/20 text-yellow-400"
                                    : "bg-blue-500/20 text-blue-400"
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
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

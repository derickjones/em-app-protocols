"use client";

import { useState, useEffect } from "react";
import { Users, Building2, FolderOpen, FileText, Shield, Crown, Mail, Plus, Trash2, RefreshCw, ChevronDown, ChevronRight, ArrowLeft, Check, X, Database } from "lucide-react";
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

interface Protocol {
  protocol_id: string;
  org_id: string;
  page_count: number;
  char_count: number;
  image_count: number;
  processed_at: string;
}

interface HospitalData {
  [bundle: string]: Protocol[];
}

interface AllHospitals {
  [hospital: string]: HospitalData;
}

export default function OwnerDashboard() {
  const { user, userProfile, loading: authLoading } = useAuth();
  const router = useRouter();
  
  const [view, setView] = useState<"admins" | "protocols">("admins");
  const [admins, setAdmins] = useState<Admin[]>([]);
  const [allHospitals, setAllHospitals] = useState<AllHospitals>({});
  const [expandedHospitals, setExpandedHospitals] = useState<Set<string>>(new Set());
  const [expandedBundles, setExpandedBundles] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [showAddAdmin, setShowAddAdmin] = useState(false);
  const [newAdminEmail, setNewAdminEmail] = useState("");
  const [newAdminBundles, setNewAdminBundles] = useState<string[]>([]);
  const [availableBundles, setAvailableBundles] = useState<string[]>([]);

  // Check if user is owner or super_admin
  useEffect(() => {
    if (!authLoading && (!user || (userProfile?.role !== "super_admin" && userProfile?.role !== "admin"))) {
      router.push("/");
    }
  }, [user, userProfile, authLoading, router]);

  // Fetch admins for the enterprise
  const fetchAdmins = async () => {
    if (!userProfile?.enterpriseId) return;
    
    setLoading(true);
    try {
      const token = await user?.getIdToken();
      const res = await fetch(`${API_URL}/admin/users?enterprise_id=${userProfile.enterpriseId}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
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

  // Fetch all enterprises and protocols
  const fetchHospitals = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/enterprises`);
      if (res.ok) {
        const data = await res.json();
        const hospitals = data.hospitals || {};
        setAllHospitals(hospitals);
        
        // Extract available EDs for this enterprise
        if (userProfile?.enterpriseId && hospitals[userProfile.enterpriseId]) {
          setAvailableBundles(Object.keys(hospitals[userProfile.enterpriseId]));
        }
      }
    } catch (err) {
      console.error("Failed to fetch hospitals:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (userProfile?.role === "super_admin" || userProfile?.role === "admin") {
      fetchAdmins();
      fetchHospitals();
    }
  }, [userProfile]);

  const handleAddAdmin = async () => {
    if (!newAdminEmail.trim() || !userProfile?.enterpriseId) return;
    
    try {
      const token = await user?.getIdToken();
      const res = await fetch(`${API_URL}/admin/users`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          email: newAdminEmail,
          enterprise_id: userProfile.enterpriseId,
          role: "admin",
          ed_access: newAdminBundles,
        }),
      });
      
      if (res.ok) {
        setShowAddAdmin(false);
        setNewAdminEmail("");
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
        headers: {
          Authorization: `Bearer ${token}`,
        },
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

  const toggleHospital = (hospital: string) => {
    const newExpanded = new Set(expandedHospitals);
    if (newExpanded.has(hospital)) {
      newExpanded.delete(hospital);
    } else {
      newExpanded.add(hospital);
    }
    setExpandedHospitals(newExpanded);
  };

  const toggleBundle = (key: string) => {
    const newExpanded = new Set(expandedBundles);
    if (newExpanded.has(key)) {
      newExpanded.delete(key);
    } else {
      newExpanded.add(key);
    }
    setExpandedBundles(newExpanded);
  };

  const toggleBundleSelection = (bundle: string) => {
    setNewAdminBundles(prev => 
      prev.includes(bundle) 
        ? prev.filter(b => b !== bundle)
        : [...prev, bundle]
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
            <span className="text-sm text-[#8ab4f8]">{userProfile.enterpriseName || userProfile.enterpriseId}</span>
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
              onClick={() => setView("protocols")}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-colors flex items-center gap-2 ${
                view === "protocols"
                  ? "bg-[#8ab4f8] text-[#131314]"
                  : "text-[#9aa0a6] hover:text-white hover:bg-white/10"
              }`}
            >
              <Database className="w-4 h-4" />
              Protocols & Bundles
            </button>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 overflow-auto p-6">
          <div className="max-w-5xl mx-auto space-y-6">
            
            {/* Admins View */}
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

                        <div>
                          <label className="block text-sm text-[#9aa0a6] mb-2">Bundle Access</label>
                          <div className="space-y-2">
                            {availableBundles.map((bundle) => (
                              <label key={bundle} className="flex items-center gap-3 px-4 py-2 bg-[#131314] rounded-full cursor-pointer hover:bg-[#2c2d2e] transition-colors">
                                <input
                                  type="checkbox"
                                  checked={newAdminBundles.includes(bundle)}
                                  onChange={() => toggleBundleSelection(bundle)}
                                  className="w-4 h-4"
                                />
                                <span className="text-white">{bundle}</span>
                              </label>
                            ))}
                          </div>
                        </div>
                      </div>

                      <div className="flex gap-3 mt-6">
                        <button
                          onClick={() => {
                            setShowAddAdmin(false);
                            setNewAdminEmail("");
                            setNewAdminBundles([]);
                          }}
                          className="flex-1 px-4 py-3 bg-[#3c4043] text-white rounded-full hover:bg-[#5f6368] transition-colors"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={handleAddAdmin}
                          disabled={!newAdminEmail.trim()}
                          className="flex-1 px-4 py-3 bg-[#8ab4f8] text-[#131314] rounded-full font-medium hover:bg-[#aecbfa] disabled:bg-[#3c4043] disabled:text-[#5f6368] disabled:cursor-not-allowed transition-colors"
                        >
                          Add Admin
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

            {/* Protocols View */}
            {view === "protocols" && (
              <div className="bg-[#1e1f20] rounded-[28px] border border-[#3c4043] overflow-hidden">
                <div className="flex items-center justify-between p-5 border-b border-[#3c4043]">
                  <h2 className="text-lg font-medium text-white flex items-center gap-2">
                    <Building2 className="w-5 h-5 text-[#8ab4f8]" />
                    All Protocols & Bundles
                  </h2>
                  <button
                    onClick={fetchHospitals}
                    disabled={loading}
                    className="text-sm text-[#8ab4f8] hover:text-[#aecbfa] flex items-center gap-2 px-4 py-2 rounded-full hover:bg-[#8ab4f8]/10 transition-colors"
                  >
                    <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                    Refresh
                  </button>
                </div>

                {Object.keys(allHospitals).length === 0 ? (
                  <div className="p-8 text-center">
                    <Building2 className="w-12 h-12 mx-auto text-[#5f6368] mb-3" />
                    <p className="text-[#9aa0a6]">No protocols found</p>
                    <p className="text-sm text-[#5f6368]">Upload protocols to see them here</p>
                  </div>
                ) : (
                  <div className="divide-y divide-[#3c4043]">
                    {Object.entries(allHospitals)
                      .filter(([hospital]) => !userProfile.enterpriseId || hospital === userProfile.enterpriseId)
                      .sort()
                      .map(([hospital, bundles]) => (
                        <div key={hospital}>
                          <button
                            onClick={() => toggleHospital(hospital)}
                            className="w-full px-5 py-4 flex items-center gap-3 hover:bg-[#2c2d2e] transition-colors"
                          >
                            {expandedHospitals.has(hospital) ? (
                              <ChevronDown className="w-4 h-4 text-[#9aa0a6]" />
                            ) : (
                              <ChevronRight className="w-4 h-4 text-[#9aa0a6]" />
                            )}
                            <Building2 className="w-5 h-5 text-[#8ab4f8]" />
                            <span className="font-medium text-white">{hospital}</span>
                            <span className="text-xs text-[#5f6368] ml-auto">
                              {Object.keys(bundles).length} bundle(s)
                            </span>
                          </button>

                          {expandedHospitals.has(hospital) && (
                            <div className="bg-[#1a1a1b]">
                              {Object.entries(bundles).sort().map(([bundle, bundleProtocols]) => {
                                const bundleKey = `${hospital}/${bundle}`;
                                return (
                                  <div key={bundleKey}>
                                    <button
                                      onClick={() => toggleBundle(bundleKey)}
                                      className="w-full pl-12 pr-5 py-3 flex items-center gap-3 hover:bg-[#2c2d2e] transition-colors"
                                    >
                                      {expandedBundles.has(bundleKey) ? (
                                        <ChevronDown className="w-4 h-4 text-[#9aa0a6]" />
                                      ) : (
                                        <ChevronRight className="w-4 h-4 text-[#9aa0a6]" />
                                      )}
                                      <FolderOpen className="w-4 h-4 text-yellow-500" />
                                      <span className="text-[#e8eaed]">{bundle}</span>
                                      <span className="text-xs text-[#5f6368] ml-auto">
                                        {bundleProtocols.length} protocol(s)
                                      </span>
                                    </button>

                                    {expandedBundles.has(bundleKey) && (
                                      <ul className="bg-[#131314]">
                                        {bundleProtocols.map((protocol) => (
                                          <li
                                            key={protocol.protocol_id}
                                            className="pl-20 pr-5 py-3 flex items-center justify-between hover:bg-[#2c2d2e] transition-colors"
                                          >
                                            <div className="flex items-center gap-3">
                                              <FileText className="w-4 h-4 text-[#5f6368]" />
                                              <div>
                                                <span className="text-[#e8eaed]">
                                                  {protocol.protocol_id.replace(/_/g, " ")}
                                                </span>
                                                <p className="text-xs text-[#5f6368]">
                                                  {protocol.page_count} pages • {protocol.image_count} images • {protocol.char_count?.toLocaleString() || 0} chars
                                                </p>
                                              </div>
                                            </div>
                                            <span className="text-xs text-[#5f6368]">
                                              {new Date(protocol.processed_at).toLocaleDateString()}
                                            </span>
                                          </li>
                                        ))}
                                      </ul>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

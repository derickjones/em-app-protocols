"use client";

import { useState, useEffect, useCallback } from "react";
import { Upload, FileText, Trash2, RefreshCw, CheckCircle, AlertCircle, ArrowLeft, Menu, SquarePen, Shield, ChevronDown, ChevronRight, Building2, FolderOpen, Database, MapPin } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://em-protocol-api-930035889332.us-central1.run.app";

interface Protocol {
  protocol_id: string;
  org_id: string;
  page_count: number;
  char_count: number;
  image_count: number;
  processed_at: string;
}

interface BundleInfo {
  id: string;
  name: string;
  color?: string;
  description?: string;
}

interface EDInfo {
  id: string;
  name: string;
  location?: string;
  bundles: BundleInfo[];
}

interface EnterpriseInfo {
  id: string;
  name: string;
  eds: EDInfo[];
}

interface HospitalData {
  [ed: string]: {
    [bundle: string]: Protocol[];
  };
}

interface AllHospitals {
  [enterprise: string]: HospitalData;
}

interface UploadStatus {
  status: "idle" | "uploading" | "processing" | "success" | "error";
  message: string;
  progress?: number;
  totalFiles?: number;
  completedFiles?: number;
}

export default function AdminPage() {
  const { user, userProfile, loading: authLoading } = useAuth();

  // Selection state
  const [enterprises, setEnterprises] = useState<EnterpriseInfo[]>([]);
  const [selectedEnterprise, setSelectedEnterprise] = useState("");
  const [selectedED, setSelectedED] = useState("");
  const [selectedBundle, setSelectedBundle] = useState("");
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const [viewMode, setViewMode] = useState<"upload" | "browse">("upload");
  const [protocols, setProtocols] = useState<Protocol[]>([]);
  const [allHospitals, setAllHospitals] = useState<AllHospitals>({});
  const [expandedHospitals, setExpandedHospitals] = useState<Set<string>>(new Set());
  const [expandedEDs, setExpandedEDs] = useState<Set<string>>(new Set());
  const [expandedBundles, setExpandedBundles] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>({ status: "idle", message: "" });
  const [dragActive, setDragActive] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [reindexStatus, setReindexStatus] = useState<{ type: "success" | "error" | null; message: string }>({ type: null, message: "" });

  // Derived helpers
  const currentEnterprise = enterprises.find((e) => e.id === selectedEnterprise);
  const currentED = currentEnterprise?.eds.find((ed) => ed.id === selectedED);
  const currentBundle = currentED?.bundles.find((b) => b.id === selectedBundle);

  // Fetch enterprises hierarchy from Firestore
  useEffect(() => {
    if (!user) return;
    const fetchEnterprises = async () => {
      try {
        const token = await user.getIdToken();
        const res = await fetch(`${API_URL}/admin/enterprises`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          const ents = data.enterprises || [];
          setEnterprises(ents);

          // Auto-select if user has an enterprise
          if (userProfile?.enterpriseId) {
            setSelectedEnterprise(userProfile.enterpriseId);
            const ent = ents.find((e: EnterpriseInfo) => e.id === userProfile.enterpriseId);
            if (ent && ent.eds.length === 1) {
              setSelectedED(ent.eds[0].id);
            }
          } else if (ents.length === 1) {
            setSelectedEnterprise(ents[0].id);
            if (ents[0].eds.length === 1) {
              setSelectedED(ents[0].eds[0].id);
            }
          }
        }
      } catch (err) {
        console.error("Failed to fetch enterprises:", err);
      }
    };
    fetchEnterprises();
  }, [user, userProfile]);

  const fetchAllHospitals = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/hospitals`);
      if (res.ok) {
        const data = await res.json();
        setAllHospitals(data.hospitals || {});
      }
    } catch (err) {
      console.error("Failed to fetch hospitals:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchProtocols = useCallback(async () => {
    if (!selectedEnterprise || !selectedED || !selectedBundle) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({
        enterprise_id: selectedEnterprise,
        ed_id: selectedED,
        bundle_id: selectedBundle,
      });
      const res = await fetch(`${API_URL}/protocols?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setProtocols(data.protocols || []);
      }
    } catch (err) {
      console.error("Failed to fetch protocols:", err);
    } finally {
      setLoading(false);
    }
  }, [selectedEnterprise, selectedED, selectedBundle]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchProtocols();
      fetchAllHospitals();
    }
  }, [isAuthenticated, fetchProtocols, fetchAllHospitals]);

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

  const toggleED = (key: string) => {
    const newExpanded = new Set(expandedEDs);
    if (newExpanded.has(key)) {
      newExpanded.delete(key);
    } else {
      newExpanded.add(key);
    }
    setExpandedEDs(newExpanded);
  };

  const handleDelete = async (enterpriseId: string, edId: string, bundleId: string, protocolId: string) => {
    if (!confirm(`Delete protocol "${protocolId.replace(/_/g, " ")}"? This cannot be undone.`)) {
      return;
    }

    const deleteKey = `${enterpriseId}/${edId}/${bundleId}/${protocolId}`;
    setDeleting(deleteKey);

    try {
      const res = await fetch(`${API_URL}/protocols/${encodeURIComponent(enterpriseId)}/${encodeURIComponent(edId)}/${encodeURIComponent(bundleId)}/${encodeURIComponent(protocolId)}`, {
        method: "DELETE",
      });

      if (res.ok) {
        await fetchAllHospitals();
        await fetchProtocols();
      } else {
        alert("Failed to delete protocol");
      }
    } catch (err) {
      console.error("Delete error:", err);
      alert("Failed to delete protocol");
    } finally {
      setDeleting(null);
    }
  };

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedEnterprise && selectedED && selectedBundle) {
      setIsAuthenticated(true);
    }
  };

  const handleReindexRAG = async () => {
    if (!confirm("Re-index all protocols in RAG? This will clear and rebuild the search index.")) {
      return;
    }
    
    setReindexing(true);
    setReindexStatus({ type: null, message: "" });
    
    try {
      const res = await fetch(`${API_URL}/admin/reindex-rag`, {
        method: "POST",
      });
      
      if (res.ok) {
        const data = await res.json();
        setReindexStatus({ 
          type: "success", 
          message: `${data.message || `Cleared ${data.deleted} files, indexing ${data.files_to_index} files`}` 
        });
        
        // Poll for completion if we got an operation name
        if (data.operation) {
          const pollInterval = setInterval(async () => {
            try {
              const statusRes = await fetch(`${API_URL}/admin/reindex-rag/status?operation=${encodeURIComponent(data.operation)}`);
              if (statusRes.ok) {
                const statusData = await statusRes.json();
                if (statusData.done) {
                  clearInterval(pollInterval);
                  setReindexing(false);
                  setReindexStatus({
                    type: statusData.status === "completed" ? "success" : "error",
                    message: statusData.message
                  });
                } else {
                  setReindexStatus({ type: "success", message: `⏳ ${statusData.message}` });
                }
              }
            } catch {
              // Keep polling on network errors
            }
          }, 5000); // Check every 5 seconds
          
          // Stop polling after 5 minutes max
          setTimeout(() => {
            clearInterval(pollInterval);
            setReindexing(false);
          }, 300000);
          
          return; // Don't set reindexing to false yet
        }
      } else {
        const error = await res.text();
        setReindexStatus({ type: "error", message: `Failed: ${error}` });
      }
    } catch (err) {
      console.error("Reindex error:", err);
      setReindexStatus({ type: "error", message: "Failed to connect to API" });
    } finally {
      setReindexing(false);
    }
  };

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    const pdfFiles = Array.from(files).filter(file => file.type === "application/pdf");
    
    if (pdfFiles.length === 0) {
      setUploadStatus({ status: "error", message: "Please upload PDF files only" });
      return;
    }

    const totalFiles = pdfFiles.length;
    let completedFiles = 0;
    let failedFiles: string[] = [];

    setUploadStatus({ 
      status: "uploading", 
      message: `Uploading ${totalFiles} file(s)...`, 
      progress: 0,
      totalFiles,
      completedFiles: 0
    });

    for (const file of pdfFiles) {
      try {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("enterprise_id", selectedEnterprise);
        formData.append("ed_id", selectedED);
        formData.append("bundle_id", selectedBundle);

        setUploadStatus({ 
          status: "uploading", 
          message: `Uploading: ${file.name}...`, 
          progress: Math.round((completedFiles / totalFiles) * 100),
          totalFiles,
          completedFiles
        });

        const uploadRes = await fetch(`${API_URL}/upload`, {
          method: "POST",
          body: formData,
        });

        if (!uploadRes.ok) {
          failedFiles.push(file.name);
        } else {
          completedFiles++;
        }

        setUploadStatus({ 
          status: "processing", 
          message: `Processing: ${file.name}...`, 
          progress: Math.round((completedFiles / totalFiles) * 100),
          totalFiles,
          completedFiles
        });

      } catch (err) {
        failedFiles.push(file.name);
      }
    }

    if (failedFiles.length === 0) {
      setUploadStatus({ 
        status: "success", 
        message: `Successfully uploaded ${completedFiles} protocol(s)! Processing may take a moment.`,
        totalFiles,
        completedFiles
      });
    } else if (completedFiles > 0) {
      setUploadStatus({ 
        status: "success", 
        message: `Uploaded ${completedFiles}/${totalFiles}. Failed: ${failedFiles.join(", ")}`,
        totalFiles,
        completedFiles
      });
    } else {
      setUploadStatus({ 
        status: "error", 
        message: `All uploads failed. Please try again.` 
      });
    }

    setTimeout(() => {
      fetchProtocols();
      fetchAllHospitals();
    }, 2000);

    setTimeout(() => {
      setUploadStatus({ status: "idle", message: "" });
    }, 5000);
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    handleUpload(e.dataTransfer.files);
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-[#131314] text-white flex">
        <div className="w-16 flex-shrink-0 flex flex-col items-center py-4 border-r border-white/10">
          <Link href="/" className="w-10 h-10 flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/10 rounded-full transition-colors">
            <Menu className="w-5 h-5" />
          </Link>
        </div>

        <div className="flex-1 flex flex-col">
          <header className="h-16 flex items-center justify-between px-6 border-b border-white/5">
            <Link href="/" className="text-xl font-normal text-white hover:text-white/80 transition-colors">
              EM Protocols
            </Link>
            <span className="text-xs text-gray-400 px-2.5 py-1 bg-white/5 rounded-full border border-white/10">
              ADMIN
            </span>
          </header>

          <div className="flex-1 flex flex-col items-center justify-center px-6">
            <div className="w-full max-w-md space-y-8">
              <div className="text-center space-y-3">
                <Shield className="w-12 h-12 mx-auto text-blue-400" />
                <h1 className="text-4xl font-normal text-white/90 tracking-tight">
                  Admin Access
                </h1>
                <p className="text-[#9aa0a6]">
                  Upload and manage your protocols
                </p>
              </div>

              <form onSubmit={handleLogin} className="bg-[#1e1f20] rounded-[28px] border border-[#3c4043] p-6 space-y-4">
                <div>
                  <label className="block text-sm text-[#9aa0a6] mb-2">
                    Enterprise
                  </label>
                  <select
                    value={selectedEnterprise}
                    onChange={(e) => {
                      setSelectedEnterprise(e.target.value);
                      setSelectedED("");
                      setSelectedBundle("");
                    }}
                    className="w-full px-4 py-3 bg-[#131314] border border-[#3c4043] rounded-full text-white focus:outline-none focus:border-[#8ab4f8] transition-colors appearance-none cursor-pointer"
                  >
                    <option value="" className="bg-[#131314]">Select enterprise...</option>
                    {enterprises.map((ent) => (
                      <option key={ent.id} value={ent.id} className="bg-[#131314]">
                        {ent.name} ({ent.id})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-[#9aa0a6] mb-2">
                    Emergency Department
                  </label>
                  <select
                    value={selectedED}
                    onChange={(e) => {
                      setSelectedED(e.target.value);
                      setSelectedBundle("");
                    }}
                    disabled={!selectedEnterprise}
                    className="w-full px-4 py-3 bg-[#131314] border border-[#3c4043] rounded-full text-white focus:outline-none focus:border-[#8ab4f8] transition-colors appearance-none cursor-pointer disabled:text-[#5f6368] disabled:cursor-not-allowed"
                  >
                    <option value="" className="bg-[#131314]">Select ED...</option>
                    {currentEnterprise?.eds.map((ed) => (
                      <option key={ed.id} value={ed.id} className="bg-[#131314]">
                        {ed.name}{ed.location ? ` — ${ed.location}` : ""} ({ed.id})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-[#9aa0a6] mb-2">
                    Protocol Bundle
                  </label>
                  <select
                    value={selectedBundle}
                    onChange={(e) => setSelectedBundle(e.target.value)}
                    disabled={!selectedED}
                    className="w-full px-4 py-3 bg-[#131314] border border-[#3c4043] rounded-full text-white focus:outline-none focus:border-[#8ab4f8] transition-colors appearance-none cursor-pointer disabled:text-[#5f6368] disabled:cursor-not-allowed"
                  >
                    <option value="" className="bg-[#131314]">Select bundle...</option>
                    {currentED?.bundles.map((b) => (
                      <option key={b.id} value={b.id} className="bg-[#131314]">
                        {b.name}{b.description ? ` — ${b.description}` : ""} ({b.id})
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-[#5f6368] mt-2 px-2">
                    Bundles organize protocols by specialty or use case
                  </p>
                </div>
                <button
                  type="submit"
                  disabled={!selectedEnterprise || !selectedED || !selectedBundle}
                  className="w-full py-3 bg-[#8ab4f8] text-[#131314] rounded-full font-medium hover:bg-[#aecbfa] disabled:bg-[#3c4043] disabled:text-[#5f6368] disabled:cursor-not-allowed transition-all"
                >
                  Continue
                </button>
              </form>

              <Link href="/" className="block text-center text-sm text-[#8ab4f8] hover:text-[#aecbfa] transition-colors">
                ← Back to Search
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#131314] text-white flex">
      <div className="w-16 flex-shrink-0 flex flex-col items-center py-4 border-r border-white/10">
        <Link href="/" className="w-10 h-10 flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/10 rounded-full transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <button className="w-10 h-10 mt-4 flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/10 rounded-full transition-colors">
          <SquarePen className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 flex flex-col">
        <header className="h-16 flex items-center justify-between px-6 border-b border-white/5">
          <div className="flex items-center gap-3">
            <Link href="/" className="text-xl font-normal text-white hover:text-white/80 transition-colors">
              EM Protocols
            </Link>
            <span className="text-xs text-[#9aa0a6]">•</span>
            <span className="text-sm text-white">{currentEnterprise?.name || selectedEnterprise}</span>
            <span className="text-xs text-[#9aa0a6]">/</span>
            <span className="text-sm text-green-400">{currentED?.name || selectedED}</span>
            <span className="text-xs text-[#9aa0a6]">/</span>
            <span className="text-sm text-[#8ab4f8]">{currentBundle?.name || selectedBundle}</span>
          </div>
          <button
            onClick={() => setIsAuthenticated(false)}
            className="text-sm text-[#9aa0a6] hover:text-white px-4 py-2 rounded-full border border-[#3c4043] hover:bg-[#3c4043] transition-colors"
          >
            Switch Bundle
          </button>
        </header>

        <div className="px-6 pt-4">
          <div className="flex items-center justify-between">
            <div className="flex gap-2">
              <button
                onClick={() => setViewMode("upload")}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                  viewMode === "upload"
                    ? "bg-[#8ab4f8] text-[#131314]"
                    : "text-[#9aa0a6] hover:text-white hover:bg-white/10"
                }`}
              >
                Upload Protocols
              </button>
              <button
                onClick={() => setViewMode("browse")}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                  viewMode === "browse"
                    ? "bg-[#8ab4f8] text-[#131314]"
                    : "text-[#9aa0a6] hover:text-white hover:bg-white/10"
                }`}
              >
                Browse All Enterprises
              </button>
            </div>
            
            {/* Re-index RAG Button */}
            <div className="flex items-center gap-3">
              {reindexStatus.type && (
                <span className={`text-sm ${reindexStatus.type === "success" ? "text-green-400" : "text-red-400"}`}>
                  {reindexStatus.message}
                </span>
              )}
              <button
                onClick={handleReindexRAG}
                disabled={reindexing}
                className="flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium border border-[#3c4043] text-[#9aa0a6] hover:text-white hover:bg-[#3c4043] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Database className={`w-4 h-4 ${reindexing ? "animate-pulse" : ""}`} />
                {reindexing ? "Re-indexing..." : "Re-index RAG"}
              </button>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-auto p-6">
          <div className="max-w-4xl mx-auto space-y-6">

            {viewMode === "upload" && (
              <>
                <div
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                  className={`relative border-2 border-dashed rounded-[28px] p-8 transition-all ${
                    dragActive 
                      ? "border-[#8ab4f8] bg-[#8ab4f8]/10" 
                      : "border-[#3c4043] bg-[#1e1f20] hover:border-[#5f6368]"
                  }`}
                >
                  <input
                    type="file"
                    accept=".pdf"
                    multiple
                    onChange={(e) => handleUpload(e.target.files)}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    disabled={uploadStatus.status === "uploading" || uploadStatus.status === "processing"}
                  />
                  
                  <div className="text-center">
                    {uploadStatus.status === "idle" && (
                      <>
                        <Upload className="w-12 h-12 mx-auto text-[#9aa0a6] mb-4" />
                        <p className="text-lg font-medium text-white mb-1">
                          Drop PDFs here or click to upload
                        </p>
                        <p className="text-sm text-[#9aa0a6]">
                          Multiple protocols can be uploaded at once
                        </p>
                      </>
                    )}

                    {(uploadStatus.status === "uploading" || uploadStatus.status === "processing") && (
                      <>
                        <RefreshCw className="w-12 h-12 mx-auto text-[#8ab4f8] mb-4 animate-spin" />
                        <p className="text-lg font-medium text-[#8ab4f8] mb-1">
                          {uploadStatus.message}
                        </p>
                        {uploadStatus.totalFiles && uploadStatus.totalFiles > 1 && (
                          <p className="text-sm text-[#9aa0a6] mb-2">
                            {uploadStatus.completedFiles || 0} of {uploadStatus.totalFiles} files completed
                          </p>
                        )}
                        {uploadStatus.progress !== undefined && (
                          <div className="w-64 mx-auto bg-[#3c4043] rounded-full h-2 mt-3">
                            <div 
                              className="bg-[#8ab4f8] h-2 rounded-full transition-all"
                              style={{ width: `${uploadStatus.progress}%` }}
                            />
                          </div>
                        )}
                      </>
                    )}

                    {uploadStatus.status === "success" && (
                      <>
                        <CheckCircle className="w-12 h-12 mx-auto text-green-400 mb-4" />
                        <p className="text-lg font-medium text-green-400">
                          {uploadStatus.message}
                        </p>
                      </>
                    )}

                    {uploadStatus.status === "error" && (
                      <>
                        <AlertCircle className="w-12 h-12 mx-auto text-red-400 mb-4" />
                        <p className="text-lg font-medium text-red-400">
                          {uploadStatus.message}
                        </p>
                      </>
                    )}
                  </div>
                </div>

                <div className="bg-[#1e1f20] rounded-[28px] border border-[#3c4043] overflow-hidden">
                  <div className="flex items-center justify-between p-5 border-b border-[#3c4043]">
                    <h2 className="text-lg font-medium text-white">
                      Protocols in {currentEnterprise?.name || selectedEnterprise} / {currentED?.name || selectedED} / {currentBundle?.name || selectedBundle}
                    </h2>
                    <button
                      onClick={fetchProtocols}
                      disabled={loading}
                      className="text-sm text-[#8ab4f8] hover:text-[#aecbfa] flex items-center gap-2 px-4 py-2 rounded-full hover:bg-[#8ab4f8]/10 transition-colors"
                    >
                      <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                      Refresh
                    </button>
                  </div>

                  {protocols.length === 0 ? (
                    <div className="p-8 text-center">
                      <FileText className="w-12 h-12 mx-auto text-[#5f6368] mb-3" />
                      <p className="text-[#9aa0a6]">No protocols uploaded yet</p>
                      <p className="text-sm text-[#5f6368]">Upload a PDF to get started</p>
                    </div>
                  ) : (
                    <ul className="divide-y divide-[#3c4043]">
                      {protocols.map((protocol) => (
                        <li key={protocol.protocol_id} className="p-5 hover:bg-[#2c2d2e] transition-colors">
                          <div className="flex items-center justify-between">
                            <div>
                              <h3 className="font-medium text-white">
                                {protocol.protocol_id.replace(/_/g, " ")}
                              </h3>
                              <p className="text-sm text-[#9aa0a6] mt-1">
                                {protocol.page_count} pages • {protocol.image_count} images • {protocol.char_count.toLocaleString()} characters
                              </p>
                            </div>
                            <div className="flex items-center gap-3">
                              <p className="text-xs text-[#5f6368]">
                                {new Date(protocol.processed_at).toLocaleDateString()}
                              </p>
                              <button
                                onClick={() => handleDelete(selectedEnterprise, selectedED, selectedBundle, protocol.protocol_id)}
                                disabled={deleting === `${selectedEnterprise}/${selectedED}/${selectedBundle}/${protocol.protocol_id}`}
                                className="p-2 text-[#9aa0a6] hover:text-red-400 hover:bg-red-400/10 rounded-full transition-colors disabled:opacity-50"
                              >
                                {deleting === `${selectedEnterprise}/${selectedED}/${selectedBundle}/${protocol.protocol_id}` ? (
                                  <RefreshCw className="w-4 h-4 animate-spin" />
                                ) : (
                                  <Trash2 className="w-4 h-4" />
                                )}
                              </button>
                            </div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </>
            )}

            {viewMode === "browse" && (
              <div className="bg-[#1e1f20] rounded-[28px] border border-[#3c4043] overflow-hidden">
                <div className="flex items-center justify-between p-5 border-b border-[#3c4043]">
                  <h2 className="text-lg font-medium text-white">All Enterprises & Protocols</h2>
                  <button
                    onClick={fetchAllHospitals}
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
                    {Object.entries(allHospitals).sort().map(([enterprise, eds]) => (
                      <div key={enterprise}>
                        <button
                          onClick={() => toggleHospital(enterprise)}
                          className="w-full px-5 py-4 flex items-center gap-3 hover:bg-[#2c2d2e] transition-colors"
                        >
                          {expandedHospitals.has(enterprise) ? (
                            <ChevronDown className="w-4 h-4 text-[#9aa0a6]" />
                          ) : (
                            <ChevronRight className="w-4 h-4 text-[#9aa0a6]" />
                          )}
                          <Building2 className="w-5 h-5 text-[#8ab4f8]" />
                          <span className="font-medium text-white">{enterprise}</span>
                          <span className="text-xs text-[#5f6368] ml-auto">
                            {Object.keys(eds).length} ED(s)
                          </span>
                        </button>

                        {expandedHospitals.has(enterprise) && (
                          <div className="bg-[#1a1a1b]">
                            {Object.entries(eds).sort().map(([ed, bundles]) => {
                              const edKey = `${enterprise}/${ed}`;
                              return (
                                <div key={edKey}>
                                  <button
                                    onClick={() => toggleED(edKey)}
                                    className="w-full pl-12 pr-5 py-3 flex items-center gap-3 hover:bg-[#2c2d2e] transition-colors"
                                  >
                                    {expandedEDs.has(edKey) ? (
                                      <ChevronDown className="w-4 h-4 text-[#9aa0a6]" />
                                    ) : (
                                      <ChevronRight className="w-4 h-4 text-[#9aa0a6]" />
                                    )}
                                    <MapPin className="w-4 h-4 text-green-400" />
                                    <span className="text-[#e8eaed]">{ed}</span>
                                    <span className="text-xs text-[#5f6368] ml-auto">
                                      {Object.keys(bundles).length} bundle(s)
                                    </span>
                                  </button>

                                  {expandedEDs.has(edKey) && (
                                    <div className="bg-[#171718]">
                                      {Object.entries(bundles).sort().map(([bundle, bundleProtocols]) => {
                                        const bundleKey = `${edKey}/${bundle}`;
                                        return (
                                          <div key={bundleKey}>
                                            <button
                                              onClick={() => toggleBundle(bundleKey)}
                                              className="w-full pl-20 pr-5 py-3 flex items-center gap-3 hover:bg-[#2c2d2e] transition-colors"
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
                                                {bundleProtocols.map((protocol) => {
                                                  const deleteKey = `${enterprise}/${ed}/${bundle}/${protocol.protocol_id}`;
                                                  return (
                                                    <li
                                                      key={protocol.protocol_id}
                                                      className="pl-28 pr-5 py-3 flex items-center justify-between hover:bg-[#2c2d2e] transition-colors"
                                                    >
                                                      <div className="flex items-center gap-3">
                                                        <FileText className="w-4 h-4 text-[#5f6368]" />
                                                        <div>
                                                          <span className="text-[#e8eaed]">
                                                            {protocol.protocol_id.replace(/_/g, " ")}
                                                          </span>
                                                          <p className="text-xs text-[#5f6368]">
                                                            {protocol.page_count} pages • {protocol.char_count?.toLocaleString() || 0} chars
                                                          </p>
                                                        </div>
                                                      </div>
                                                      <button
                                                        onClick={() => handleDelete(enterprise, ed, bundle, protocol.protocol_id)}
                                                        disabled={deleting === deleteKey}
                                                        className="p-2 text-[#9aa0a6] hover:text-red-400 hover:bg-red-400/10 rounded-full transition-colors disabled:opacity-50"
                                                      >
                                                        {deleting === deleteKey ? (
                                                          <RefreshCw className="w-4 h-4 animate-spin" />
                                                        ) : (
                                                          <Trash2 className="w-4 h-4" />
                                                        )}
                                                      </button>
                                                    </li>
                                                  );
                                                })}
                                              </ul>
                                            )}
                                          </div>
                                        );
                                      })}
                                    </div>
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

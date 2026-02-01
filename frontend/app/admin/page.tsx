"use client";

import { useState, useEffect, useCallback } from "react";
import { Upload, FileText, Trash2, RefreshCw, CheckCircle, AlertCircle, ArrowLeft, Menu, SquarePen, Shield } from "lucide-react";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://em-protocol-api-930035889332.us-central1.run.app";

interface Protocol {
  protocol_id: string;
  org_id: string;
  page_count: number;
  char_count: number;
  image_count: number;
  processed_at: string;
}

interface UploadStatus {
  status: "idle" | "uploading" | "processing" | "success" | "error";
  message: string;
  progress?: number;
}

export default function AdminPage() {
  const [orgId, setOrgId] = useState("");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [protocols, setProtocols] = useState<Protocol[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>({ status: "idle", message: "" });
  const [dragActive, setDragActive] = useState(false);

  // Fetch protocols for the org
  const fetchProtocols = useCallback(async () => {
    if (!orgId) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/protocols?org_id=${orgId}`);
      if (res.ok) {
        const data = await res.json();
        setProtocols(data.protocols || []);
      }
    } catch (err) {
      console.error("Failed to fetch protocols:", err);
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchProtocols();
    }
  }, [isAuthenticated, fetchProtocols]);

  // Handle login
  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (orgId.trim()) {
      setIsAuthenticated(true);
    }
  };

  // Handle file upload
  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    const file = files[0];
    if (file.type !== "application/pdf") {
      setUploadStatus({ status: "error", message: "Please upload a PDF file" });
      return;
    }

    setUploadStatus({ status: "uploading", message: "Uploading PDF...", progress: 25 });

    try {
      // Create form data for multipart upload
      const formData = new FormData();
      formData.append("file", file);
      formData.append("org_id", orgId);

      setUploadStatus({ status: "uploading", message: "Uploading to cloud storage...", progress: 50 });

      // Upload directly to API
      const uploadRes = await fetch(`${API_URL}/upload`, {
        method: "POST",
        body: formData,
      });

      if (!uploadRes.ok) {
        throw new Error("Failed to upload file");
      }

      setUploadStatus({ 
        status: "processing", 
        message: "Processing PDF... This may take a minute.",
        progress: 75 
      });

      // Poll for completion (check if protocol appears in list)
      const protocolId = file.name.replace(".pdf", "").replace(/[^a-zA-Z0-9_-]/g, "_");
      let attempts = 0;
      const maxAttempts = 30; // 30 seconds max

      const checkInterval = setInterval(async () => {
        attempts++;
        try {
          const checkRes = await fetch(`${API_URL}/protocols?org_id=${orgId}`);
          if (checkRes.ok) {
            const data = await checkRes.json();
            const found = data.protocols?.find((p: Protocol) => p.protocol_id === protocolId);
            if (found) {
              clearInterval(checkInterval);
              setUploadStatus({ status: "success", message: "Protocol uploaded and indexed!" });
              setProtocols(data.protocols);
              setTimeout(() => setUploadStatus({ status: "idle", message: "" }), 3000);
            }
          }
        } catch (err) {
          // Keep polling
        }

        if (attempts >= maxAttempts) {
          clearInterval(checkInterval);
          setUploadStatus({ 
            status: "success", 
            message: "Upload complete! Processing may still be in progress." 
          });
          fetchProtocols();
          setTimeout(() => setUploadStatus({ status: "idle", message: "" }), 3000);
        }
      }, 1000);

    } catch (err) {
      setUploadStatus({ 
        status: "error", 
        message: err instanceof Error ? err.message : "Upload failed" 
      });
    }
  };

  // Drag and drop handlers
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

  // Login screen
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-[#131314] text-white flex">
        {/* Left Sidebar */}
        <div className="w-16 flex-shrink-0 flex flex-col items-center py-4 border-r border-white/10">
          <Link href="/" className="w-10 h-10 flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/10 rounded-full transition-colors">
            <Menu className="w-5 h-5" />
          </Link>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex flex-col">
          {/* Header */}
          <header className="h-16 flex items-center justify-between px-6 border-b border-white/5">
            <Link href="/" className="text-xl font-normal text-white hover:text-white/80 transition-colors">
              EM Protocols
            </Link>
            <span className="text-xs text-gray-400 px-2.5 py-1 bg-white/5 rounded-full border border-white/10">
              ADMIN
            </span>
          </header>

          {/* Center Content */}
          <div className="flex-1 flex flex-col items-center justify-center px-6">
            <div className="w-full max-w-md space-y-8">
              {/* Greeting */}
              <div className="text-center space-y-3">
                <Shield className="w-12 h-12 mx-auto text-blue-400" />
                <h1 className="text-4xl font-normal text-white/90 tracking-tight">
                  Admin Access
                </h1>
                <p className="text-[#9aa0a6]">
                  Upload and manage your protocols
                </p>
              </div>

              {/* Login Box */}
              <form onSubmit={handleLogin} className="bg-[#1e1f20] rounded-[28px] border border-[#3c4043] p-6 space-y-4">
                <div>
                  <label className="block text-sm text-[#9aa0a6] mb-2">
                    Organization ID
                  </label>
                  <input
                    type="text"
                    value={orgId}
                    onChange={(e) => setOrgId(e.target.value)}
                    placeholder="e.g., mayo-clinic"
                    className="w-full px-4 py-3 bg-[#131314] border border-[#3c4043] rounded-full text-white placeholder-[#5f6368] focus:outline-none focus:border-[#8ab4f8] transition-colors"
                  />
                </div>
                <button
                  type="submit"
                  disabled={!orgId.trim()}
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

  // Admin dashboard
  return (
    <div className="min-h-screen bg-[#131314] text-white flex">
      {/* Left Sidebar */}
      <div className="w-16 flex-shrink-0 flex flex-col items-center py-4 border-r border-white/10">
        <Link href="/" className="w-10 h-10 flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/10 rounded-full transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <button className="w-10 h-10 mt-4 flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/10 rounded-full transition-colors">
          <SquarePen className="w-5 h-5" />
        </button>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="h-16 flex items-center justify-between px-6 border-b border-white/5">
          <div className="flex items-center gap-3">
            <Link href="/" className="text-xl font-normal text-white hover:text-white/80 transition-colors">
              EM Protocols
            </Link>
            <span className="text-xs text-[#9aa0a6]">•</span>
            <span className="text-sm text-[#9aa0a6]">{orgId}</span>
          </div>
          <button
            onClick={() => setIsAuthenticated(false)}
            className="text-sm text-[#9aa0a6] hover:text-white px-4 py-2 rounded-full border border-[#3c4043] hover:bg-[#3c4043] transition-colors"
          >
            Switch Org
          </button>
        </header>

        {/* Dashboard Content */}
        <div className="flex-1 overflow-auto p-6">
          <div className="max-w-4xl mx-auto space-y-6">

            {/* Upload Area */}
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
                onChange={(e) => handleUpload(e.target.files)}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                disabled={uploadStatus.status === "uploading" || uploadStatus.status === "processing"}
              />
              
              <div className="text-center">
                {uploadStatus.status === "idle" && (
                  <>
                    <Upload className="w-12 h-12 mx-auto text-[#9aa0a6] mb-4" />
                    <p className="text-lg font-medium text-white mb-1">
                      Drop PDF here or click to upload
                    </p>
                    <p className="text-sm text-[#9aa0a6]">
                      Protocol will be automatically processed and indexed
                    </p>
                  </>
                )}

                {(uploadStatus.status === "uploading" || uploadStatus.status === "processing") && (
                  <>
                    <RefreshCw className="w-12 h-12 mx-auto text-[#8ab4f8] mb-4 animate-spin" />
                    <p className="text-lg font-medium text-[#8ab4f8] mb-1">
                      {uploadStatus.message}
                    </p>
                    {uploadStatus.progress && (
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

            {/* Protocols List */}
            <div className="bg-[#1e1f20] rounded-[28px] border border-[#3c4043] overflow-hidden">
              <div className="flex items-center justify-between p-5 border-b border-[#3c4043]">
                <h2 className="text-lg font-medium text-white">Your Protocols</h2>
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
                        <div className="text-right">
                          <p className="text-xs text-[#5f6368]">
                            {new Date(protocol.processed_at).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

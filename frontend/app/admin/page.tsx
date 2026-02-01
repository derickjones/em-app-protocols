"use client";

import { useState, useEffect, useCallback } from "react";
import { Upload, FileText, Trash2, RefreshCw, CheckCircle, AlertCircle, ArrowLeft } from "lucide-react";
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

    setUploadStatus({ status: "uploading", message: "Uploading PDF...", progress: 0 });

    try {
      // Get signed upload URL from API
      const urlRes = await fetch(`${API_URL}/upload-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          org_id: orgId,
          filename: file.name,
        }),
      });

      if (!urlRes.ok) {
        throw new Error("Failed to get upload URL");
      }

      const { upload_url, gcs_path } = await urlRes.json();

      setUploadStatus({ status: "uploading", message: "Uploading to cloud storage...", progress: 50 });

      // Upload directly to GCS
      const uploadRes = await fetch(upload_url, {
        method: "PUT",
        headers: { "Content-Type": "application/pdf" },
        body: file,
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
      <main className="flex flex-col items-center justify-center min-h-screen px-4 py-8 bg-gray-50">
        <div className="w-full max-w-md">
          <div className="bg-white rounded-2xl shadow-lg p-8">
            <h1 className="text-2xl font-bold text-center mb-2">🏥 Protocol Admin</h1>
            <p className="text-gray-500 text-center mb-6">Upload and manage your organization&apos;s protocols</p>
            
            <form onSubmit={handleLogin}>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Organization ID
              </label>
              <input
                type="text"
                value={orgId}
                onChange={(e) => setOrgId(e.target.value)}
                placeholder="e.g., mayo-clinic"
                className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100 transition-all mb-4"
              />
              <button
                type="submit"
                disabled={!orgId.trim()}
                className="w-full py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-all"
              >
                Continue
              </button>
            </form>

            <Link href="/" className="block text-center text-sm text-gray-500 hover:text-blue-600 mt-4">
              ← Back to Search
            </Link>
          </div>
        </div>
      </main>
    );
  }

  // Admin dashboard
  return (
    <main className="min-h-screen bg-gray-50 px-4 py-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <Link href="/" className="text-blue-600 hover:text-blue-700 text-sm flex items-center gap-1 mb-2">
              <ArrowLeft className="w-4 h-4" /> Back to Search
            </Link>
            <h1 className="text-2xl font-bold">🏥 Protocol Admin</h1>
            <p className="text-gray-500">Organization: <span className="font-medium text-gray-700">{orgId}</span></p>
          </div>
          <button
            onClick={() => setIsAuthenticated(false)}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Switch Org
          </button>
        </div>

        {/* Upload Area */}
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          className={`relative border-2 border-dashed rounded-2xl p-8 mb-8 transition-all ${
            dragActive 
              ? "border-blue-500 bg-blue-50" 
              : "border-gray-300 bg-white hover:border-gray-400"
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
                <Upload className="w-12 h-12 mx-auto text-gray-400 mb-4" />
                <p className="text-lg font-medium text-gray-700 mb-1">
                  Drop PDF here or click to upload
                </p>
                <p className="text-sm text-gray-500">
                  Protocol will be automatically processed and indexed
                </p>
              </>
            )}

            {(uploadStatus.status === "uploading" || uploadStatus.status === "processing") && (
              <>
                <RefreshCw className="w-12 h-12 mx-auto text-blue-500 mb-4 animate-spin" />
                <p className="text-lg font-medium text-blue-700 mb-1">
                  {uploadStatus.message}
                </p>
                {uploadStatus.progress && (
                  <div className="w-64 mx-auto bg-gray-200 rounded-full h-2 mt-3">
                    <div 
                      className="bg-blue-600 h-2 rounded-full transition-all"
                      style={{ width: `${uploadStatus.progress}%` }}
                    />
                  </div>
                )}
              </>
            )}

            {uploadStatus.status === "success" && (
              <>
                <CheckCircle className="w-12 h-12 mx-auto text-green-500 mb-4" />
                <p className="text-lg font-medium text-green-700">
                  {uploadStatus.message}
                </p>
              </>
            )}

            {uploadStatus.status === "error" && (
              <>
                <AlertCircle className="w-12 h-12 mx-auto text-red-500 mb-4" />
                <p className="text-lg font-medium text-red-700">
                  {uploadStatus.message}
                </p>
              </>
            )}
          </div>
        </div>

        {/* Protocols List */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200">
          <div className="flex items-center justify-between p-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold">Your Protocols</h2>
            <button
              onClick={fetchProtocols}
              disabled={loading}
              className="text-sm text-blue-600 hover:text-blue-700 flex items-center gap-1"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>

          {protocols.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              <FileText className="w-12 h-12 mx-auto text-gray-300 mb-3" />
              <p>No protocols uploaded yet</p>
              <p className="text-sm">Upload a PDF to get started</p>
            </div>
          ) : (
            <ul className="divide-y divide-gray-100">
              {protocols.map((protocol) => (
                <li key={protocol.protocol_id} className="p-4 hover:bg-gray-50 transition-colors">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-medium text-gray-900">
                        {protocol.protocol_id.replace(/_/g, " ")}
                      </h3>
                      <p className="text-sm text-gray-500">
                        {protocol.page_count} pages • {protocol.image_count} images • {protocol.char_count.toLocaleString()} characters
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-gray-400">
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
    </main>
  );
}

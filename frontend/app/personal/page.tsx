"use client";

/**
 * Personal Files Page
 * Upload, view, and manage personal documents for RAG search.
 * Files are indexed into a user-scoped Vertex AI RAG corpus.
 */

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  ArrowLeft,
  Upload,
  Trash2,
  FileText,
  Image as ImageIcon,
  File,
  Loader2,
  AlertTriangle,
  CheckCircle,
  XCircle,
  FolderOpen,
  X,
} from "lucide-react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "https://em-protocol-api-930035889332.us-central1.run.app";

interface PersonalFile {
  file_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: "processing" | "indexed" | "failed";
  error?: string;
  chunk_count?: number;
  uploaded_at: string;
  indexed_at?: string;
}

interface Quota {
  file_count: number;
  file_limit: number;
  bytes_used: number;
  bytes_limit: number;
}

const ALLOWED_TYPES = [
  "application/pdf",
  "image/png",
  "image/jpeg",
  "image/heic",
  "image/heif",
  "text/plain",
  "text/markdown",
];

const ALLOWED_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg", ".heic", ".heif", ".txt", ".md"];

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

function fileIcon(contentType: string) {
  if (contentType === "application/pdf") return <FileText className="w-5 h-5 text-red-400" />;
  if (contentType.startsWith("image/")) return <ImageIcon className="w-5 h-5 text-blue-400" />;
  return <File className="w-5 h-5 text-gray-400" />;
}

function statusBadge(status: string, error?: string) {
  switch (status) {
    case "indexed":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400">
          <CheckCircle className="w-3 h-3" /> Indexed
        </span>
      );
    case "processing":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-400">
          <Loader2 className="w-3 h-3 animate-spin" /> Processing
        </span>
      );
    case "failed":
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400" title={error}>
          <XCircle className="w-3 h-3" /> Failed
        </span>
      );
    default:
      return null;
  }
}

export default function PersonalPage() {
  const { user, userProfile, getIdToken } = useAuth();
  const router = useRouter();

  const [files, setFiles] = useState<PersonalFile[]>([]);
  const [quota, setQuota] = useState<Quota | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [showPhiWarning, setShowPhiWarning] = useState(true);

  const fetchData = useCallback(async () => {
    if (!user && !userProfile) return;
    try {
      const token = await getIdToken();
      if (!token) return;
      const headers = { Authorization: `Bearer ${token}` };
      const [filesRes, quotaRes] = await Promise.all([
        fetch(`${API_URL}/personal/files`, { headers }),
        fetch(`${API_URL}/personal/quota`, { headers }),
      ]);
      if (filesRes.ok) {
        const data = await filesRes.json();
        setFiles(data.files || []);
      }
      if (quotaRes.ok) {
        const data = await quotaRes.json();
        setQuota(data);
      }
    } catch (err) {
      console.error("Failed to fetch personal files:", err);
    } finally {
      setLoading(false);
    }
  }, [user, userProfile, getIdToken]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Poll for processing files
  useEffect(() => {
    const hasProcessing = files.some((f) => f.status === "processing");
    if (!hasProcessing) return;
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [files, fetchData]);

  const handleUpload = async (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0 || (!user && !userProfile)) return;
    setUploadError(null);
    setUploading(true);

    try {
      const token = await getIdToken();
      if (!token) throw new Error("Not authenticated");

      for (let i = 0; i < fileList.length; i++) {
        const file = fileList[i];

        // Validate extension
        const ext = "." + file.name.split(".").pop()?.toLowerCase();
        if (!ALLOWED_EXTENSIONS.includes(ext)) {
          setUploadError(`Unsupported file type: ${ext}. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}`);
          continue;
        }

        // Validate size (20 MB)
        if (file.size > 20 * 1024 * 1024) {
          setUploadError(`File too large: ${file.name} (${formatBytes(file.size)}). Max 20 MB.`);
          continue;
        }

        const formData = new FormData();
        formData.append("file", file);

        const res = await fetch(`${API_URL}/personal/upload`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: "Upload failed" }));
          setUploadError(err.detail || "Upload failed");
        }
      }
      // Refresh
      await fetchData();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (fileId: string) => {
    if (!user && !userProfile) return;
    setDeletingId(fileId);
    try {
      const token = await getIdToken();
      if (!token) return;
      await fetch(`${API_URL}/personal/files/${fileId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      await fetchData();
    } catch (err) {
      console.error("Delete failed:", err);
    } finally {
      setDeletingId(null);
    }
  };

  const handleDeleteAll = async () => {
    if ((!user && !userProfile) || !confirm("Delete ALL personal files? This cannot be undone.")) return;
    try {
      const token = await getIdToken();
      if (!token) return;
      await fetch(`${API_URL}/personal/files`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      await fetchData();
    } catch (err) {
      console.error("Delete all failed:", err);
    }
  };

  const quotaPct = quota ? Math.round((quota.file_count / quota.file_limit) * 100) : 0;
  const storagePct = quota ? Math.round((quota.bytes_used / quota.bytes_limit) * 100) : 0;

  if (!user && !userProfile) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-black">
        <p className="text-gray-500 dark:text-gray-400">Please sign in to manage personal files.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-black">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b bg-white/80 dark:bg-[#141414]/80 backdrop-blur border-gray-200 dark:border-[#2A2A2A]">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-4">
          <button onClick={() => router.push("/")} className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-[#1E1E1E] transition-colors">
            <ArrowLeft className="w-5 h-5 text-gray-600 dark:text-gray-300" />
          </button>
          <div className="flex items-center gap-2">
            <FolderOpen className="w-5 h-5 text-violet-500" />
            <h1 className="text-lg font-semibold text-gray-800 dark:text-gray-100">My Files</h1>
          </div>
          <div className="flex-1" />
          {files.length > 0 && (
            <button
              onClick={handleDeleteAll}
              className="px-3 py-1.5 text-xs font-medium text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
            >
              Delete All
            </button>
          )}
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        {/* PHI Warning */}
        {showPhiWarning && (
          <div className="relative flex items-start gap-3 p-4 rounded-xl border bg-amber-50 border-amber-200 dark:bg-amber-900/20 dark:border-amber-700/50">
            <AlertTriangle className="w-5 h-5 text-amber-500 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-amber-800 dark:text-amber-300">
                Privacy Notice
              </p>
              <p className="text-xs text-amber-700 dark:text-amber-400 mt-1 leading-relaxed">
                <strong>Do not upload documents containing Protected Health Information (PHI).</strong> This feature uses cloud AI services for text extraction and indexing.
                Uploaded files are stored in your private cloud workspace and are not shared with other users.
                By uploading, you confirm the content does not contain patient-identifiable data.
              </p>
            </div>
            <button onClick={() => setShowPhiWarning(false)} className="p-1 rounded hover:bg-amber-100 dark:hover:bg-amber-800/40">
              <X className="w-4 h-4 text-amber-500" />
            </button>
          </div>
        )}

        {/* Quota Bar */}
        {quota && (
          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 rounded-xl border bg-white dark:bg-[#141414] border-gray-200 dark:border-[#2A2A2A]">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Files</span>
                <span className="text-xs tabular-nums text-gray-600 dark:text-gray-300">{quota.file_count} / {quota.file_limit}</span>
              </div>
              <div className="h-2 rounded-full bg-gray-100 dark:bg-[#1E1E1E] overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${quotaPct > 80 ? 'bg-red-500' : 'bg-violet-500'}`}
                  style={{ width: `${quotaPct}%` }}
                />
              </div>
            </div>
            <div className="p-4 rounded-xl border bg-white dark:bg-[#141414] border-gray-200 dark:border-[#2A2A2A]">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Storage</span>
                <span className="text-xs tabular-nums text-gray-600 dark:text-gray-300">{formatBytes(quota.bytes_used)} / {formatBytes(quota.bytes_limit)}</span>
              </div>
              <div className="h-2 rounded-full bg-gray-100 dark:bg-[#1E1E1E] overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${storagePct > 80 ? 'bg-red-500' : 'bg-violet-500'}`}
                  style={{ width: `${storagePct}%` }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Upload Zone */}
        <div
          className={`relative border-2 border-dashed rounded-2xl p-8 text-center transition-colors ${
            dragOver
              ? "border-violet-500 bg-violet-50 dark:bg-violet-900/20"
              : "border-gray-300 dark:border-[#2A2A2A] hover:border-violet-400 dark:hover:border-violet-600"
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            handleUpload(e.dataTransfer.files);
          }}
        >
          <input
            id="file-upload"
            type="file"
            multiple
            accept={ALLOWED_EXTENSIONS.join(",")}
            className="hidden"
            onChange={(e) => handleUpload(e.target.files)}
          />
          <label htmlFor="file-upload" className="cursor-pointer">
            {uploading ? (
              <div className="flex flex-col items-center gap-2">
                <Loader2 className="w-8 h-8 text-violet-500 animate-spin" />
                <p className="text-sm font-medium text-gray-600 dark:text-gray-300">Uploading…</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <Upload className="w-8 h-8 text-gray-400 dark:text-gray-500" />
                <p className="text-sm font-medium text-gray-600 dark:text-gray-300">
                  Drop files here or <span className="text-violet-600 dark:text-violet-400 underline">browse</span>
                </p>
                <p className="text-xs text-gray-400 dark:text-gray-500">
                  PDF, PNG, JPG, HEIC, TXT, MD — up to 20 MB each
                </p>
              </div>
            )}
          </label>
        </div>

        {uploadError && (
          <div className="flex items-center gap-2 p-3 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700/50">
            <XCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
            <p className="text-sm text-red-600 dark:text-red-400">{uploadError}</p>
          </div>
        )}

        {/* File List */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
          </div>
        ) : files.length === 0 ? (
          <div className="text-center py-12">
            <FolderOpen className="w-12 h-12 mx-auto text-gray-300 dark:text-gray-600 mb-3" />
            <p className="text-sm text-gray-500 dark:text-gray-400">No files uploaded yet</p>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              Upload personal reference documents to include them in your AI search results.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {files.map((f) => (
              <div
                key={f.file_id}
                className="flex items-center gap-3 p-4 rounded-xl border bg-white dark:bg-[#141414] border-gray-200 dark:border-[#2A2A2A]"
              >
                {fileIcon(f.content_type)}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
                    {f.filename}
                  </p>
                  <div className="flex items-center gap-3 mt-0.5">
                    <span className="text-xs text-gray-400 dark:text-gray-500">
                      {formatBytes(f.size_bytes)}
                    </span>
                    {f.chunk_count !== undefined && f.chunk_count > 0 && (
                      <span className="text-xs text-gray-400 dark:text-gray-500">
                        {f.chunk_count} chunks
                      </span>
                    )}
                    <span className="text-xs text-gray-400 dark:text-gray-500">
                      {new Date(f.uploaded_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
                {statusBadge(f.status, f.error)}
                <button
                  onClick={() => handleDelete(f.file_id)}
                  disabled={deletingId === f.file_id}
                  className="p-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-50"
                  title="Delete file"
                >
                  {deletingId === f.file_id ? (
                    <Loader2 className="w-4 h-4 text-red-400 animate-spin" />
                  ) : (
                    <Trash2 className="w-4 h-4 text-red-400" />
                  )}
                </button>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

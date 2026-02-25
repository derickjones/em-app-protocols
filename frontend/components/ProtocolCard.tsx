"use client";

import React, { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

export interface ProtocolCardData {
  protocol_id: string;
  enterprise_id: string;
  ed_id: string | null;
  bundle_id: string;
  summary: string;
  pdf_url: string;
  images: { page: number; url: string }[];
  relevance_score: number;
}

interface ProtocolCardProps {
  card: ProtocolCardData;
  darkMode: boolean;
}

export default function ProtocolCard({ card, darkMode }: ProtocolCardProps) {
  const [currentPage, setCurrentPage] = useState(0);
  const images = card.images || [];

  const displayName = card.protocol_id
    .replace(/_/g, " ")
    .replace(/\.pdf$/i, "")
    .replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div
      className={`rounded-2xl overflow-hidden shadow-sm transition-all duration-200 ${
        darkMode
          ? "bg-neutral-900 border border-neutral-800"
          : "bg-white border border-gray-200"
      }`}
    >
      {/* Image Carousel */}
      {images.length > 0 && (
        <div className="relative bg-black/5">
          <div className="flex items-center justify-center h-72 overflow-hidden">
            <img
              src={images[currentPage]?.url}
              alt={`${displayName} — Page ${images[currentPage]?.page}`}
              className="max-h-full max-w-full object-contain"
              loading="lazy"
            />
          </div>
          {images.length > 1 && (
            <>
              <button
                onClick={() => setCurrentPage((p) => Math.max(0, p - 1))}
                disabled={currentPage === 0}
                className="absolute left-2 top-1/2 -translate-y-1/2 bg-black/60 hover:bg-black/80 disabled:opacity-30 text-white rounded-full w-8 h-8 flex items-center justify-center transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={() =>
                  setCurrentPage((p) => Math.min(images.length - 1, p + 1))
                }
                disabled={currentPage === images.length - 1}
                className="absolute right-2 top-1/2 -translate-y-1/2 bg-black/60 hover:bg-black/80 disabled:opacity-30 text-white rounded-full w-8 h-8 flex items-center justify-center transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
              <div className="absolute bottom-2 left-1/2 -translate-x-1/2 bg-black/60 text-white text-xs px-2 py-1 rounded-full">
                Page {images[currentPage]?.page} · {currentPage + 1} / {images.length}
              </div>
            </>
          )}
        </div>
      )}

      {/* Card Body */}
      <div className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h3
              className={`font-semibold text-base ${
                darkMode ? "text-white" : "text-gray-900"
              }`}
            >
              {displayName}
            </h3>
            <p
              className={`text-xs mt-0.5 ${
                darkMode ? "text-gray-500" : "text-gray-400"
              }`}
            >
              {card.ed_id || "—"} › {card.bundle_id}
            </p>
          </div>
        </div>

        <p
          className={`text-sm mt-3 leading-relaxed ${
            darkMode ? "text-gray-300" : "text-gray-600"
          }`}
        >
          {card.summary}
        </p>

        <a
          href={card.pdf_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 mt-4 text-sm text-blue-500 hover:text-blue-400 transition-colors"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
            />
          </svg>
          View Full Protocol (PDF)
        </a>
      </div>
    </div>
  );
}

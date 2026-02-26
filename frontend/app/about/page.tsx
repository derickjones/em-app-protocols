"use client";

import Link from "next/link";
import { Stethoscope, Brain, Zap, FileText, Users } from "lucide-react";

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-white text-gray-900 font-sans">
      <div className="max-w-3xl mx-auto px-6 py-16">
        {/* Header */}
        <Link href="/" className="text-sm text-blue-500 hover:text-blue-600 transition-colors">
          ← Back to EM Protocols
        </Link>

        <h1 className="text-3xl font-bold mt-6 mb-2">About EM Protocols</h1>
        <p className="text-sm text-gray-400 mb-10">AI-powered emergency medicine clinical decision support</p>

        {/* What It Is */}
        <section className="mb-10">
          <h2 className="text-xl font-semibold mb-3">What We Do</h2>
          <p className="text-sm leading-relaxed text-gray-700 mb-3">
            EM Protocols is a clinical decision support tool built for emergency medicine. It gives physicians, APPs, nurses, and trainees instant, searchable access to their department&apos;s clinical protocols alongside the best open-access emergency medicine literature — all in one place, with answers in under two seconds.
          </p>
          <p className="text-sm leading-relaxed text-gray-700">
            Instead of navigating clunky hospital websites or clicking through PDFs during a critical patient encounter, clinicians can ask a plain-language question and get a cited, actionable answer with the relevant flowcharts and algorithms displayed prominently.
          </p>
        </section>

        {/* How It Works */}
        <section className="mb-10">
          <h2 className="text-xl font-semibold mb-3">How It Works</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="border border-gray-200 rounded-xl p-4 flex gap-3">
              <FileText className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-semibold">Protocol Ingestion</h3>
                <p className="text-xs text-gray-500 mt-1">Hospitals upload their protocols as PDFs. We extract all text, images, flowcharts, and algorithms automatically.</p>
              </div>
            </div>
            <div className="border border-gray-200 rounded-xl p-4 flex gap-3">
              <Brain className="w-5 h-5 text-purple-500 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-semibold">AI-Powered Search</h3>
                <p className="text-xs text-gray-500 mt-1">Google Vertex AI indexes everything. When you ask a question, the most relevant content is retrieved in milliseconds.</p>
              </div>
            </div>
            <div className="border border-gray-200 rounded-xl p-4 flex gap-3">
              <Zap className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-semibold">Instant Answers</h3>
                <p className="text-xs text-gray-500 mt-1">Gemini 2.0 Flash synthesizes a concise, cited answer from the retrieved content — streamed to you in real time.</p>
              </div>
            </div>
            <div className="border border-gray-200 rounded-xl p-4 flex gap-3">
              <Stethoscope className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-semibold">Visual-First</h3>
                <p className="text-xs text-gray-500 mt-1">Flowcharts, algorithms, and protocol diagrams are displayed prominently alongside every answer, with clickable PDF citations.</p>
              </div>
            </div>
          </div>
        </section>

        {/* Who It's For */}
        <section className="mb-10">
          <h2 className="text-xl font-semibold mb-3">Who It&apos;s For</h2>
          <p className="text-sm leading-relaxed text-gray-700 mb-3">
            EM Protocols is designed for healthcare professionals working in emergency medicine:
          </p>
          <ul className="text-sm text-gray-700 space-y-1.5 ml-4 list-disc">
            <li>Emergency Physicians</li>
            <li>Advanced Practice Providers (PAs, NPs)</li>
            <li>Emergency Department Nurses</li>
            <li>Residents and Fellows</li>
            <li>Medical Students on EM rotations</li>
          </ul>
        </section>

        {/* Knowledge Sources */}
        <section className="mb-10">
          <h2 className="text-xl font-semibold mb-3">Knowledge Sources</h2>
          <p className="text-sm leading-relaxed text-gray-700 mb-3">
            Beyond your department&apos;s local protocols, EM Protocols searches across the best open-access emergency medicine resources:
          </p>
          <ul className="text-sm text-gray-700 space-y-1.5 ml-4 list-disc">
            <li><strong>WikEM</strong> — ~5,000 emergency medicine topic pages</li>
            <li><strong>PMC Open Access</strong> — ~18,000 peer-reviewed EM journal articles from 11 journals</li>
            <li><strong>LITFL</strong> — ~7,900 pages covering EM, critical care, toxicology, and ECG education</li>
            <li><strong>REBEL EM</strong> — ~1,350 evidence-based EM reviews</li>
            <li><strong>ALiEM</strong> — ~260 PV clinical reference cards and MEdIC case discussions</li>
          </ul>
          <p className="text-sm leading-relaxed text-gray-700 mt-3">
            All external content is used under Creative Commons licenses with full attribution. See our <Link href="/legal" className="text-blue-500 hover:underline">Legal &amp; Disclaimer</Link> page for complete licensing details.
          </p>
        </section>

        {/* Founders */}
        <section className="mb-10">
          <h2 className="text-xl font-semibold mb-3">Co-Founders</h2>
          <div className="space-y-4">
            <div className="border border-gray-200 rounded-xl p-5 flex gap-4 items-start">
              <Users className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-semibold">Jake Morey, MD, MBA</h3>
                <p className="text-xs text-gray-500 mt-1">Co-Founder</p>
              </div>
            </div>
            <div className="border border-gray-200 rounded-xl p-5 flex gap-4 items-start">
              <Users className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-semibold">Derick Jones, MD, MBA, MHI</h3>
                <p className="text-xs text-gray-500 mt-1">Co-Founder &amp; Technical Lead</p>
              </div>
            </div>
          </div>
        </section>

        {/* Version */}
        <div className="border-t border-gray-200 pt-6 text-xs text-gray-400">
          EM Protocols v1.0 · © {new Date().getFullYear()} EM Protocols. All rights reserved.
        </div>
      </div>
    </div>
  );
}

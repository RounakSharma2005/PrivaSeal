'use client'

import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import TextAnalyzer from "@/components/TextAnalyzer";
import dynamic from "next/dynamic";

const PdfAnalyzer = dynamic(() => import("@/components/PdfAnalyzer"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center p-12">
      <div className="size-6 animate-spin rounded-full border-2 border-[#EAEAEA] border-t-[#2F3437]" />
    </div>
  ),
});

export default function Home() {
  const [activeTab, setActiveTab] = useState('text')

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <header className="shrink-0 border-b border-[#EAEAEA] bg-white/80 backdrop-blur-sm">
        <div className="mx-auto flex h-14 max-w-4xl items-center px-6">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold tracking-tight text-[#2F3437]">Privaseal</span>
            <span className="hidden rounded-full bg-[#F1F0ED] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-[#787774] sm:inline">
              Trust &amp; Explainability
            </span>
          </div>
        </div>
      </header>
      <main className="flex-1 flex flex-col overflow-hidden min-h-0">
        {/* Hero banner — shared across tabs */}
        <div className="shrink-0 bg-[url('/images/bg.png')] bg-cover bg-center py-6 px-5">
          <div className="mx-auto max-w-4xl space-y-1">
            <h1 className="font-heading text-2xl tracking-tight text-[#2F3437] sm:text-3xl">
              Understand every redaction.
            </h1>
            <p className="max-w-2xl text-sm leading-relaxed text-[#787774]">
              Paste your text or upload a PDF. See exactly what gets flagged, why, and how it&apos;s redacted.
              No black boxes — every decision comes with an explanation.
            </p>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto min-h-0 px-6 py-6">
          <div className="mx-auto w-full">
            <AnimatePresence mode="wait">
              {activeTab === 'text' ? (
                <motion.div
                  key="text"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.15 }}
                >
                  <TextAnalyzer activeTab={activeTab} onTabChange={setActiveTab} />
                </motion.div>
              ) : (
                <motion.div
                  key="pdf"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.15 }}
                >
                  <PdfAnalyzer activeTab={activeTab} onTabChange={setActiveTab} />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </main>
    </div>
  );
}

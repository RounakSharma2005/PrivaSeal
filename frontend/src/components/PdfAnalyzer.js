
'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import { uploadPdf, exportPdf, generatePolicy, auditRedactedText, refinePolicy } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import {
  AlertCircle,
  CheckCircle2,
  Eye,
  EyeOff,
  FileText,
  Loader2,
  Shield,
  Download,
  RotateCcw,
  ChevronRight,
  Info,
  Sparkles,
  X,
  BookOpen,
  Search,
  ShieldCheck,
  FileUp,
  File,
  ZoomIn,
  ZoomOut,
  ChevronLeft,
  ChevronDown,
  ChevronUp,
  Scan,
} from 'lucide-react'

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url
).toString()

const riskColors = {
  high: 'bg-[#FDEBEC] text-[#9F2F2D] border-[#FDEBEC]',
  medium: 'bg-[#FBF3DB] text-[#956400] border-[#FBF3DB]',
  low: 'bg-[#EDF3EC] text-[#346538] border-[#EDF3EC]',
}

const typeColors = {
  PERSON: 'bg-[#E1F3FE] text-[#1F6C9F]',
  EMAIL_ADDRESS: 'bg-[#FDEBEC] text-[#9F2F2D]',
  PHONE_NUMBER: 'bg-[#FBF3DB] text-[#956400]',
  CREDIT_CARD: 'bg-[#FDEBEC] text-[#9F2F2D]',
  ADDRESS: 'bg-[#EDF3EC] text-[#346538]',
  DATE_OF_BIRTH: 'bg-[#E1F3FE] text-[#1F6C9F]',
  US_SSN: 'bg-[#FDEBEC] text-[#9F2F2D]',
  IP_ADDRESS: 'bg-[#E1F3FE] text-[#1F6C9F]',
  IBAN_CODE: 'bg-[#EDF3EC] text-[#346538]',
  EMPLOYEE_ID: 'bg-[#FBF3DB] text-[#956400]',
  URL: 'bg-[#E1F3FE] text-[#1F6C9F]',
  INDIAN_PHONE: 'bg-[#FBF3DB] text-[#956400]',
  AADHAAR: 'bg-[#FDEBEC] text-[#9F2F2D]',
  PAN: 'bg-[#FDEBEC] text-[#9F2F2D]',
  UPI_ID: 'bg-[#FBF3DB] text-[#956400]',
  IFSC: 'bg-[#E1F3FE] text-[#1F6C9F]',
  DEFAULT: 'bg-[#F1F0ED] text-[#2F3437]',
}

function getTypeColor(type) {
  return typeColors[type] || typeColors.DEFAULT
}

const policySectionStyles = {
  hide: 'border-[#FDEBEC] bg-[#FFF8F8]',
  keep: 'border-[#EDF3EC] bg-[#F8FBF8]',
  review: 'border-[#FBF3DB] bg-[#FFFCF5]',
}

const policySectionIcons = {
  hide: EyeOff,
  keep: Eye,
  review: Search,
}

const policySectionLabels = {
  hide: 'Will be hidden',
  keep: 'Will be kept',
  review: 'Will be reviewed',
}

function PolicySection({ type, items }) {
  const Icon = policySectionIcons[type]
  return (
    <div className={`rounded-lg border p-3 ${policySectionStyles[type]}`}>
      <div className="flex items-center gap-1.5 mb-2">
        <Icon className="size-3.5" />
        <p className="text-xs font-medium uppercase tracking-wider">
          {policySectionLabels[type]}
        </p>
      </div>
      {items.length === 0 ? (
        <p className="text-xs opacity-60">None specified</p>
      ) : (
        <ul className="space-y-0.5">
          {items.map((item, i) => (
            <li key={i} className="text-sm">{item}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

function AnonymizedText({ text }) {
  const parts = text.split(/(<[^>]+>)/g)
  return (
    <span>
      {parts.map((part, i) => {
        if (part.startsWith('<') && part.endsWith('>')) {
          const type = part.slice(1, -1)
          return (
            <span
              key={i}
              className="inline-flex items-center rounded-full bg-[#2F3437] px-2 py-0.5 mx-0.5 font-mono text-[11px] font-medium text-white"
            >
              {type}
            </span>
          )
        }
        return <span key={i}>{part}</span>
      })}
    </span>
  )
}

function HighlightedText({ text, entities, onEntityClick }) {
  if (!entities || entities.length === 0) {
    return <span>{text}</span>
  }

  const sorted = [...entities].sort((a, b) => a.start - b.start)
  const parts = []
  let lastIndex = 0

  for (const entity of sorted) {
    if (entity.start > lastIndex) {
      parts.push(
        <span key={`t-${lastIndex}`}>{text.slice(lastIndex, entity.start)}</span>
      )
    }

    const value = text.slice(entity.start, entity.end)
    parts.push(
      <button
        key={`e-${entity.start}`}
        onClick={() => onEntityClick(entity)}
        className={`inline-flex items-center gap-1 rounded px-1 -mx-0.5 cursor-pointer transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 ${getTypeColor(entity.type)}`}
        title={`${entity.type} — click for explanation`}
      >
        {value}
        <Info className="size-3 shrink-0 opacity-60" />
      </button>
    )

    lastIndex = entity.end
  }

  if (lastIndex < text.length) {
    parts.push(<span key={`t-${lastIndex}`}>{text.slice(lastIndex)}</span>)
  }

  return <span>{parts}</span>
}

export default function PdfAnalyzer({ activeTab, onTabChange }) {
  const [file, setFile] = useState(null)
  const [fileType, setFileType] = useState(null)
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [selectedEntity, setSelectedEntity] = useState(null)
  const [exporting, setExporting] = useState(false)
  const [auditing, setAuditing] = useState(false)
  const [auditResult, setAuditResult] = useState(null)

  const [purpose, setPurpose] = useState('')
  const [policy, setPolicy] = useState(null)
  const [activePolicyTab, setActivePolicyTab] = useState('hide')
  const [generatingPolicy, setGeneratingPolicy] = useState(false)
  const [refiningPolicy, setRefiningPolicy] = useState(false)
  const [refinePrompt, setRefinePrompt] = useState('')
  const [policyGeneratedFor, setPolicyGeneratedFor] = useState('')

  const [numPages, setNumPages] = useState(null)
  const [pageNumber, setPageNumber] = useState(1)
  const [scale, setScale] = useState(1.0)
  const [pdfLoading, setPdfLoading] = useState(false)
  const [pdfError, setPdfError] = useState(null)

  const [decisions, setDecisions] = useState({})
  const [includeEvidence, setIncludeEvidence] = useState(false)
  const [activeSection, setActiveSection] = useState('overview')
  const fileInputRef = useRef(null)

  const navItems = [
    { id: 'overview', label: 'Overview' },
    { id: 'audit', label: 'Audit' },
    { id: 'entities', label: 'Entities' },
    { id: 'comparison', label: 'Extracted Text' },
    { id: 'decisions', label: 'Redaction Decisions' },
    { id: 'actions', label: 'Actions' },
  ]

  const handleGeneratePolicy = useCallback(async () => {
    if (!purpose.trim()) return
    setGeneratingPolicy(true)
    setError(null)
    try {
      const data = await generatePolicy(purpose)
      setPolicy(data.policy)
      setPolicyGeneratedFor(data.purpose)
    } catch (err) {
      setError('Policy generation failed: ' + err.message)
    } finally {
      setGeneratingPolicy(false)
    }
  }, [purpose])

  const handleRefinePolicy = useCallback(async () => {
    if (!refinePrompt.trim() || !policy) return
    setRefiningPolicy(true)
    setError(null)
    try {
      const data = await refinePolicy(policy, refinePrompt)
      setPolicy(data.policy)
      setRefinePrompt('')
    } catch (err) {
      setError('Policy refinement failed: ' + err.message)
    } finally {
      setRefiningPolicy(false)
    }
  }, [refinePrompt, policy])

  const handleRemovePolicy = useCallback(() => {
    setPolicy(null)
    setPurpose('')
    setPolicyGeneratedFor('')
  }, [])

  const handleAnalyze = useCallback(async () => {
    if (!file) return
    setUploading(true)
    setLoading(true)
    setError(null)
    setResult(null)
    setAuditResult(null)
    setDecisions({})

    try {
      const params = {}
      if (policy) {
        params.policy = policy
      }
      if (policy && policyGeneratedFor) {
        params.purpose = policyGeneratedFor
      }

      const data = await uploadPdf(file, params)
      setResult(data)

      const initialDecisions = {}
      ;(data.entities || []).forEach((entity, index) => {
        const key = `${entity.type}-${entity.start}-${entity.end}-${index}`
        initialDecisions[key] = {
          ...entity,
          action: entity.recommendation || 'redact',
        }
      })
      setDecisions(initialDecisions)
    } catch (err) {
      setError(err.message || 'Unable to analyze the uploaded file.')
    } finally {
      setUploading(false)
      setLoading(false)
    }
  }, [file, policy, policyGeneratedFor])


const handleExport = useCallback(async () => {
  if (!result || !file) return

  // Prevent exporting while any entity still requires review.
  const unresolvedReviews = Object.values(decisions).filter(
    (decision) => decision.action === 'review'
  )

  if (unresolvedReviews.length > 0) {
    setError(
      `Please resolve all ${unresolvedReviews.length} entity review(s) before exporting. Choose Redact, Anonymize, or Keep for each one.`
    )
    return
  }

  setExporting(true)
  setError(null)

  try {
    if (fileType === 'txt') {
      const output = (result.entities || []).reduce((currentText, entity, index) => {
        const key = `${entity.type}-${entity.start}-${entity.end}-${index}`
        const decision = decisions[key]

        if (!decision || decision.action === 'keep') return currentText

        const replacement =
          decision.action === 'anonymize'
            ? `<${entity.type}>`
            : '[REDACTED]'

        return currentText.slice(0, entity.start) +
          replacement +
          currentText.slice(entity.end)
      }, result.original_text)

      const blob = new Blob([output], {
        type: 'text/plain;charset=utf-8',
      })

      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')

      a.href = url
      a.download = 'redacted_document.txt'

      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)

      URL.revokeObjectURL(url)

    } else {
      const redactions = Object.values(decisions)
        .filter((decision) =>
          ['redact', 'anonymize'].includes(decision.action)
        )
        .map((decision) => ({
          value: decision.value,
          type: decision.type,
          action: decision.action,
          start: decision.start,
          end: decision.end,
        }))

      if (redactions.length === 0) {
        setError(
          'No entities are selected for redaction. Change at least one decision before exporting.'
        )
        return
      }

      // Generate PDF with optional privacy evidence report.
      const blob = await exportPdf(file, redactions, {
        includeEvidence,
      })

      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')

      a.href = url
      a.download = includeEvidence
        ? 'privaseal_export.zip'
        : 'redacted_document.pdf'

      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)

      URL.revokeObjectURL(url)
    }

  } catch (err) {
    setError('Export failed: ' + err.message)
  } finally {
    setExporting(false)
  }
}, [result, file, fileType, decisions, includeEvidence])


  const handleAudit = useCallback(async () => {
    if (!result) return

    setAuditing(true)
    setAuditResult(null)
    setError(null)

    try {
      const data = await auditRedactedText(result.anonymized_text, {
        policy: policy || undefined,
      })
      setAuditResult(data)
    } catch (err) {
      setError('Audit failed: ' + err.message)
    } finally {
      setAuditing(false)
    }
  }, [result, policy])

  const handleReset = useCallback(() => {
    setFile(null)
    setFileType(null)
    setResult(null)
    setError(null)
    setSelectedEntity(null)
    setAuditResult(null)
    setDecisions({})
    setNumPages(null)
    setPageNumber(1)
    setPdfError(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }, [])

  const handleFileChange = useCallback((selectedFile) => {
    if (!selectedFile) return

    const extension = selectedFile.name.split('.').pop()?.toLowerCase()
    if (!['pdf', 'txt'].includes(extension)) {
      setError('Please upload a PDF or TXT file.')
      return
    }

    setFile(selectedFile)
    setFileType(extension)
    setResult(null)
    setError(null)
    setAuditResult(null)
    setDecisions({})
    setNumPages(null)
    setPageNumber(1)
    setPdfError(null)
  }, [])

  const onDocumentLoadSuccess = useCallback(({ numPages: pages }) => {
    setNumPages(pages)
    setPageNumber(1)
    setPdfLoading(false)
    setPdfError(null)
  }, [])

  const onDocumentLoadError = useCallback((err) => {
    setPdfLoading(false)
    setPdfError(err.message || 'Unable to preview this PDF.')
  }, [])

  const updateDecision = useCallback((key, action) => {
    setDecisions((previous) => ({
      ...previous,
      [key]: {
        ...previous[key],
        action,
      },
    }))
  }, [])

  const scrollToSection = (id) => {
    setActiveSection(id)
    document.getElementById(id)?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    })
  }

  useEffect(() => {
    if (!result) return

    const observers = []
    for (const item of navItems) {
      const element = document.getElementById(item.id)
      if (!element) continue

      const observer = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) setActiveSection(item.id)
        },
        { rootMargin: '-20% 0px -60% 0px', threshold: 0 }
      )

      observer.observe(element)
      observers.push(observer)
    }

    return () => observers.forEach((observer) => observer.disconnect())
  }, [result])

  const entityEntries = Object.entries(decisions)
  const redactionCount = entityEntries.filter(([, item]) =>
    ['redact', 'anonymize'].includes(item.action)
  ).length
  const keepCount = entityEntries.filter(([, item]) => item.action === 'keep').length
  const reviewCount = entityEntries.filter(([, item]) => item.action === 'review').length

  return (
    <div className="w-full">
      <div className="grid grid-cols-1 md:grid-cols-[1fr_minmax(auto,800px)_1fr] gap-8 max-w-[1600px] mx-auto">
        {/* Left navigation */}
        <div className="hidden md:flex justify-end items-start">
          {result && (
            <nav className="sticky top-6 w-[10rem]">
              <div className="space-y-1">
                {navItems.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => scrollToSection(item.id)}
                    className={`w-full rounded-md px-3 py-1.5 text-left text-xs font-medium transition-colors ${
                      activeSection === item.id
                        ? 'bg-[#F1F0ED] text-[#2F3437]'
                        : 'text-[#787774] hover:bg-[#F1F0ED] hover:text-[#2F3437]'
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </nav>
          )}
        </div>

        {/* Main content */}
        <div className="min-w-0 space-y-8">
          {!result && (
            <Card className="border-[#EAEAEA] shadow-none">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Shield className="size-5 text-[#2F3437]" />
                    <CardTitle className="font-heading text-xl tracking-tight">
                      Upload a document for analysis
                    </CardTitle>
                  </div>

                  <div className="flex items-center gap-1 rounded-lg bg-[#F1F0ED] p-0.5">
                    {[{ id: 'text', label: 'Text' }, { id: 'pdf', label: 'PDF' }].map((tab) => (
                      <button
                        key={tab.id}
                        onClick={() => onTabChange(tab.id)}
                        className={`rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
                          activeTab === tab.id
                            ? 'bg-white text-[#2F3437] shadow-sm'
                            : 'text-[#787774] hover:text-[#2F3437]'
                        }`}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>
                </div>

                <CardDescription className="text-[#787774]">
                  Upload a PDF or TXT file and analyze it. You can optionally generate a privacy policy to guide redaction decisions.
                </CardDescription>
              </CardHeader>

              <CardContent className="space-y-4">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.txt,application/pdf,text/plain"
                  className="hidden"
                  onChange={(event) => handleFileChange(event.target.files?.[0])}
                />

                {!file ? (
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={(event) => {
                      event.preventDefault()
                      handleFileChange(event.dataTransfer.files?.[0])
                    }}
                    className="flex min-h-[220px] w-full flex-col items-center justify-center rounded-xl border-2 border-dashed border-[#D0CEC9] bg-[#FAFAF8] px-6 py-10 text-center transition-colors hover:border-[#787774] hover:bg-[#F7F6F3]"
                  >
                    <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-[#F1F0ED]">
                      <FileUp className="size-6 text-[#787774]" />
                    </div>
                    <p className="text-sm font-medium text-[#2F3437]">
                      Click to upload or drag and drop
                    </p>
                    <p className="mt-1 text-xs text-[#787774]">
                      PDF or TXT files
                    </p>
                  </button>
                ) : (
                  <div className="flex items-center gap-3 rounded-lg border border-[#EAEAEA] bg-white p-4">
                    <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-[#F1F0ED]">
                      <File className="size-5 text-[#787774]" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-[#2F3437]">
                        {file.name}
                      </p>
                      <p className="text-xs text-[#787774]">
                        {fileType?.toUpperCase()} · {(file.size / 1024).toFixed(1)} KB
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleReset}
                      className="text-[#787774] hover:text-[#9F2F2D]"
                    >
                      <X className="size-4" />
                    </Button>
                  </div>
                )}

                {/* Optional privacy policy */}
                <div className="rounded-lg border border-[#EAEAEA] bg-white px-4 py-3">
                  {!policy ? (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <BookOpen className="size-4 text-[#787774]" />
                        <span className="text-sm font-medium text-[#2F3437]">
                          Privacy Policy
                        </span>
                        <Badge variant="outline" className="border-0 bg-[#F1F0ED] text-[#787774] text-[10px]">
                          Optional
                        </Badge>
                      </div>

                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={purpose}
                          onChange={(event) => setPurpose(event.target.value)}
                          placeholder="e.g. Resume Review, Contract Analysis"
                          className="flex-1 rounded-lg border border-[#EAEAEA] bg-white px-3 py-2 text-sm text-[#2F3437] placeholder:text-[#B0AEAA] outline-none focus-visible:border-[#D0CEC9] focus-visible:ring-1 focus-visible:ring-[#D0CEC9]"
                          onKeyDown={(event) => event.key === 'Enter' && handleGeneratePolicy()}
                        />

                        <Button
                          onClick={handleGeneratePolicy}
                          disabled={!purpose.trim() || generatingPolicy}
                          variant="outline"
                          className="shrink-0 border-[#EAEAEA] text-[#2F3437]"
                        >
                          {generatingPolicy ? (
                            <Loader2 className="size-4 animate-spin" />
                          ) : (
                            <Sparkles className="size-4" />
                          )}
                          Generate
                        </Button>
                      </div>

                      <p className="text-xs text-[#B0AEAA]">
                        Generate a tailored policy if you want to control which detected entities are hidden, kept, or reviewed.
                      </p>
                    </div>
                  ) : (
                    <div className="flex items-center justify-between">
                      <div className="flex min-w-0 items-center gap-2">
                        <BookOpen className="size-4 shrink-0 text-[#346538]" />
                        <span className="truncate text-sm font-medium text-[#2F3437]">
                          Policy active for <span className="text-[#346538]">{policyGeneratedFor}</span>
                        </span>
                        <Badge variant="outline" className="rounded-full border-0 bg-[#EDF3EC] text-[#346538] text-[10px] font-medium">
                          Active
                        </Badge>
                      </div>
                      <Button
                        onClick={handleRemovePolicy}
                        variant="ghost"
                        size="sm"
                        className="h-7 shrink-0 px-2 text-[#787774] hover:text-[#9F2F2D]"
                      >
                        <X className="size-3.5" />
                      </Button>
                    </div>
                  )}
                </div>

                {error && (
                  <div className="flex items-start gap-3 rounded-lg border border-[#FDEBEC] bg-[#FFF8F8] p-3">
                    <AlertCircle className="mt-0.5 size-4 shrink-0 text-[#9F2F2D]" />
                    <p className="flex-1 text-sm text-[#9F2F2D]">{error}</p>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setError(null)}
                      className="h-6 px-2 text-[#9F2F2D]"
                    >
                      Dismiss
                    </Button>
                  </div>
                )}

                <div className="flex items-center justify-between">
                  <p className="text-xs text-[#B0AEAA]">
                    {file ? 'Ready to analyze' : 'No file selected'}
                    {!policy && (
                      <span className="ml-2">— Privacy policy is optional</span>
                    )}
                  </p>

                  <Button
                    onClick={handleAnalyze}
                    disabled={!file || uploading}
                    className="bg-[#111111] text-white hover:bg-[#333333]"
                  >
                    {uploading ? (
                      <>
                        <Loader2 className="size-4 animate-spin" />
                        Analyzing...
                      </>
                    ) : (
                      <>
                        <Scan className="size-4" />
                        Analyze Document
                      </>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Error display */}
          {result && error && (
            <Card className="border-[#FDEBEC] bg-[#FFF8F8] shadow-none">
              <CardContent className="flex items-start gap-3 pt-4">
                <AlertCircle className="mt-0.5 size-5 shrink-0 text-[#9F2F2D]" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-[#9F2F2D]">Operation failed</p>
                  <p className="mt-1 text-sm text-[#9F2F2D]/80">{error}</p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setError(null)}
                  className="text-[#9F2F2D]"
                >
                  Dismiss
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Results */}
          {result && (
            <>
              <Card id="overview" className="scroll-mt-24 border-[#EAEAEA] shadow-none">
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Shield className="size-5 text-[#2F3437]" />
                    <CardTitle className="font-heading text-xl tracking-tight">
                      Document Analysis Results
                    </CardTitle>
                  </div>
                  {result.overall_risk_summary && (
                    <CardDescription className="text-[#787774]">
                      {result.overall_risk_summary}
                    </CardDescription>
                  )}
                  {policyGeneratedFor && policy && (
                    <CardDescription className="mt-1 flex items-center gap-1.5 text-[#787774]">
                      <BookOpen className="size-3.5" />
                      Policy applied: <span className="text-[#2F3437]">{policyGeneratedFor}</span>
                    </CardDescription>
                  )}
                </CardHeader>

                <CardContent>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <div className="rounded-lg border border-[#EAEAEA] p-3">
                      <p className="text-xs text-[#787774]">Entities found</p>
                      <p className="mt-1 text-2xl font-semibold text-[#2F3437]">
                        {result.entities?.length || 0}
                      </p>
                    </div>
                    <div className="rounded-lg border border-[#EAEAEA] p-3">
                      <p className="text-xs text-[#787774]">Selected to redact</p>
                      <p className="mt-1 text-2xl font-semibold text-[#9F2F2D]">
                        {redactionCount}
                      </p>
                    </div>
                    <div className="rounded-lg border border-[#EAEAEA] p-3">
                      <p className="text-xs text-[#787774]">Kept visible</p>
                      <p className="mt-1 text-2xl font-semibold text-[#346538]">
                        {keepCount}
                      </p>
                    </div>
                    <div className="rounded-lg border border-[#EAEAEA] p-3">
                      <p className="text-xs text-[#787774]">Needs review</p>
                      <p className="mt-1 text-2xl font-semibold text-[#956400]">
                        {reviewCount}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Privacy audit */}
              <Card id="audit" className="scroll-mt-24 border-[#EAEAEA] shadow-none">
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="size-4 text-[#787774]" />
                    <CardTitle className="font-heading text-base tracking-tight">
                      Privacy Audit
                    </CardTitle>
                  </div>
                  <CardDescription>
                    Run an independent check on the analyzer's redacted text to find remaining identifiers.
                  </CardDescription>
                </CardHeader>

                <CardContent>
                  {!auditResult ? (
                    <Button
                      onClick={handleAudit}
                      disabled={auditing}
                      variant="outline"
                      className="border-[#EAEAEA] text-[#2F3437] hover:bg-[#F1F0ED]"
                    >
                      {auditing ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : (
                        <ShieldCheck className="size-4" />
                      )}
                      {auditing ? 'Running audit...' : 'Run Privacy Audit'}
                    </Button>
                  ) : (
                    <div className="space-y-4">
                      <div className="flex flex-wrap items-center gap-3">
                        <Badge
                          variant="secondary"
                          className={`rounded-full text-[11px] font-medium uppercase tracking-wider ${
                            auditResult.status === 'PASS'
                              ? 'bg-[#EDF3EC] text-[#346538]'
                              : 'bg-[#FBF3DB] text-[#956400]'
                          }`}
                        >
                          {auditResult.status}
                        </Badge>
                        <Badge
                          variant="secondary"
                          className={`rounded-full text-[11px] font-medium uppercase tracking-wider ${
                            auditResult.residual_risk === 'LOW'
                              ? 'bg-[#EDF3EC] text-[#346538]'
                              : auditResult.residual_risk === 'MEDIUM'
                                ? 'bg-[#FBF3DB] text-[#956400]'
                                : 'bg-[#FDEBEC] text-[#9F2F2D]'
                          }`}
                        >
                          Residual Risk: {auditResult.residual_risk}
                        </Badge>
                      </div>

                      {auditResult.result_summary && (
                        <p className="text-sm leading-relaxed text-[#787774]">
                          {auditResult.result_summary}
                        </p>
                      )}

                      {auditResult.remaining_identifiers?.length > 0 && (
                        <div className="space-y-2">
                          <p className="text-xs font-medium uppercase tracking-wider text-[#B0AEAA]">
                            Remaining Identifiers — {auditResult.remaining_identifiers.length}
                          </p>
                          {auditResult.remaining_identifiers.map((item, index) => (
                            <div key={index} className="rounded-lg border border-[#EAEAEA] bg-white p-3">
                              <p className="text-sm font-medium text-[#2F3437]">{item.value}</p>
                              <p className="mt-1 text-xs text-[#787774]">{item.reason}</p>
                              {item.recommendation && (
                                <p className="mt-1 text-xs text-[#9F2F2D]">{item.recommendation}</p>
                              )}
                            </div>
                          ))}
                        </div>
                      )}

                      <Button
                        onClick={handleAudit}
                        disabled={auditing}
                        variant="ghost"
                        size="sm"
                        className="text-[#787774] hover:text-[#2F3437]"
                      >
                        {auditing ? (
                          <Loader2 className="size-3.5 animate-spin" />
                        ) : (
                          <RotateCcw className="size-3.5" />
                        )}
                        Re-run
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Detected entities */}
              {result.entities?.length > 0 && (
                <Card id="entities" className="scroll-mt-24 border-[#EAEAEA] shadow-none">
                  <CardHeader>
                    <CardTitle className="font-heading text-base tracking-tight">
                      Detected Entities — {result.entities.length} found
                    </CardTitle>
                    <CardDescription>
                      Select an entity to review its explanation and redaction decision.
                    </CardDescription>
                  </CardHeader>

                  <CardContent>
                    <div className="flex flex-wrap gap-2">
                      {result.entities.map((entity, index) => (
                        <button
                          key={`${entity.type}-${entity.start}-${index}`}
                          onClick={() => setSelectedEntity(entity)}
                          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-all hover:opacity-80 ${getTypeColor(entity.type)}`}
                        >
                          <span>{entity.value}</span>
                          <span className="text-[10px] opacity-60">{entity.type}</span>
                          <ChevronRight className="size-3 opacity-40" />
                        </button>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Extracted text */}
              <Card id="comparison" className="scroll-mt-24 border-[#EAEAEA] shadow-none">
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <FileText className="size-4 text-[#787774]" />
                    <CardTitle className="font-heading text-base tracking-tight">
                      Extracted Document Text
                    </CardTitle>
                  </div>
                  <CardDescription>
                    Detected entities are highlighted. Select one to inspect its details.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="max-h-[500px] overflow-y-auto rounded-lg border border-[#EAEAEA] bg-white p-4 text-sm leading-relaxed text-[#2F3437] whitespace-pre-wrap">
                    <HighlightedText
                      text={result.original_text || ''}
                      entities={result.entities || []}
                      onEntityClick={setSelectedEntity}
                    />
                  </div>
                </CardContent>
              </Card>

              {/* Redaction decisions */}
              <Card id="decisions" className="scroll-mt-24 border-[#EAEAEA] shadow-none">
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="size-4 text-[#787774]" />
                    <CardTitle className="font-heading text-base tracking-tight">
                      Review Redaction Decisions
                    </CardTitle>
                  </div>
                  <CardDescription>
                    Choose whether each detected entity should be redacted, anonymized, kept, or reviewed.
                  </CardDescription>
                </CardHeader>

                <CardContent>
                  {entityEntries.length === 0 ? (
                    <div className="rounded-lg border border-[#EAEAEA] bg-[#FAFAF8] p-6 text-center">
                      <CheckCircle2 className="mx-auto size-6 text-[#346538]" />
                      <p className="mt-2 text-sm font-medium text-[#2F3437]">
                        No entities detected
                      </p>
                      <p className="mt-1 text-xs text-[#787774]">
                        No detected entities require a redaction decision.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {entityEntries.map(([key, entity]) => (
                        <div
                          key={key}
                          className="rounded-lg border border-[#EAEAEA] bg-white p-4"
                        >
                          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="font-medium text-[#2F3437]">
                                  {entity.value}
                                </span>
                                <Badge
                                  variant="outline"
                                  className={`rounded-full border-0 text-[10px] font-medium uppercase tracking-wider ${getTypeColor(entity.type)}`}
                                >
                                  {entity.type}
                                </Badge>
                                <Badge
                                  variant="secondary"
                                  className={`rounded-full text-[10px] font-medium uppercase tracking-wider ${riskColors[entity.risk_level] || ''}`}
                                >
                                  {entity.risk_level || 'unknown'} risk
                                </Badge>
                              </div>

                              {entity.explanation && (
                                <p className="mt-2 text-sm text-[#787774]">
                                  {entity.explanation}
                                </p>
                              )}

                              {entity.applied_policy_rule && (
                                <p className="mt-1 text-xs text-[#787774]">
                                  Policy rule: {entity.applied_policy_rule}
                                </p>
                              )}
                            </div>

                            <div className="flex shrink-0 flex-wrap gap-1">
                              {[
                                { value: 'redact', label: 'Redact' },
                                { value: 'anonymize', label: 'Anonymize' },
                                { value: 'keep', label: 'Keep' },
                                { value: 'review', label: 'Review' },
                              ].map((option) => (
                                <Button
                                  key={option.value}
                                  size="sm"
                                  variant={entity.action === option.value ? 'default' : 'outline'}
                                  onClick={() => updateDecision(key, option.value)}
                                  className={
                                    entity.action === option.value
                                      ? 'bg-[#2F3437] text-white hover:bg-[#444444]'
                                      : 'border-[#EAEAEA] text-[#787774]'
                                  }
                                >
                                  {option.label}
                                </Button>
                              ))}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Actions */}
              <div id="actions" className="scroll-mt-24 flex flex-wrap items-center justify-center gap-3 pb-8">
                {fileType === 'pdf' && (
  <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-[#EAEAEA] px-4 py-3">
    <input
      type="checkbox"
      checked={includeEvidence}
      onChange={(e) => setIncludeEvidence(e.target.checked)}
      disabled={exporting}
      className="size-4 accent-[#346538]"
    />

    <div>
      <p className="text-sm font-medium text-[#2F3437]">
        Include Privacy Evidence Report
      </p>
      <p className="text-xs text-[#787774]">
        Download sanitized PDF with JSON evidence in a ZIP
      </p>
    </div>
  </label>
)}
                <Button
                  onClick={handleExport}
                  disabled={exporting || redactionCount === 0}
                  className="bg-[#111111] text-white hover:bg-[#333333]"
                >
                  {exporting ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Download className="size-4" />
                  )}
                  Export Redacted Document
                </Button>

                <Button
                  onClick={handleReset}
                  variant="outline"
                  className="border-[#EAEAEA] text-[#2F3437]"
                >
                  <RotateCcw className="size-4" />
                  Analyze Another File
                </Button>
              </div>
            </>
          )}
        </div>

        {/* Right policy panel */}
        <div className="hidden md:flex justify-end items-start">
          <AnimatePresence>
            {policy && (
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ duration: 0.2 }}
                className="sticky top-6 w-[18rem]"
              >
                <div className="flex flex-col space-y-3 rounded-lg border border-[#EAEAEA] bg-white p-4">
                  <div className="flex shrink-0 items-center justify-between">
                    <p className="text-xs font-medium uppercase tracking-wider text-[#787774]">
                      Policy for: <span className="normal-case text-[#2F3437]">{policyGeneratedFor}</span>
                    </p>
                    <Button
                      onClick={handleRemovePolicy}
                      variant="ghost"
                      size="sm"
                      className="h-7 shrink-0 px-2 text-[#787774] hover:text-[#9F2F2D]"
                    >
                      <X className="size-3.5" />
                    </Button>
                  </div>

                  <div className="flex shrink-0 gap-1 rounded-lg bg-[#F1F0ED] p-0.5">
                    {[
                      { id: 'hide', label: 'Hide' },
                      { id: 'keep', label: 'Keep' },
                      { id: 'review', label: 'Review' },
                    ].map((tab) => (
                      <button
                        key={tab.id}
                        onClick={() => setActivePolicyTab(tab.id)}
                        className={`flex-1 rounded-md px-2 py-1 text-xs font-medium transition-all ${
                          activePolicyTab === tab.id
                            ? 'bg-white text-[#2F3437] shadow-sm'
                            : 'text-[#787774] hover:text-[#2F3437]'
                        }`}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>

                  <div className="min-h-0 flex-1 overflow-y-auto pb-2">
                    <PolicySection
                      type={activePolicyTab}
                      items={policy[activePolicyTab] || []}
                    />
                  </div>

                  <div className="flex shrink-0 items-center gap-2 border-t border-[#EAEAEA] pt-3">
                    <div className="relative flex-1">
                      <input
                        type="text"
                        value={refinePrompt}
                        onChange={(event) => setRefinePrompt(event.target.value)}
                        onKeyDown={(event) => event.key === 'Enter' && handleRefinePolicy()}
                        placeholder="Refine policy (e.g. keep names)"
                        className="w-full rounded-md border border-[#EAEAEA] bg-[#F1F0ED]/50 px-3 py-1.5 pr-8 text-xs text-[#2F3437] placeholder:text-[#B0AEAA] focus:border-[#2F3437] focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#2F3437] transition-all"
                        disabled={refiningPolicy}
                      />
                      <Button
                        onClick={handleRefinePolicy}
                        disabled={!refinePrompt.trim() || refiningPolicy}
                        className="absolute right-1 top-1 h-6 w-6 rounded-sm bg-transparent p-0 text-[#787774] hover:bg-[#F1F0ED] hover:text-[#2F3437]"
                        variant="ghost"
                      >
                        {refiningPolicy ? (
                          <Loader2 className="size-3 animate-spin" />
                        ) : (
                          <Sparkles className="size-3" />
                        )}
                      </Button>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* PDF preview sheet */}
      {file && fileType === 'pdf' && !result && (
        <Sheet>
          <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-2xl">
            <SheetHeader>
              <SheetTitle>PDF Preview</SheetTitle>
              <SheetDescription>
                Preview the selected PDF before analysis.
              </SheetDescription>
            </SheetHeader>

            <div className="mt-4">
              <div className="flex items-center justify-center gap-2 border-b border-[#EAEAEA] pb-3">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={pageNumber <= 1}
                  onClick={() => setPageNumber((page) => Math.max(1, page - 1))}
                >
                  <ChevronLeft className="size-4" />
                </Button>
                <span className="text-xs text-[#787774]">
                  Page {pageNumber}{numPages ? ` of ${numPages}` : ''}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={numPages ? pageNumber >= numPages : true}
                  onClick={() => setPageNumber((page) => Math.min(numPages || page, page + 1))}
                >
                  <ChevronRight className="size-4" />
                </Button>
                <Separator orientation="vertical" className="mx-1 h-5" />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setScale((value) => Math.max(0.5, value - 0.1))}
                >
                  <ZoomOut className="size-4" />
                </Button>
                <span className="w-10 text-center text-xs text-[#787774]">
                  {Math.round(scale * 100)}%
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setScale((value) => Math.min(2, value + 0.1))}
                >
                  <ZoomIn className="size-4" />
                </Button>
              </div>

              {pdfError && (
                <p className="mt-4 rounded-lg bg-[#FFF8F8] p-3 text-sm text-[#9F2F2D]">
                  {pdfError}
                </p>
              )}

              <div className="mt-4 flex justify-center">
                <Document
                  file={file}
                  onLoadSuccess={onDocumentLoadSuccess}
                  onLoadError={onDocumentLoadError}
                  loading={
                    <div className="flex items-center gap-2 py-10 text-sm text-[#787774]">
                      <Loader2 className="size-4 animate-spin" />
                      Loading PDF preview...
                    </div>
                  }
                >
                  <Page
                    pageNumber={pageNumber}
                    scale={scale}
                    renderTextLayer
                    renderAnnotationLayer
                  />
                </Document>
              </div>
            </div>
          </SheetContent>
        </Sheet>
      )}

      {/* Entity detail sheet */}
      <Sheet open={!!selectedEntity} onOpenChange={(open) => !open && setSelectedEntity(null)}>
        <SheetContent side="right" className="w-full border-l-[#EAEAEA] sm:max-w-md">
          {selectedEntity && (
            <>
              <SheetHeader className="border-b border-[#EAEAEA] pb-4">
                <SheetTitle className="font-heading text-lg tracking-tight text-[#2F3437]">
                  {selectedEntity.value}
                </SheetTitle>
                <SheetDescription className="text-[#787774]">
                  Detected as{' '}
                  <Badge
                    variant="outline"
                    className={`rounded-full border-0 text-[10px] font-medium uppercase tracking-wider ${getTypeColor(selectedEntity.type)}`}
                  >
                    {selectedEntity.type}
                  </Badge>
                </SheetDescription>
              </SheetHeader>

              <ScrollArea className="flex-1 px-4">
                <div className="space-y-6 py-4">
                  <div className="space-y-2">
                    <p className="text-xs font-medium uppercase tracking-wider text-[#B0AEAA]">
                      Confidence
                    </p>
                    <div className="flex items-center gap-2">
                      <div className="h-2 flex-1 rounded-full bg-[#F1F0ED]">
                        <div
                          className="h-2 rounded-full bg-[#2F3437] transition-all"
                          style={{
                            width: `${Math.round((selectedEntity.score || 0) * 100)}%`,
                          }}
                        />
                      </div>
                      <span className="text-sm font-medium text-[#2F3437]">
                        {Math.round((selectedEntity.score || 0) * 100)}%
                      </span>
                    </div>
                  </div>

                  <Separator className="bg-[#EAEAEA]" />

                  <div className="space-y-2">
                    <p className="text-xs font-medium uppercase tracking-wider text-[#B0AEAA]">
                      Detected By
                    </p>
                    <Badge
                      variant="secondary"
                      className={`rounded-full text-[11px] font-medium ${
                        selectedEntity.detected_by === 'presidio'
                          ? 'bg-[#E1F3FE] text-[#1F6C9F]'
                          : 'bg-[#FBF3DB] text-[#956400]'
                      }`}
                    >
                      {selectedEntity.detected_by === 'presidio' ? 'Presidio' : 'Custom recognizer'}
                    </Badge>
                  </div>

                  <Separator className="bg-[#EAEAEA]" />

                  <div className="space-y-2">
                    <p className="text-xs font-medium uppercase tracking-wider text-[#B0AEAA]">
                      Explanation
                    </p>
                    <p className="text-sm leading-relaxed text-[#2F3437]">
                      {selectedEntity.explanation || 'No explanation is available.'}
                    </p>
                  </div>

                  {selectedEntity.applied_policy_rule && (
                    <>
                      <Separator className="bg-[#EAEAEA]" />
                      <div className="space-y-2">
                        <p className="text-xs font-medium uppercase tracking-wider text-[#B0AEAA]">
                          Policy Rule Applied
                        </p>
                        <Badge
                          variant="secondary"
                          className="rounded-full bg-[#F1F0ED] text-[11px] font-medium text-[#2F3437]"
                        >
                          {selectedEntity.applied_policy_rule}
                        </Badge>
                      </div>
                    </>
                  )}

                  <Separator className="bg-[#EAEAEA]" />

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <p className="text-xs font-medium uppercase tracking-wider text-[#B0AEAA]">
                        Risk Level
                      </p>
                      <Badge
                        variant="secondary"
                        className={`rounded-full text-[11px] font-medium uppercase ${riskColors[selectedEntity.risk_level] || ''}`}
                      >
                        {selectedEntity.risk_level || 'Unknown'}
                      </Badge>
                    </div>
                    <div className="space-y-2">
                      <p className="text-xs font-medium uppercase tracking-wider text-[#B0AEAA]">
                        Recommendation
                      </p>
                      <Badge
                        variant="outline"
                        className={`rounded-full text-[11px] font-medium uppercase ${
                          selectedEntity.recommendation === 'redact'
                            ? 'border-[#FDEBEC] bg-[#FDEBEC] text-[#9F2F2D]'
                            : selectedEntity.recommendation === 'review'
                              ? 'border-[#FBF3DB] bg-[#FBF3DB] text-[#956400]'
                              : 'border-[#EDF3EC] bg-[#EDF3EC] text-[#346538]'
                        }`}
                      >
                        {selectedEntity.recommendation || 'Review'}
                      </Badge>
                    </div>
                  </div>

                  <Separator className="bg-[#EAEAEA]" />

                  <div className="space-y-2">
                    <p className="text-xs font-medium uppercase tracking-wider text-[#B0AEAA]">
                      Location in extracted text
                    </p>
                    <p className="text-sm text-[#787774]">
                      Characters {selectedEntity.start}–{selectedEntity.end}
                    </p>
                  </div>

                  {result?.original_text && (
                    <div className="rounded-lg border border-[#EAEAEA] bg-[#F7F6F3] p-3">
                      <p className="mb-1 text-xs font-medium uppercase tracking-wider text-[#B0AEAA]">
                        Context
                      </p>
                      <p className="text-sm text-[#2F3437]">
                        “{result.original_text.slice(
                          Math.max(0, selectedEntity.start - 40),
                          Math.min(result.original_text.length, selectedEntity.end + 40)
                        )}”
                      </p>
                    </div>
                  )}
                </div>
              </ScrollArea>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  )
}

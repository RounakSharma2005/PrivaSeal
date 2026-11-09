import { useState, useCallback, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { analyzeText, exportText, generatePolicy, auditRedactedText, refinePolicy } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
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
  Eye as EyeIcon,
  Search,
  ShieldCheck,
} from 'lucide-react'

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
  keep: EyeIcon,
  review: Search,
}

const policySectionLabels = {
  hide: 'Will be hidden',
  keep: 'Will be kept',
  review: 'Will be reviewed',
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

export default function TextAnalyzer({ activeTab, onTabChange }) {
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
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

  const handleGeneratePolicy = useCallback(async () => {
    if (!purpose.trim()) return
    setGeneratingPolicy(true)
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
    if (!text.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    setAuditResult(null)
    try {
      const params = {}
      if (purpose && policyGeneratedFor) params.purpose = policyGeneratedFor
      if (policy) params.policy = policy
      const data = await analyzeText(text, params)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [text, purpose, policy, policyGeneratedFor])

  const handleExport = useCallback(async () => {
    if (!result) return
    setExporting(true)
    try {
      const blob = new Blob([result.anonymized_text], { type: 'text/plain;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'redacted_document.txt'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err) {
      setError('Export failed: ' + err.message)
    } finally {
      setExporting(false)
    }
  }, [result])

  const handleAudit = useCallback(async () => {
    if (!result) return
    setAuditing(true)
    setAuditResult(null)
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
    setText('')
    setResult(null)
    setError(null)
    setSelectedEntity(null)
    setAuditResult(null)
  }, [])

  const [activeSection, setActiveSection] = useState('overview')

  const navItems = [
    { id: 'overview', label: 'Overview' },
    { id: 'audit', label: 'Audit' },
    { id: 'entities', label: 'Entities' },
    { id: 'comparison', label: 'Comparison' },
    { id: 'explanations', label: 'Explanations' },
    { id: 'kept', label: 'Kept Items' },
    { id: 'actions', label: 'Actions' },
  ]
  const scrollToSection = (id) => {
    setActiveSection(id)
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  useEffect(() => {
    if (!result) return
    const sectionIds = navItems.map((item) => item.id)
    const observers = []
    for (const id of sectionIds) {
      const el = document.getElementById(id)
      if (!el) continue
      const observer = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) setActiveSection(id)
        },
        { rootMargin: '-20% 0px -60% 0px', threshold: 0 }
      )
      observer.observe(el)
      observers.push(observer)
    }
    return () => observers.forEach((o) => o.disconnect())
  }, [result])

  return (
    <div className="w-full">
      <div className="grid grid-cols-1 md:grid-cols-[1fr_minmax(auto,800px)_1fr] gap-8 max-w-[1600px] mx-auto">
        {/* Left nav column */}
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

        {/* Middle content column */}
        <div className="min-w-0 space-y-8">
      {/* Input Section */}
      {!result && (
        <Card className="border-[#EAEAEA] shadow-none">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Shield className="size-5 text-[#2F3437]" />
                <CardTitle className="font-heading text-xl tracking-tight">
                  Paste your text for analysis
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
              Enter any text containing personal information. Set a privacy policy to control what gets redacted.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Textarea
              placeholder="Paste or type your text here..."
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="min-h-[200px] resize-y border-[#EAEAEA] bg-white text-sm leading-relaxed text-[#2F3437] placeholder:text-[#B0AEAA] focus-visible:border-[#D0CEC9]"
            />

            {/* Privacy Policy Section */}
            <div className="rounded-lg border border-[#EAEAEA] bg-white px-4 py-3">
              {!policy ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <BookOpen className="size-4 text-[#787774]" />
                    <span className="text-sm font-medium text-[#2F3437]">Privacy Policy</span>
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={purpose}
                      onChange={(e) => setPurpose(e.target.value)}
                      placeholder="e.g. Resume Review, Contract Analysis"
                      className="flex-1 rounded-lg border border-[#EAEAEA] bg-white px-3 py-2 text-sm text-[#2F3437] placeholder:text-[#B0AEAA] outline-none focus-visible:border-[#D0CEC9] focus-visible:ring-1 focus-visible:ring-[#D0CEC9]"
                      onKeyDown={(e) => e.key === 'Enter' && handleGeneratePolicy()}
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
                    Describe the purpose to generate a tailored policy.
                  </p>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <BookOpen className="size-4 text-[#346538]" />
                    <span className="text-sm font-medium text-[#2F3437]">
                      Policy active for <span className="text-[#346538]">{policyGeneratedFor}</span>
                    </span>
                    <Badge variant="outline" className="rounded-full bg-[#EDF3EC] text-[#346538] border-0 text-[10px] font-medium">Active</Badge>
                  </div>
                  <Button onClick={handleRemovePolicy} variant="ghost" size="sm" className="text-[#787774] hover:text-[#9F2F2D] h-7 px-2 shrink-0">
                    <X className="size-3.5" />
                  </Button>
                </div>
              )}
            </div>

            <div className="flex items-center justify-between">
              <p className="text-xs text-[#B0AEAA]">
                {text.length} character{text.length !== 1 ? 's' : ''}
                {!policy && (
                  <span className="ml-2">— Privacy policy is optional</span>
                )}
              </p>
              <Button
                onClick={handleAnalyze}
                disabled={!text.trim() || loading}
                className="bg-[#111111] text-white hover:bg-[#333333]"
              >
                {loading ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <FileText className="size-4" />
                    Analyze Text
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Error */}
      {error && (
        <Card className="border-[#FDEBEC] shadow-none bg-[#FFF8F8]">
          <CardContent className="flex items-start gap-3 pt-4">
            <AlertCircle className="mt-0.5 size-5 shrink-0 text-[#9F2F2D]" />
            <div className="flex-1">
              <p className="text-sm font-medium text-[#9F2F2D]">Analysis failed</p>
              <p className="mt-1 text-sm text-[#9F2F2D]/80">{error}</p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => setError(null)} className="text-[#9F2F2D]">
              Dismiss
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {result && (
        <>
          {/* Overall Risk Summary */}
          <Card id="overview" className="scroll-mt-24 border-[#EAEAEA] shadow-none">
            <CardHeader>
              <div className="flex items-center gap-2">
                <Shield className="size-5 text-[#2F3437]" />
                <CardTitle className="font-heading text-xl tracking-tight">
                  Analysis Results
                </CardTitle>
              </div>
              {result.overall_risk_summary && (
                <CardDescription className="text-[#787774]">
                  {result.overall_risk_summary}
                </CardDescription>
              )}
              {policyGeneratedFor && purpose && (
                <CardDescription className="text-[#787774] flex items-center gap-1.5 mt-1">
                  <BookOpen className="size-3.5" />
                  Policy applied: <span className="text-[#2F3437]">{policyGeneratedFor}</span>
                </CardDescription>
              )}
            </CardHeader>
          </Card>

          {/* Privacy Audit */}
          <Card id="audit" className="scroll-mt-24 border-[#EAEAEA] shadow-none">
            <CardHeader>
              <div className="flex items-center gap-2">
                <ShieldCheck className="size-4 text-[#787774]" />
                <CardTitle className="font-heading text-base tracking-tight">
                  Privacy Audit
                </CardTitle>
              </div>
              <CardDescription>
                Run an independent check on the redacted text to find any remaining identifiers.
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
                  <div className="flex items-center gap-3">
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
                    <p className="text-sm text-[#787774] leading-relaxed">
                      {auditResult.result_summary}
                    </p>
                  )}

                  {auditResult.remaining_identifiers && auditResult.remaining_identifiers.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-xs font-medium uppercase tracking-wider text-[#B0AEAA]">
                        Remaining Identifiers — {auditResult.remaining_identifiers.length}
                      </p>
                      {auditResult.remaining_identifiers.map((item, i) => (
                        <div key={i} className="rounded-lg border border-[#EAEAEA] bg-white p-3">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-sm font-medium text-[#2F3437]">{item.value}</span>
                          </div>
                          <p className="text-xs text-[#787774]">{item.reason}</p>
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

          {/* Entity Summary */}
          {result.entities && result.entities.length > 0 && (
            <Card id="entities" className="scroll-mt-24 border-[#EAEAEA] shadow-none">
              <CardHeader>
                <CardTitle className="font-heading text-base tracking-tight">
                  Detected Entities — {result.entities.length} found
                </CardTitle>
                <CardDescription>
                  Click on any highlighted entity or card to see the full explanation.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {result.entities.map((entity, i) => (
                    <button
                      key={i}
                      onClick={() => setSelectedEntity(entity)}
                      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-all hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 ${getTypeColor(entity.type)}`}
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

          {/* Original vs Anonymized */}
          <div id="comparison" className="scroll-mt-24 grid gap-6 md:grid-cols-2">
            <Card className="border-[#EAEAEA] shadow-none">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Eye className="size-4 text-[#787774]" />
                  <CardTitle className="font-heading text-sm tracking-tight">
                    Original Text
                  </CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <div className="rounded-lg border border-[#EAEAEA] bg-white p-4 text-sm leading-relaxed text-[#2F3437]">
                  <HighlightedText
                    text={result.original_text}
                    entities={result.entities}
                    onEntityClick={setSelectedEntity}
                  />
                </div>
              </CardContent>
            </Card>

            <Card className="border-[#EAEAEA] shadow-none">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <EyeOff className="size-4 text-[#787774]" />
                  <CardTitle className="font-heading text-sm tracking-tight">
                    Redacted
                  </CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <div className="rounded-lg border border-[#EAEAEA] bg-white p-4 text-sm leading-relaxed text-[#2F3437]">
                  <AnonymizedText text={result.anonymized_text} />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Entity Details List */}
          {result.entities && result.entities.length > 0 && (
            <Card id="explanations" className="scroll-mt-24 border-[#EAEAEA] shadow-none">
              <CardHeader>
                <CardTitle className="font-heading text-base tracking-tight">
                  Entity Explanations
                </CardTitle>
                <CardDescription>
                  Why each entity was flagged and what action is recommended.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {result.entities.map((entity, i) => (
                    <button
                      key={i}
                      onClick={() => setSelectedEntity(entity)}
                      className="w-full rounded-lg border border-[#EAEAEA] bg-white p-4 text-left transition-all hover:border-[#D0CEC9] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-[#2F3437]">{entity.value}</span>
                            <Badge
                              variant="outline"
                              className={`rounded-full border-0 text-[10px] font-medium uppercase tracking-wider ${getTypeColor(entity.type)}`}
                            >
                              {entity.type}
                            </Badge>
                            {entity.applied_policy_rule && (
                              <Badge variant="outline" className="rounded-full border-0 bg-[#F1F0ED] text-[#787774] text-[10px] font-medium">
                                {entity.applied_policy_rule}
                              </Badge>
                            )}
                          </div>
                          <p className="mt-1 text-sm text-[#787774] line-clamp-2">
                            {entity.explanation}
                          </p>
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          <Badge
                            variant="secondary"
                            className={`rounded-full border-0 text-[10px] font-medium uppercase tracking-wider ${riskColors[entity.risk_level] || ''}`}
                          >
                            {entity.risk_level}
                          </Badge>
                          <Badge
                            variant="outline"
                            className={`rounded-full border text-[10px] font-medium uppercase tracking-wider ${
                              entity.recommendation === 'redact'
                                ? 'border-[#FDEBEC] bg-[#FDEBEC] text-[#9F2F2D]'
                                : entity.recommendation === 'review'
                                  ? 'border-[#FBF3DB] bg-[#FBF3DB] text-[#956400]'
                                  : 'border-[#EDF3EC] bg-[#EDF3EC] text-[#346538]'
                            }`}
                          >
                            {entity.recommendation}
                          </Badge>
                          <ChevronRight className="size-4 text-[#B0AEAA]" />
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

            {/* Non-Redacted Items */}
            {result.non_redacted && result.non_redacted.length > 0 && (
            <Card id="kept" className="scroll-mt-24 border-[#EAEAEA] shadow-none">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="size-4 text-[#346538]" />
                  <CardTitle className="font-heading text-base tracking-tight">
                    Kept Visible — {result.non_redacted.length} items
                  </CardTitle>
                </div>
                <CardDescription>
                  These items were reviewed and determined safe to keep visible.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {result.non_redacted.map((item, i) => (
                    <div
                      key={i}
                      className="rounded-lg border border-[#EAEAEA] bg-white p-4"
                    >
                      <div className="flex items-start gap-3">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-[#2F3437]">{item.value}</span>
                            <Badge
                              variant="outline"
                              className="rounded-full border-0 bg-[#EDF3EC] text-[#346538] text-[10px] font-medium uppercase tracking-wider"
                            >
                              {item.type}
                            </Badge>
                          </div>
                          <p className="mt-1 text-sm text-[#787774]">{item.explanation}</p>
                          <p className="mt-0.5 text-xs text-[#346538]">
                            {item.reason_kept}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Actions */}
          <div id="actions" className="scroll-mt-24 flex items-center justify-center gap-4 pb-8">
            <Button
              onClick={handleExport}
              disabled={exporting}
              variant="outline"
              className="border-[#EAEAEA] text-[#2F3437] hover:bg-[#F1F0ED]"
            >
              {exporting ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Download className="size-4" />
              )}
              Export Redacted
            </Button>
            <Button
              onClick={handleReset}
              variant="ghost"
              className="text-[#787774] hover:text-[#2F3437]"
            >
              <RotateCcw className="size-4" />
              Analyze New Text
            </Button>
          </div>
        </>
      )}
        </div>

        {/* Right policy column */}
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
                <div className="rounded-lg border border-[#EAEAEA] bg-white p-4 flex flex-col space-y-3">
                  <div className="flex items-center justify-between shrink-0">
                    <p className="text-xs font-medium uppercase tracking-wider text-[#787774]">
                      Policy for: <span className="text-[#2F3437] normal-case">{policyGeneratedFor}</span>
                    </p>
                    <Button onClick={handleRemovePolicy} variant="ghost" size="sm" className="text-[#787774] hover:text-[#9F2F2D] h-7 px-2 shrink-0">
                      <X className="size-3.5" />
                    </Button>
                  </div>

                  {/* Toggle buttons */}
                  <div className="flex gap-1 rounded-lg bg-[#F1F0ED] p-0.5 shrink-0">
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

                  {/* Active section */}
                  <div className="flex-1 overflow-y-auto min-h-0 pb-2">
                    <PolicySection type={activePolicyTab} items={policy[activePolicyTab] || []} />
                  </div>

                  {/* Refine Policy Input */}
                  <div className="flex items-center gap-2 pt-3 border-t border-[#EAEAEA] shrink-0">
                    <div className="relative flex-1">
                      <input
                        type="text"
                        value={refinePrompt}
                        onChange={(e) => setRefinePrompt(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleRefinePolicy()}
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

      {/* Entity Detail Sheet */}
      <Sheet open={!!selectedEntity} onOpenChange={(open) => !open && setSelectedEntity(null)}>
        <SheetContent side="right" className="w-full sm:max-w-md border-l-[#EAEAEA]">
          {selectedEntity && (
            <>
              <SheetHeader className="pb-4 border-b border-[#EAEAEA]">
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
                      <div className="flex-1 h-2 rounded-full bg-[#F1F0ED]">
                        <div
                          className="h-2 rounded-full bg-[#2F3437] transition-all"
                          style={{ width: `${Math.round(selectedEntity.score * 100)}%` }}
                        />
                      </div>
                      <span className="text-sm font-medium text-[#2F3437]">
                        {Math.round(selectedEntity.score * 100)}%
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
                      {selectedEntity.detected_by === 'presidio' ? 'Presidio' : 'LLM'}
                    </Badge>
                  </div>

                  <Separator className="bg-[#EAEAEA]" />

                  <div className="space-y-2">
                    <p className="text-xs font-medium uppercase tracking-wider text-[#B0AEAA]">
                      Explanation
                    </p>
                    <p className="text-sm leading-relaxed text-[#2F3437]">
                      {selectedEntity.explanation}
                    </p>
                  </div>

                  {selectedEntity.applied_policy_rule && (
                    <>
                      <Separator className="bg-[#EAEAEA]" />
                      <div className="space-y-2">
                        <p className="text-xs font-medium uppercase tracking-wider text-[#B0AEAA]">
                          Policy Rule Applied
                        </p>
                        <Badge variant="secondary" className="rounded-full text-[11px] font-medium bg-[#F1F0ED] text-[#2F3437]">
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
                        {selectedEntity.risk_level}
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
                        {selectedEntity.recommendation}
                      </Badge>
                    </div>
                  </div>

                  <Separator className="bg-[#EAEAEA]" />

                  <div className="space-y-2">
                    <p className="text-xs font-medium uppercase tracking-wider text-[#B0AEAA]">
                      Location
                    </p>
                    <p className="text-sm text-[#787774]">
                      Characters {selectedEntity.start}–{selectedEntity.end}
                    </p>
                  </div>

                  <div className="rounded-lg border border-[#EAEAEA] bg-[#F7F6F3] p-3">
                    <p className="text-xs font-medium uppercase tracking-wider text-[#B0AEAA] mb-1">
                      Context
                    </p>
                    <p className="text-sm text-[#2F3437]">
                      &ldquo;{result?.original_text?.slice(
                        Math.max(0, selectedEntity.start - 40),
                        Math.min(result.original_text.length, selectedEntity.end + 40)
                      )}&rdquo;
                    </p>
                  </div>
                </div>
              </ScrollArea>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  )
}

# Conseal Frontend Architecture

A simple, minimal overview of Conseal's frontend application architecture.

## Tech Stack
* **Framework:** Next.js (App Router)
* **Language:** JavaScript (ES6+)
* **Styling:** Tailwind CSS (Vanilla CSS utilities)
* **Package Manager:** Bun
* **Core Libraries:**
  * `react-pdf` / `pdfjs-dist` (PDF document rendering and text-layer mapping)
  * `lucide-react` (Icon system)
  * `framer-motion` (Micro-animations and slide transitions)

---

## Directory Structure

```text
frontend/
├── src/
│   ├── app/                # Next.js App Router root
│   │   ├── layout.js       # Global layout & HTML structure
│   │   ├── page.js         # Main landing dashboard (Tab controller)
│   │   └── globals.css     # Global Tailwind imports & custom classes
│   ├── components/         # Shared UI & business-logic components
│   │   ├── PdfAnalyzer.js  # PDF upload, interactive rendering & redaction layer
│   │   ├── TextAnalyzer.js # Raw text analysis & side-by-side comparison
│   │   ├── GoogleSignIn.js # Authentication controller
│   │   └── ui/             # Reusable design tokens (Card, Button, Badge)
│   └── lib/
│       └── api.js          # API client calling the FastAPI backend
├── package.json            # Scripts & dependencies
└── bun.lock                # Bun lockfile
```

---

## Core Flows

### 1. Document Analysis & Redaction (PDF)
* **Upload:** PDF is sent to `/pii/upload`.
* **Rendering:** `<Document>` from `react-pdf` renders the canvas.
* **Redaction Injection:** Once the text-layer loads, `applyHighlights()` queries all `span[role="presentation"]` elements in the PDF text layer. If they match the backend's PII findings:
  * The actual text is stripped out (`span.textContent = ''`) for absolute security (cannot be copied/selected).
  * Opaque boxes (`#2F3437`) are drawn using exact bounding client rectangles.
* **Review & Scroll:** Clicking a redaction box automatically scrolls to its corresponding Explanation card (`#explanation-{i}`) with a visual flash highlight.
* **Re-render:** Changing a status (e.g. Redact ➔ Keep) updates the state, triggering `applyHighlights()` to re-render the view, and scrolls the user back up to the PDF preview.

### 2. Privacy Policy Generation
* The user inputs a purpose (e.g., "Resume Review").
* `/pii/policy` is called to generate a privacy strategy.
* The rules classify data into **Hide**, **Keep**, and **Review** sections, displayed in the sticky right-hand column.

---

## Getting Started

### Development
```bash
bun install
bun run dev
```

### Production Build
```bash
bun run build
```

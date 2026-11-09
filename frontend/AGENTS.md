# AGENTS.md

## Project

This project is built with:

* Next.js 15 (App Router)
* React 19
* React Compiler enabled
* Bun
* Tailwind CSS v4
* JavaScript (NO TypeScript unless explicitly requested)

Primary goal:
Build clean, maintainable and production-ready code while keeping performance high.

---

# General Rules

Before writing code:

1. Read the relevant files.
2. Understand existing architecture.
3. Reuse existing patterns.
4. Never rewrite working code unnecessarily.
5. Check for nessasary skills in ./agetns/skills folder and use if exists

Always prefer consistency over cleverness.

---

# Scope Rules

Only modify files necessary for the current task.

Never refactor unrelated code.

Never rename files unless requested.

Never move folders unless requested.

Never introduce breaking changes.

---

# Coding Style

Prefer:

* Functional components
* Server Components by default
* Client Components only when required
* Async/await
* Early returns
* Small reusable functions

Avoid:

* Nested ternaries
* Large components (>300 lines)
* Duplicate logic
* Magic numbers
* Dead code

---

# JavaScript

Use JavaScript.

Never convert files to TypeScript.

Do not introduce TS config.

---

# React

Prefer:

* Server Components
* React Compiler friendly code
* Minimal useEffect
* Derived state over duplicated state
* useMemo/useCallback only when actually useful

Avoid unnecessary re-renders.

---

# Next.js

Prefer:

* App Router
* Server Actions when appropriate
* Route Handlers for APIs
* next/image
* next/font

Do not use Pages Router.

---

# Styling

Use:

* Tailwind CSS v4

Keep styling:

* Mobile first
* Responsive
* Accessible
* use minimalsic-ui skill
* Utility-first

Avoid inline styles unless absolutely necessary.

---

# Components

Create reusable components.

Avoid copying UI.

If similar code already exists,
reuse it.

---

# Performance

Always think about:

* bundle size
* lazy loading
* image optimization
* avoiding unnecessary renders
* minimizing client JavaScript

---

# Accessibility

Every UI must include:

* keyboard navigation
* aria labels where needed
* visible focus states

---

# Error Handling

Handle:

* loading
* empty
* error

Do not assume requests succeed.

---

# File Changes

When editing:

* preserve formatting
* preserve comments
* preserve existing architecture

Do not rewrite entire files unless required.

---

# Before Finishing

Verify:

* imports
* lint errors
* build errors
* unused variables
* formatting

---

# Response Format

Before making changes:

Explain your plan.

After implementation:

Provide:

* Files changed
* Why they changed
* Any follow-up recommendations

---

# If Context Is Missing

Never guess.

Ask for:

* relevant files
* API responses
* screenshots
* design references

instead of making assumptions.

---

# Architecture Priority

Always prefer:

Existing Architecture

>

Consistency

>

Performance

>

New Abstractions

Do not invent a new pattern if one already exists.

---

# Golden Rule

Write code that another senior engineer could maintain without asking why it was written that way.

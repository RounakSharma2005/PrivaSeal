const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function generatePolicy(purpose) {
  const res = await fetch(`${API_BASE}/pii/policy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ purpose }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || 'Policy generation failed');
  }
  return res.json();
}

export async function refinePolicy(current_policy, user_prompt) {
  const res = await fetch(`${API_BASE}/pii/policy/refine`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ current_policy, user_prompt }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || 'Policy refinement failed');
  }
  return res.json();
}

export async function analyzeText(text, { purpose, policy } = {}) {
  const body = { text };
  if (purpose) body.purpose = purpose;
  if (policy) body.policy = policy;

  const res = await fetch(`${API_BASE}/pii/anonymize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || 'Analysis failed');
  }
  return res.json();
}

export async function auditRedactedText(redactedText, { policy } = {}) {
  const body = { redacted_text: redactedText };
  if (policy) body.policy = policy;

  const res = await fetch(`${API_BASE}/pii/audit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || 'Audit failed');
  }
  return res.json();
}

export async function uploadPdf(file, { purpose, policy } = {}) {
  const form = new FormData();
  form.append('file', file);
  if (purpose) form.append('purpose', purpose);
  if (policy) form.append('policy_json', JSON.stringify(policy));

  const res = await fetch(`${API_BASE}/pii/upload`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || 'Upload analysis failed');
  }
  return res.json();
}


export async function exportPdf(file, redactions, { includeEvidence = false } = {}) {
  const form = new FormData();

  form.append('file', file);

  form.append(
    'redactions_json',
    JSON.stringify(
      redactions.map((r) => ({
        value: r.value,
        type: r.type,
        action: r.action || 'redact',
      }))
    )
  );

  form.append('include_evidence', String(includeEvidence));

  const res = await fetch(`${API_BASE}/pii/export_pdf`, {
    method: 'POST',
    body: form,
  });

  if (!res.ok) {
    let message = 'PDF export failed';

    try {
      const err = await res.json();
      message = err.detail?.message || err.detail || err.message || message;
    } catch {
      // Keep the fallback error message.
    }

    throw new Error(
      typeof message === 'string' ? message : 'PDF export failed'
    );
  }

  return res.blob();
}


export async function exportText(text) {
  const res = await fetch(`${API_BASE}/pii/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error('Export failed');
  return res.blob();
}

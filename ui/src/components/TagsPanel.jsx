import { useState } from "react";
import { api, p } from "../api.js";
import { formatDate } from "../useApi.js";
import { ErrorNotice, versionLabel } from "./common.jsx";

function GateSummary({ gate }) {
  if (!gate) return <span className="muted">No gate</span>;
  return (
    <span className="subtle">
      Gate:{" "}
      {gate.rules
        .map((rule) =>
          [rule.min != null && `${rule.metric} ≥ ${rule.min}`, rule.max != null && `${rule.metric} ≤ ${rule.max}`]
            .filter(Boolean)
            .join(", "),
        )
        .join("; ")}
      {gate.require_better_than_current && "; at least as good as current"}
    </span>
  );
}

function TagCard({ name, tag, versions, onChange }) {
  const latest = versions.length ? versions[versions.length - 1].version : null;
  const [target, setTarget] = useState(latest ?? "");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [confirmRollback, setConfirmRollback] = useState(false);

  const run = async (request) => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const updated = await request();
      setResult(updated);
      setReason("");
      setConfirmRollback(false);
      onChange();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const promote = (force) =>
    run(() =>
      api(`${p(name)}/tags/${encodeURIComponent(tag.name)}`, {
        method: "PUT",
        body: { version: Number(target), reason: reason.trim() || null, force },
      }),
    );
  const rollback = () =>
    run(() =>
      api(`${p(name)}/tags/${encodeURIComponent(tag.name)}/rollback`, {
        method: "POST",
        body: { reason: reason.trim() || null },
      }),
    );

  const gateFailed = error?.type === "GateFailedError";
  return (
    <div className="card">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <strong style={{ fontSize: 16 }}>{tag.name}</strong>
        <span className="chip">
          points to <strong>{versionLabel(tag.version)}</strong>
        </span>
      </div>
      <div style={{ margin: "6px 0" }}>
        <GateSummary gate={tag.gate} />
      </div>
      {tag.updated_by && (
        <div className="muted" style={{ fontSize: 12 }}>
          Last change by {tag.updated_by}, {formatDate(tag.updated_at)}
        </div>
      )}

      <label htmlFor={`v-${tag.name}`}>Promote to</label>
      <div className="row">
        <select id={`v-${tag.name}`} value={target} onChange={(e) => setTarget(e.target.value)}>
          {[...versions].reverse().map((v) => (
            <option key={v.version} value={v.version}>
              v{v.version}
              {v.commit_message ? ` – ${v.commit_message.slice(0, 40)}` : ""}
            </option>
          ))}
        </select>
        <button
          className="primary"
          disabled={busy || !target || Number(target) === tag.version}
          onClick={() => promote(false)}
        >
          Promote
        </button>
      </div>
      <label htmlFor={`r-${tag.name}`}>Reason (optional; required to force or explain a rollback)</label>
      <input
        id={`r-${tag.name}`}
        type="text"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
      />

      <ErrorNotice error={error} />
      {gateFailed && (
        <div className="row">
          <button className="danger" disabled={busy || !reason.trim()} onClick={() => promote(true)}>
            Force promote (bypass gate)
          </button>
          {!reason.trim() && <span className="muted">Enter a reason to force.</span>}
        </div>
      )}
      {result && (
        <div className="notice ok">
          ✅ {tag.name} now points to {versionLabel(result.version)}.
          {result.warnings?.length > 0 && (
            <div className="notice warn" style={{ marginBottom: 0 }}>
              ⚠️ {result.warnings.join(" ")}
            </div>
          )}
        </div>
      )}

      <div style={{ marginTop: 12 }}>
        {!confirmRollback ? (
          <button disabled={busy || !tag.version} onClick={() => setConfirmRollback(true)}>
            Roll back…
          </button>
        ) : (
          <div className="notice warn">
            ⚠️ Undo the last promote of <strong>{tag.name}</strong>? Apps reading this tag switch
            back within their cache time. Rollback does not run the gate.
            <div className="row" style={{ marginTop: 8 }}>
              <button className="danger" disabled={busy} onClick={rollback}>
                Yes, roll back
              </button>
              <button onClick={() => setConfirmRollback(false)}>Cancel</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function TagsPanel({ name, tags, versions, onChange }) {
  if (versions.length === 0) {
    return <div className="card">This prompt has no versions yet.</div>;
  }
  return (
    <div className="grid-cards">
      {tags.map((tag) => (
        <TagCard key={tag.name} name={name} tag={tag} versions={versions} onChange={onChange} />
      ))}
    </div>
  );
}

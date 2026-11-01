import { Fragment, useState } from "react";
import { api, p } from "../api.js";
import {
  Dialog,
  ErrorNotice,
  Notice,
  STAGES,
  TagPill,
  gateText,
  timeAgo,
  versionLabel,
} from "./common.jsx";

// Where an undo would take the tag: each rollback cancels the next older promote
// (the same rule the server uses).
function rollbackTarget(events) {
  let pending = 0;
  for (const event of events) {
    if (event.action === "rollback") pending += 1;
    else if (pending) pending -= 1;
    else return event.from_version;
  }
  return null;
}

function PromoteDialog({ name, tag, versions, suggested, onClose, onDone }) {
  const [target, setTarget] = useState(String(suggested));
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const gateFailed = error?.type === "GateFailedError";

  const promote = async (force) => {
    setBusy(true);
    setError(null);
    try {
      const updated = await api(`${p(name)}/tags/${encodeURIComponent(tag.name)}`, {
        method: "PUT",
        body: { version: Number(target), reason: reason.trim() || null, force },
      });
      setResult(updated);
      onDone();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  if (result) {
    return (
      <Dialog
        title={`${tag.name} now serves ${versionLabel(result.version)}`}
        onClose={onClose}
        footer={
          <button className="primary" onClick={onClose}>
            Done
          </button>
        }
      >
        <Notice kind="ok">Apps reading this tag pick it up within their cache time.</Notice>
        {result.warnings?.map((warning) => (
          <Notice key={warning} kind="warn">
            {warning}
          </Notice>
        ))}
      </Dialog>
    );
  }

  return (
    <Dialog
      title={`Promote ${tag.name}`}
      description={`Currently ${versionLabel(tag.version)}. ${tag.gate ? "The gate is checked before the tag moves." : "This tag has no gate."}`}
      onClose={onClose}
      footer={
        <>
          <button onClick={onClose}>Cancel</button>
          {gateFailed ? (
            <button className="danger" disabled={busy || !reason.trim()} onClick={() => promote(true)}>
              Force promote
            </button>
          ) : (
            <button
              className="primary"
              disabled={busy || Number(target) === tag.version}
              onClick={() => promote(false)}
            >
              Promote to {versionLabel(Number(target))}
            </button>
          )}
        </>
      }
    >
      <label className="field" htmlFor="promote-version">
        Version
      </label>
      <select
        id="promote-version"
        value={target}
        style={{ width: "100%" }}
        onChange={(e) => {
          setTarget(e.target.value);
          setError(null);
        }}
      >
        {[...versions].reverse().map((v) => (
          <option key={v.version} value={v.version}>
            v{v.version}
            {v.commit_message ? ` — ${v.commit_message.slice(0, 50)}` : ""}
            {v.version === tag.version ? " (current)" : ""}
          </option>
        ))}
      </select>
      {tag.gate && <div className="help">Gate: {gateText(tag.gate)}</div>}
      <label className="field" htmlFor="promote-reason">
        Reason {gateFailed ? "(required to force)" : "(optional)"}
      </label>
      <input
        id="promote-reason"
        type="text"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="e.g. evals passed on faq-100"
      />
      <ErrorNotice error={error} />
      {gateFailed && (
        <div className="help">
          Forcing bypasses the gate and is recorded in the audit log with your reason.
        </div>
      )}
    </Dialog>
  );
}

function RollbackDialog({ name, tag, events, onClose, onDone }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const target = rollbackTarget(events.filter((e) => e.tag === tag.name));

  const rollback = async () => {
    setBusy(true);
    setError(null);
    try {
      await api(`${p(name)}/tags/${encodeURIComponent(tag.name)}/rollback`, {
        method: "POST",
        body: { reason: reason.trim() || null },
      });
      onDone();
      onClose();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      title={`Roll back ${tag.name}`}
      description={
        target
          ? `${tag.name} goes back from ${versionLabel(tag.version)} to ${versionLabel(target)}, undoing its last promote. Rollback never runs the gate.`
          : `${tag.name} has no earlier version to go back to.`
      }
      onClose={onClose}
      footer={
        <>
          <button onClick={onClose}>Cancel</button>
          <button className="danger" disabled={busy || !target} onClick={rollback}>
            Roll back to {versionLabel(target)}
          </button>
        </>
      }
    >
      <label className="field" htmlFor="rollback-reason">
        Reason (recommended)
      </label>
      <input
        id="rollback-reason"
        type="text"
        value={reason}
        autoFocus
        onChange={(e) => setReason(e.target.value)}
        placeholder="e.g. answers got worse after the release"
      />
      <ErrorNotice error={error} />
    </Dialog>
  );
}

function Stage({ tag, onPromote, onRollback, canRollback }) {
  const gate = gateText(tag.gate);
  return (
    <div className={`stage is-${tag.name}`}>
      <div className="stage-head">
        <span className="stage-name">{tag.name}</span>
        {tag.gate && <span className="pill">Gated</span>}
      </div>
      <div className="stage-version">
        {tag.version ? versionLabel(tag.version) : <span className="faint">Not deployed</span>}
      </div>
      <div className="stage-meta">
        {tag.updated_by || tag.version
          ? `Updated ${timeAgo(tag.updated_at)}${tag.updated_by ? ` by ${tag.updated_by}` : ""}`
          : "No version promoted yet"}
      </div>
      <div className="stage-gate">{gate ? `Gate: ${gate}` : "No gate — any version can be promoted"}</div>
      <div className="stage-actions">
        <button className="primary small" onClick={onPromote}>
          Promote…
        </button>
        <button className="small" disabled={!canRollback} onClick={onRollback}>
          Roll back…
        </button>
      </div>
    </div>
  );
}

export default function TagsPanel({ name, tags, versions, events, onChange }) {
  const [dialog, setDialog] = useState(null);

  if (versions.length === 0) {
    return (
      <div className="panel">
        <div className="empty">
          <strong>No versions yet</strong>
          Save one with <code>promptdock push</code> or the client, then promote it here.
        </div>
      </div>
    );
  }

  const byName = Object.fromEntries(tags.map((t) => [t.name, t]));
  const stages = STAGES.filter((s) => byName[s]).map((s) => byName[s]);
  const others = tags.filter((t) => !STAGES.includes(t.name));
  const latest = versions[versions.length - 1].version;

  // Default target: what the previous stage runs (moving a version down the pipeline),
  // otherwise the latest version.
  const suggestedFor = (tag) => {
    const index = stages.indexOf(tag);
    const previous = index > 0 ? stages[index - 1].version : null;
    return previous && previous !== tag.version ? previous : latest;
  };
  const hasHistory = (tag) => events.some((e) => e.tag === tag.name) && rollbackTarget(events.filter((e) => e.tag === tag.name));

  return (
    <>
      <div className="pipeline">
        {stages.map((tag, i) => (
          <Fragment key={tag.name}>
            {i > 0 && <div className="pipe-arrow">→</div>}
            <Stage
              tag={tag}
              canRollback={Boolean(hasHistory(tag))}
              onPromote={() => setDialog({ kind: "promote", tag })}
              onRollback={() => setDialog({ kind: "rollback", tag })}
            />
          </Fragment>
        ))}
      </div>

      {others.length > 0 && (
        <div className="panel other-tags">
          <div className="panel-head">
            <h2>Other tags</h2>
            <span className="hint">Custom tags such as canaries or per-customer versions</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Tag</th>
                <th>Version</th>
                <th>Gate</th>
                <th>Updated</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {others.map((tag) => (
                <tr key={tag.name}>
                  <td>
                    <TagPill name={tag.name} />
                  </td>
                  <td className="mono">{versionLabel(tag.version)}</td>
                  <td className="muted">{gateText(tag.gate) || "–"}</td>
                  <td className="muted">
                    {timeAgo(tag.updated_at)}
                    {tag.updated_by ? ` by ${tag.updated_by}` : ""}
                  </td>
                  <td className="right nowrap">
                    <button className="small" onClick={() => setDialog({ kind: "promote", tag })}>
                      Promote…
                    </button>{" "}
                    <button
                      className="small"
                      disabled={!hasHistory(tag)}
                      onClick={() => setDialog({ kind: "rollback", tag })}
                    >
                      Roll back…
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {dialog?.kind === "promote" && (
        <PromoteDialog
          name={name}
          tag={dialog.tag}
          versions={versions}
          suggested={suggestedFor(dialog.tag)}
          onClose={() => setDialog(null)}
          onDone={onChange}
        />
      )}
      {dialog?.kind === "rollback" && (
        <RollbackDialog
          name={name}
          tag={dialog.tag}
          events={events}
          onClose={() => setDialog(null)}
          onDone={onChange}
        />
      )}
    </>
  );
}

import { useEffect, useState } from "react";

export const STAGES = ["dev", "preprod", "prod"];

export function versionLabel(version) {
  return version ? `v${version}` : "–";
}

export function TagPill({ name }) {
  const cls = STAGES.includes(name) ? ` tag-${name}` : "";
  return (
    <span className={`pill${cls}`}>
      <span className="dot" />
      {name}
    </span>
  );
}

export function VersionPill({ version }) {
  return <span className="pill version">{versionLabel(version)}</span>;
}

export function ErrorNotice({ error }) {
  if (!error) return null;
  const gate = error.type === "GateFailedError";
  return (
    <div className="notice error" role="alert">
      <span className="icon">✕</span>
      <div>
        <strong>{gate ? "Refused by the gate" : "Something went wrong"}</strong>
        {gate ? (
          <ul>
            {error.failures.map((failure) => (
              <li key={failure}>{failure}</li>
            ))}
          </ul>
        ) : (
          <div>{error.message}</div>
        )}
      </div>
    </div>
  );
}

export function Notice({ kind = "info", icon, children }) {
  const icons = { ok: "✓", warn: "!", error: "✕", info: "i" };
  return (
    <div className={`notice ${kind}`}>
      <span className="icon">{icon || icons[kind]}</span>
      <div>{children}</div>
    </div>
  );
}

// Highlights {{ variables }} inside template text.
function Highlighted({ text }) {
  const parts = text.split(/(\{\{.*?\}\})/g);
  return parts.map((part, i) =>
    part.startsWith("{{") ? (
      <span key={i} className="var">
        {part}
      </span>
    ) : (
      part
    ),
  );
}

export function Template({ template }) {
  if (typeof template === "string") {
    return (
      <div className="code">
        <Highlighted text={template} />
      </div>
    );
  }
  return template.map((message, i) => (
    <div className="code" key={i}>
      <span className="role">{message.role}</span>
      <Highlighted text={message.content} />
    </div>
  ));
}

export function Dialog({ title, description, children, footer, onClose }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose?.();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}>
      <div className="dialog" role="dialog" aria-modal="true" aria-label={title}>
        <div className="dialog-head">
          <h2>{title}</h2>
          {description && <p>{description}</p>}
        </div>
        <div className="dialog-body">{children}</div>
        {footer && <div className="dialog-foot">{footer}</div>}
      </div>
    </div>
  );
}

export function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="small"
      onClick={() => {
        navigator.clipboard?.writeText(text).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        });
      }}
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

export function templateText(template) {
  if (typeof template === "string") return template;
  return template.map((m) => `[${m.role}]\n${m.content}`).join("\n\n");
}

// --- time ---------------------------------------------------------------------------

export function formatDate(iso) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function timeAgo(iso) {
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  const units = [
    ["year", 31536000],
    ["month", 2592000],
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
  ];
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) {
      const n = Math.round(seconds / size);
      return `${n} ${unit}${n === 1 ? "" : "s"} ago`;
    }
  }
  return "just now";
}

// --- metrics ------------------------------------------------------------------------

const LOWER_IS_BETTER = /(latency|_ms$|duration|time|cost|error|tokens|loss)/i;

// Which way is better for a metric: gates decide (min = higher, max = lower), otherwise a
// name-based guess.
export function metricDirection(metric, tags) {
  for (const tag of tags || []) {
    for (const rule of tag.gate?.rules || []) {
      if (rule.metric === metric) return rule.min != null ? "higher" : "lower";
    }
  }
  return LOWER_IS_BETTER.test(metric) ? "lower" : "higher";
}

export function metricUnit(metric) {
  if (/_ms$|latency/i.test(metric)) return "ms";
  if (/_s$|seconds/i.test(metric)) return "s";
  return "";
}

// One number format per column so values line up: precision from the column's scale.
export function metricFormatter(values, metric) {
  const finite = values.filter((v) => v != null && Number.isFinite(v));
  const max = finite.length ? Math.max(...finite.map(Math.abs)) : 0;
  const digits = max >= 100 ? 0 : max >= 10 ? 1 : 2;
  const unit = metricUnit(metric);
  return (value, withUnit = true) => {
    if (value == null) return "–";
    const text = Number(value).toLocaleString(undefined, {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
    return withUnit && unit ? `${text} ${unit}` : text;
  };
}

export function gateText(gate) {
  if (!gate || !gate.rules?.length) return null;
  const rules = gate.rules.map((rule) =>
    [rule.min != null && `${rule.metric} ≥ ${rule.min}`, rule.max != null && `${rule.metric} ≤ ${rule.max}`]
      .filter(Boolean)
      .join(", "),
  );
  return rules.join(" · ") + (gate.require_better_than_current ? " · at least as good as current" : "");
}

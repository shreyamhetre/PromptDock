import { useState } from "react";
import { TagPill, formatDate, timeAgo, versionLabel } from "./common.jsx";

function describe(event) {
  if (event.action === "rollback") {
    return `Rolled back to ${versionLabel(event.to_version)}`;
  }
  return event.from_version
    ? `Promoted ${versionLabel(event.from_version)} → ${versionLabel(event.to_version)}`
    : `First promote to ${versionLabel(event.to_version)}`;
}

export default function HistoryPanel({ events, tags }) {
  const [tag, setTag] = useState("");
  const shown = tag ? events.filter((e) => e.tag === tag) : events;
  const used = tags.filter((t) => events.some((e) => e.tag === t.name));

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Audit log</h2>
        {used.length > 1 && (
          <div className="segmented">
            <button className={tag === "" ? "on" : ""} onClick={() => setTag("")}>
              All
            </button>
            {used.map((t) => (
              <button key={t.name} className={tag === t.name ? "on" : ""} onClick={() => setTag(t.name)}>
                {t.name}
              </button>
            ))}
          </div>
        )}
      </div>
      {shown.length === 0 ? (
        <div className="empty">
          <strong>No promotes or rollbacks yet</strong>
          Every tag move will be recorded here with who, when and why.
        </div>
      ) : (
        <ul className="timeline">
          {shown.map((e) => {
            const kind = e.forced ? "forced" : e.action;
            const icon = e.forced ? "!" : e.action === "rollback" ? "↺" : "↑";
            return (
              <li key={e.id}>
                <span className={`event-icon ${kind}`} aria-hidden="true">
                  {icon}
                </span>
                <div>
                  <div className="event-title">
                    <TagPill name={e.tag} /> {describe(e)}
                  </div>
                  <div className="event-sub">
                    {e.action === "rollback" && e.from_version
                      ? `from ${versionLabel(e.from_version)} · `
                      : ""}
                    by {e.actor || "unknown"} · {formatDate(e.created_at)}
                  </div>
                  {e.reason && <div className="event-reason">“{e.reason}”</div>}
                </div>
                <div className="right">
                  {e.forced && <span className="pill" style={{ color: "var(--bad)" }}>Gate bypassed</span>}
                  <div className="event-sub">{timeAgo(e.created_at)}</div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

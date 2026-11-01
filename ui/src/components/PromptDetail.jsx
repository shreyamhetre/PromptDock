import { useState } from "react";
import { p } from "../api.js";
import { useApi } from "../useApi.js";
import { ErrorNotice, timeAgo, versionLabel } from "./common.jsx";
import DiffPanel from "./DiffPanel.jsx";
import HistoryPanel from "./HistoryPanel.jsx";
import LeaderboardPanel from "./LeaderboardPanel.jsx";
import TagsPanel from "./TagsPanel.jsx";
import VersionsPanel from "./VersionsPanel.jsx";

const TABS = [
  ["tags", "Deployments"],
  ["versions", "Versions"],
  ["leaderboard", "Leaderboard"],
  ["diff", "Compare"],
  ["history", "Audit log"],
];

function Stat({ label, value, sub }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

export default function PromptDetail({ name, tab }) {
  const [reloadKey, setReloadKey] = useState(0);
  const info = useApi(`${p(name)}/info`);
  const versions = useApi(`${p(name)}/versions`, null, reloadKey);
  const tags = useApi(`${p(name)}/tags`, null, reloadKey);
  const events = useApi(`${p(name)}/events`, null, reloadKey);
  const changed = () => setReloadKey((k) => k + 1);

  if (info.error) return <ErrorNotice error={info.error} />;

  const base = `#/p/${encodeURIComponent(name)}`;
  const ready = versions.data && tags.data && events.data;
  const latest = versions.data?.[versions.data.length - 1];
  const prod = tags.data?.find((t) => t.name === "prod");
  const lastEvent = events.data?.[0];
  const counts = { versions: versions.data?.length, history: events.data?.length };

  return (
    <>
      <div className="crumbs">
        <a href="#/">Prompts</a> / {name}
      </div>
      <div className="page-head">
        <div>
          <h1>{name}</h1>
          {info.data?.description && <p>{info.data.description}</p>}
        </div>
      </div>

      {ready && (
        <div className="stats">
          <Stat
            label="Live in prod"
            value={versionLabel(prod?.version)}
            sub={prod?.version ? `since ${timeAgo(prod.updated_at)}` : "not promoted yet"}
          />
          <Stat
            label="Latest version"
            value={versionLabel(latest?.version)}
            sub={latest ? `saved ${timeAgo(latest.created_at)}` : "no versions yet"}
          />
          <Stat
            label="Versions"
            value={versions.data.length}
            sub={latest?.created_by ? `latest by ${latest.created_by}` : " "}
          />
          <Stat
            label="Last change"
            value={lastEvent ? timeAgo(lastEvent.created_at) : "–"}
            sub={
              lastEvent
                ? `${lastEvent.tag} ${lastEvent.action === "rollback" ? "rolled back to" : "→"} ${versionLabel(lastEvent.to_version)}${lastEvent.actor ? ` by ${lastEvent.actor}` : ""}`
                : "no promotes yet"
            }
          />
        </div>
      )}

      <nav className="tabs">
        {TABS.map(([key, label]) => (
          <a key={key} href={`${base}/${key}`} className={tab === key ? "active" : ""}>
            {label}
            {counts[key] != null && <span className="tab-count">{counts[key]}</span>}
          </a>
        ))}
      </nav>

      <ErrorNotice error={versions.error || tags.error || events.error} />
      {!ready ? (
        <div className="skeleton" />
      ) : (
        <>
          {tab === "tags" && (
            <TagsPanel
              name={name}
              tags={tags.data}
              versions={versions.data}
              events={events.data}
              onChange={changed}
            />
          )}
          {tab === "versions" && <VersionsPanel versions={versions.data} tags={tags.data} />}
          {tab === "leaderboard" && (
            <LeaderboardPanel name={name} tags={tags.data} reloadKey={reloadKey} />
          )}
          {tab === "diff" && <DiffPanel name={name} versions={versions.data} />}
          {tab === "history" && <HistoryPanel events={events.data} tags={tags.data} />}
        </>
      )}
    </>
  );
}

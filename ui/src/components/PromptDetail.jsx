import { useState } from "react";
import { p } from "../api.js";
import { useApi } from "../useApi.js";
import { ErrorNotice } from "./common.jsx";
import DiffPanel from "./DiffPanel.jsx";
import HistoryPanel from "./HistoryPanel.jsx";
import LeaderboardPanel from "./LeaderboardPanel.jsx";
import TagsPanel from "./TagsPanel.jsx";
import VersionsPanel from "./VersionsPanel.jsx";

const TABS = [
  ["tags", "Tags"],
  ["versions", "Versions"],
  ["leaderboard", "Leaderboard"],
  ["diff", "Diff"],
  ["history", "Audit log"],
];

export default function PromptDetail({ name, tab }) {
  const [reloadKey, setReloadKey] = useState(0);
  const info = useApi(`${p(name)}/info`);
  const versions = useApi(`${p(name)}/versions`, null, reloadKey);
  const tags = useApi(`${p(name)}/tags`, null, reloadKey);
  const changed = () => setReloadKey((k) => k + 1);

  if (info.error) return <ErrorNotice error={info.error} />;

  const base = `#/p/${encodeURIComponent(name)}`;
  const ready = versions.data && tags.data;
  return (
    <>
      <div className="muted">
        <a href="#/">Prompts</a> / {name}
      </div>
      <h1>{name}</h1>
      {info.data?.description && <p className="subtle">{info.data.description}</p>}
      <nav className="tabs">
        {TABS.map(([key, label]) => (
          <a key={key} href={`${base}/${key}`} className={tab === key ? "active" : ""}>
            {label}
          </a>
        ))}
      </nav>
      <ErrorNotice error={versions.error || tags.error} />
      {!ready ? (
        <p className="muted">Loading…</p>
      ) : (
        <>
          {tab === "tags" && (
            <TagsPanel name={name} tags={tags.data} versions={versions.data} onChange={changed} />
          )}
          {tab === "versions" && <VersionsPanel versions={versions.data} tags={tags.data} />}
          {tab === "leaderboard" && <LeaderboardPanel name={name} reloadKey={reloadKey} />}
          {tab === "diff" && <DiffPanel name={name} versions={versions.data} />}
          {tab === "history" && <HistoryPanel name={name} tags={tags.data} reloadKey={reloadKey} />}
        </>
      )}
    </>
  );
}

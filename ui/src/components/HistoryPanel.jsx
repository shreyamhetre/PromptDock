import { useState } from "react";
import { p } from "../api.js";
import { formatDate, useApi } from "../useApi.js";
import { ErrorNotice, versionLabel } from "./common.jsx";

export default function HistoryPanel({ name, tags, reloadKey }) {
  const [tag, setTag] = useState("");
  const path = tag ? `${p(name)}/tags/${encodeURIComponent(tag)}/events` : `${p(name)}/events`;
  const { data: events, error } = useApi(path, null, reloadKey);

  return (
    <>
      <div className="row" style={{ marginBottom: 12 }}>
        <label className="row" style={{ margin: 0 }}>
          Tag
          <select value={tag} onChange={(e) => setTag(e.target.value)}>
            <option value="">All tags</option>
            {tags.map((t) => (
              <option key={t.name} value={t.name}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <ErrorNotice error={error} />
      {events && events.length === 0 && <p className="muted">No promotes or rollbacks yet.</p>}
      {events && events.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>When</th>
              <th>Tag</th>
              <th>Action</th>
              <th>From → to</th>
              <th>Who</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id}>
                <td className="subtle">{formatDate(e.created_at)}</td>
                <td>{e.tag}</td>
                <td>
                  {e.action}
                  {e.forced && <span className="chip">⚠️ forced</span>}
                </td>
                <td>
                  {versionLabel(e.from_version)} → <strong>{versionLabel(e.to_version)}</strong>
                </td>
                <td>{e.actor || <span className="muted">unknown</span>}</td>
                <td>{e.reason || ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

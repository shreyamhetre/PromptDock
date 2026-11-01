import { useEffect, useState } from "react";
import { api, p } from "../api.js";
import { useApi } from "../useApi.js";
import { ErrorNotice, STAGES, TagPill, timeAgo, versionLabel } from "./common.jsx";

export default function PromptList() {
  const { data: prompts, error } = useApi("/prompts");
  const [details, setDetails] = useState({});

  useEffect(() => {
    if (!prompts) return;
    Promise.all(
      prompts.map((prompt) =>
        Promise.all([api(`${p(prompt.name)}/tags`), api(`${p(prompt.name)}/versions`)]).then(
          ([tags, versions]) => [prompt.name, { tags, versions }],
        ),
      ),
    ).then((pairs) => setDetails(Object.fromEntries(pairs)), () => {});
  }, [prompts]);

  if (error) return <ErrorNotice error={error} />;

  const open = (name) => (window.location.hash = `#/p/${encodeURIComponent(name)}`);
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Prompts</h1>
          <p>Versioned prompts and where each environment points.</p>
        </div>
      </div>
      <div className="panel">
        {!prompts ? (
          <div className="panel-body">
            <div className="skeleton" />
          </div>
        ) : prompts.length === 0 ? (
          <div className="empty">
            <strong>No prompts yet</strong>
            Create some from the terminal with <code>promptdock push ./prompts</code>.
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Prompt</th>
                {STAGES.map((stage) => (
                  <th key={stage}>{stage}</th>
                ))}
                <th className="right">Versions</th>
                <th className="right">Updated</th>
              </tr>
            </thead>
            <tbody>
              {prompts.map((prompt) => {
                const d = details[prompt.name];
                const byName = Object.fromEntries((d?.tags || []).map((t) => [t.name, t]));
                const latest = d?.versions?.[d.versions.length - 1];
                return (
                  <tr key={prompt.id} className="clickable" onClick={() => open(prompt.name)}>
                    <td>
                      <a href={`#/p/${encodeURIComponent(prompt.name)}`} style={{ fontWeight: 600 }}>
                        {prompt.name}
                      </a>
                      {prompt.description && <div className="muted">{prompt.description}</div>}
                    </td>
                    {STAGES.map((stage) => (
                      <td key={stage} className="mono">
                        {byName[stage]?.version ? (
                          versionLabel(byName[stage].version)
                        ) : (
                          <span className="faint">–</span>
                        )}
                      </td>
                    ))}
                    <td className="right num">{d ? d.versions.length : ""}</td>
                    <td className="right muted nowrap">{latest ? timeAgo(latest.created_at) : ""}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
      {prompts && prompts.length > 0 && (
        <p className="muted" style={{ marginTop: 12, fontSize: 12.5 }}>
          Legend: <TagPill name="dev" /> <TagPill name="preprod" /> <TagPill name="prod" /> — apps
          read a tag; promoting or rolling back changes what they get, with no code change.
        </p>
      )}
    </>
  );
}

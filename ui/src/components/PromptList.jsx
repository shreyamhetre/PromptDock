import { useEffect, useState } from "react";
import { api, p } from "../api.js";
import { useApi } from "../useApi.js";
import { ErrorNotice } from "./common.jsx";

export default function PromptList() {
  const { data: prompts, error, loading } = useApi("/prompts");
  const [tags, setTags] = useState({});

  useEffect(() => {
    if (!prompts) return;
    Promise.all(
      prompts.map((prompt) =>
        api(`${p(prompt.name)}/tags`).then((list) => [prompt.name, list]),
      ),
    ).then((pairs) => setTags(Object.fromEntries(pairs)), () => {});
  }, [prompts]);

  if (error) return <ErrorNotice error={error} />;
  if (loading && !prompts) return <p className="muted">Loading…</p>;

  return (
    <>
      <h1>Prompts</h1>
      <p className="subtle">Click a prompt to see its versions, tags, scores and history.</p>
      {prompts.length === 0 ? (
        <div className="card">
          No prompts yet. Create some from the terminal: <code>promptdock push ./prompts</code>
        </div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Description</th>
              <th>Tags</th>
            </tr>
          </thead>
          <tbody>
            {prompts.map((prompt) => (
              <tr
                key={prompt.id}
                className="clickable"
                onClick={() => (window.location.hash = `#/p/${encodeURIComponent(prompt.name)}`)}
              >
                <td>
                  <a href={`#/p/${encodeURIComponent(prompt.name)}`}>{prompt.name}</a>
                </td>
                <td className="subtle">{prompt.description || ""}</td>
                <td>
                  {(tags[prompt.name] || []).map((tag) => (
                    <span className="chip" key={tag.name}>
                      {tag.name} <strong>{tag.version ? `v${tag.version}` : "–"}</strong>
                    </span>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

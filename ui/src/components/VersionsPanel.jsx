import { Fragment, useState } from "react";
import { CopyButton, TagPill, Template, formatDate, templateText, timeAgo } from "./common.jsx";

export default function VersionsPanel({ versions, tags }) {
  const [open, setOpen] = useState(versions.length ? versions[versions.length - 1].version : null);
  const tagsOf = (version) => tags.filter((t) => t.version === version).map((t) => t.name);

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Versions</h2>
        <span className="hint">Versions never change · click a row to see its template</span>
      </div>
      <table>
        <thead>
          <tr>
            <th>Version</th>
            <th>Message</th>
            <th>Tags</th>
            <th>Author</th>
            <th className="right">Saved</th>
          </tr>
        </thead>
        <tbody>
          {[...versions].reverse().map((v) => {
            const expanded = open === v.version;
            return (
              <Fragment key={v.version}>
                <tr
                  className={`clickable${expanded ? " expanded" : ""}`}
                  onClick={() => setOpen(expanded ? null : v.version)}
                >
                  <td className="nowrap">
                    <span className="faint">{expanded ? "▾" : "▸"}</span>{" "}
                    <strong className="mono">v{v.version}</strong>
                  </td>
                  <td>{v.commit_message || <span className="faint">No message</span>}</td>
                  <td>
                    {tagsOf(v.version).map((t) => (
                      <TagPill key={t} name={t} />
                    ))}
                  </td>
                  <td className="muted">{v.created_by || "–"}</td>
                  <td className="right muted nowrap" title={formatDate(v.created_at)}>
                    {timeAgo(v.created_at)}
                  </td>
                </tr>
                {expanded && (
                  <tr className="expanded">
                    <td colSpan={5} style={{ padding: 0 }}>
                      <div className="detail">
                        <div>
                          <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
                            <strong>
                              {v.template_type === "chat" ? "Chat template" : "Text template"}
                            </strong>
                            <CopyButton text={templateText(v.template)} />
                          </div>
                          <Template template={v.template} />
                        </div>
                        <dl className="kv detail-side">
                          <dt>Variables</dt>
                          <dd className="chips">
                            {v.variables.length ? (
                              v.variables.map((name) => (
                                <span key={name} className="var mono">
                                  {name}
                                </span>
                              ))
                            ) : (
                              <span className="faint">none</span>
                            )}
                          </dd>
                          <dt>Model config</dt>
                          <dd className="cfg">
                            {Object.keys(v.model_config).length ? (
                              Object.entries(v.model_config).map(([key, value]) => (
                                <div key={key}>
                                  <span>{key}:</span> {JSON.stringify(value)}
                                </div>
                              ))
                            ) : (
                              <span className="faint">none</span>
                            )}
                          </dd>
                          <dt>Saved</dt>
                          <dd>{formatDate(v.created_at)}</dd>
                          <dt>Content hash</dt>
                          <dd className="mono faint">{v.content_hash.slice(0, 12)}</dd>
                        </dl>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

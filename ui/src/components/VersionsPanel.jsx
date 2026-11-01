import { Fragment, useState } from "react";
import { formatDate } from "../useApi.js";
import { Template } from "./common.jsx";

export default function VersionsPanel({ versions, tags }) {
  const [open, setOpen] = useState(versions.length ? versions[versions.length - 1].version : null);
  const tagsOf = (version) => tags.filter((t) => t.version === version).map((t) => t.name);

  return (
    <table>
      <thead>
        <tr>
          <th>Version</th>
          <th>Tags</th>
          <th>Created</th>
          <th>By</th>
          <th>Message</th>
        </tr>
      </thead>
      <tbody>
        {[...versions].reverse().map((v) => (
          <Fragment key={v.version}>
            <tr className="clickable" onClick={() => setOpen(open === v.version ? null : v.version)}>
              <td>
                <strong>v{v.version}</strong>
              </td>
              <td>
                {tagsOf(v.version).map((t) => (
                  <span className="chip" key={t}>
                    {t}
                  </span>
                ))}
              </td>
              <td className="subtle">{formatDate(v.created_at)}</td>
              <td className="subtle">{v.created_by || "–"}</td>
              <td>{v.commit_message || ""}</td>
            </tr>
            {open === v.version && (
              <tr>
                <td colSpan={5}>
                  <div className="subtle" style={{ marginBottom: 6 }}>
                    Variables: {v.variables.length ? v.variables.join(", ") : "none"} · model_config:{" "}
                    <code>{JSON.stringify(v.model_config)}</code>
                  </div>
                  <Template template={v.template} />
                </td>
              </tr>
            )}
          </Fragment>
        ))}
      </tbody>
    </table>
  );
}

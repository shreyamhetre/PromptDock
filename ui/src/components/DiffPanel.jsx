import { useState } from "react";
import { p } from "../api.js";
import { useApi } from "../useApi.js";
import { ErrorNotice } from "./common.jsx";

function DiffLines({ text }) {
  return (
    <div className="diff mono">
      {text.split("\n").map((line, i) => {
        let kind = "";
        if (line.startsWith("@@")) kind = "hunk";
        else if (line.startsWith("+") && !line.startsWith("+++")) kind = "add";
        else if (line.startsWith("-") && !line.startsWith("---")) kind = "del";
        return (
          <div key={i} className={kind}>
            {line || " "}
          </div>
        );
      })}
    </div>
  );
}

export default function DiffPanel({ name, versions }) {
  const numbers = versions.map((v) => v.version);
  const last = numbers[numbers.length - 1];
  const [a, setA] = useState(numbers.length > 1 ? numbers[numbers.length - 2] : last);
  const [b, setB] = useState(last);
  const { data, error } = useApi(`${p(name)}/diff`, { a, b });

  const picker = (value, set, label) => (
    <label className="row" style={{ margin: 0 }}>
      {label}
      <select value={value} onChange={(e) => set(Number(e.target.value))}>
        {[...numbers].reverse().map((n) => (
          <option key={n} value={n}>
            v{n}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <>
      <div className="row" style={{ marginBottom: 12 }}>
        {picker(a, setA, "Compare")}
        {picker(b, setB, "with")}
      </div>
      <ErrorNotice error={error} />
      {data && (
        <>
          <h2>Template</h2>
          {data.template_changed ? (
            <DiffLines text={data.template_diff.trimEnd()} />
          ) : (
            <p className="muted">Unchanged.</p>
          )}
          <h2>model_config</h2>
          {data.model_config_changes.length === 0 ? (
            <p className="muted">Unchanged.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Key</th>
                  <th>Change</th>
                  <th>v{data.a}</th>
                  <th>v{data.b}</th>
                </tr>
              </thead>
              <tbody>
                {data.model_config_changes.map((c) => (
                  <tr key={c.key}>
                    <td className="mono">{c.key}</td>
                    <td>{c.change}</td>
                    <td className="mono">{c.change === "added" ? "–" : JSON.stringify(c.a)}</td>
                    <td className="mono">{c.change === "removed" ? "–" : JSON.stringify(c.b)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <h2>Variables</h2>
          <p>
            {data.variables_added.length === 0 && data.variables_removed.length === 0 && (
              <span className="muted">Unchanged.</span>
            )}
            {data.variables_added.length > 0 && <>Added: {data.variables_added.join(", ")}. </>}
            {data.variables_removed.length > 0 && <>Removed: {data.variables_removed.join(", ")}.</>}
          </p>
        </>
      )}
    </>
  );
}

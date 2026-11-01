import { useState } from "react";
import { p } from "../api.js";
import { useApi } from "../useApi.js";
import { ErrorNotice } from "./common.jsx";

function DiffLines({ text }) {
  // Skip the "--- vA / +++ vB" file header; the panel heading already says which is which.
  const lines = text.trimEnd().split("\n").filter((l) => !l.startsWith("---") && !l.startsWith("+++"));
  return (
    <div className="diff">
      {lines.map((line, i) => {
        let kind = "";
        let mark = "";
        if (line.startsWith("@@")) kind = "hunk";
        else if (line.startsWith("+")) [kind, mark] = ["add", "+"];
        else if (line.startsWith("-")) [kind, mark] = ["del", "−"];
        const content = kind === "hunk" ? "" : line.slice(1);
        return (
          <div key={i} className={`line ${kind}`}>
            <span className="gutter">{mark}</span>
            <span className="content">{content || " "}</span>
          </div>
        );
      })}
    </div>
  );
}

function countChanges(text) {
  const lines = text.split("\n");
  return {
    added: lines.filter((l) => l.startsWith("+") && !l.startsWith("+++")).length,
    removed: lines.filter((l) => l.startsWith("-") && !l.startsWith("---")).length,
  };
}

export default function DiffPanel({ name, versions }) {
  const numbers = versions.map((v) => v.version);
  const last = numbers[numbers.length - 1];
  const [a, setA] = useState(numbers.length > 1 ? numbers[numbers.length - 2] : last);
  const [b, setB] = useState(last);
  const { data, error } = useApi(`${p(name)}/diff`, { a, b });

  const picker = (value, set, label) => (
    <select value={value} aria-label={label} onChange={(e) => set(Number(e.target.value))}>
      {[...numbers].reverse().map((n) => (
        <option key={n} value={n}>
          v{n}
        </option>
      ))}
    </select>
  );
  const changes = data?.template_changed ? countChanges(data.template_diff) : null;

  return (
    <>
      <div className="panel">
        <div className="panel-head">
          <div className="row">
            {picker(a, setA, "Base version")}
            <span className="muted">→</span>
            {picker(b, setB, "Compared version")}
            <button className="ghost small" onClick={() => [setA(b), setB(a)]} title="Swap">
              ⇄ Swap
            </button>
          </div>
          {data && (
            <div className="row">
              {changes ? (
                <>
                  {changes.added > 0 && (
                    <span className="pill" style={{ color: "var(--good)" }}>
                      +{changes.added} line{changes.added === 1 ? "" : "s"}
                    </span>
                  )}
                  {changes.removed > 0 && (
                    <span className="pill" style={{ color: "var(--bad)" }}>
                      −{changes.removed} line{changes.removed === 1 ? "" : "s"}
                    </span>
                  )}
                </>
              ) : (
                <span className="pill">Template unchanged</span>
              )}
              <span className="pill">
                {data.model_config_changes.length} config change
                {data.model_config_changes.length === 1 ? "" : "s"}
              </span>
            </div>
          )}
        </div>
        <ErrorNotice error={error} />
        {data &&
          (data.template_changed ? (
            <DiffLines text={data.template_diff} />
          ) : (
            <div className="empty">
              <strong>Same template</strong>v{data.a} and v{data.b} have identical template text.
            </div>
          ))}
      </div>

      {data && (data.model_config_changes.length > 0 || data.variables_added.length > 0 || data.variables_removed.length > 0) && (
        <div className="panel">
          <div className="panel-head">
            <h2>Settings and variables</h2>
          </div>
          <table>
            <thead>
              <tr>
                <th>Field</th>
                <th>Change</th>
                <th>v{data.a}</th>
                <th>v{data.b}</th>
              </tr>
            </thead>
            <tbody>
              {data.model_config_changes.map((c) => (
                <tr key={c.key}>
                  <td className="mono">model_config.{c.key}</td>
                  <td className="muted">{c.change}</td>
                  <td className="mono">{c.change === "added" ? "–" : JSON.stringify(c.a)}</td>
                  <td className="mono">{c.change === "removed" ? "–" : JSON.stringify(c.b)}</td>
                </tr>
              ))}
              {data.variables_added.map((v) => (
                <tr key={`+${v}`}>
                  <td className="mono">{`{{ ${v} }}`}</td>
                  <td className="muted">variable added</td>
                  <td>–</td>
                  <td className="mono">required</td>
                </tr>
              ))}
              {data.variables_removed.map((v) => (
                <tr key={`-${v}`}>
                  <td className="mono">{`{{ ${v} }}`}</td>
                  <td className="muted">variable removed</td>
                  <td className="mono">required</td>
                  <td>–</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

export function ErrorNotice({ error }) {
  if (!error) return null;
  return (
    <div className="notice error" role="alert">
      {error.type === "GateFailedError" ? (
        <>
          ⛔ <strong>Refused by the gate.</strong> These rules failed:
        </>
      ) : (
        <>
          ⛔ <strong>Error:</strong> {error.message}
        </>
      )}
      {error.failures?.length > 0 && (
        <ul>
          {error.failures.map((failure) => (
            <li key={failure}>{failure}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Template({ template }) {
  if (typeof template === "string") return <div className="template mono">{template}</div>;
  return template.map((message, i) => (
    <div key={i}>
      <div className="role">{message.role}</div>
      <div className="template mono">{message.content}</div>
    </div>
  ));
}

export function versionLabel(version) {
  return version ? `v${version}` : "–";
}

import { useState } from "react";
import { settings } from "../api.js";
import { Dialog, Notice } from "./common.jsx";

// Asks once for the user's name (recorded as the actor of promotes and rollbacks) and,
// if the server has one, the shared token. Both are kept in this browser only.
export default function Settings({ needsToken, onSaved, onClose }) {
  const [actor, setActor] = useState(settings.actor);
  const [token, setToken] = useState(settings.token);

  const submit = (event) => {
    event?.preventDefault();
    if (!actor.trim()) return;
    settings.save(actor, token);
    onSaved();
  };

  return (
    <Dialog
      title={settings.actor ? "Settings" : "Welcome to PromptDock"}
      description="Your name is recorded in the audit log when you promote or roll back. It is not verified, like a git author."
      onClose={onClose}
      footer={
        <>
          {onClose && <button onClick={onClose}>Cancel</button>}
          <button className="primary" disabled={!actor.trim()} onClick={submit}>
            Save
          </button>
        </>
      }
    >
      <form onSubmit={submit}>
        <label className="field" htmlFor="actor">
          Your name
        </label>
        <input
          id="actor"
          type="text"
          value={actor}
          autoFocus
          onChange={(e) => setActor(e.target.value)}
          placeholder="e.g. shreya"
        />
        <label className="field" htmlFor="token">
          Server token
        </label>
        <input
          id="token"
          type="password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="Only if the server has one"
        />
        <div className="help">Both are stored in this browser only.</div>
        {needsToken && (
          <Notice kind="error">This server needs a token, or the saved one is wrong.</Notice>
        )}
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}

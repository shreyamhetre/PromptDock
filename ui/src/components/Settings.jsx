import { useState } from "react";
import { settings } from "../api.js";

// Asks once for the user's name (recorded as the actor of promotes and rollbacks) and,
// if the server has one, the shared token. Both are kept in this browser only.
export default function Settings({ needsToken, onSaved, onClose }) {
  const [actor, setActor] = useState(settings.actor);
  const [token, setToken] = useState(settings.token);

  const submit = (event) => {
    event.preventDefault();
    if (!actor.trim()) return;
    settings.save(actor, token);
    onSaved();
  };

  return (
    <div className="modal-backdrop">
      <form className="card modal" onSubmit={submit}>
        <h2 style={{ marginTop: 0 }}>Who are you?</h2>
        <p className="subtle">
          Your name is recorded in the history when you promote or roll back. It is not
          verified, like a git author.
        </p>
        <label htmlFor="actor">Your name</label>
        <input
          id="actor"
          type="text"
          value={actor}
          autoFocus
          onChange={(e) => setActor(e.target.value)}
          placeholder="e.g. shreya"
        />
        <label htmlFor="token">Server token (only if the server has one)</label>
        <input
          id="token"
          type="password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="leave empty if not needed"
        />
        {needsToken && (
          <div className="notice error">⛔ This server needs a token, or the saved one is wrong.</div>
        )}
        <div className="row" style={{ marginTop: 16, justifyContent: "flex-end" }}>
          {onClose && (
            <button type="button" onClick={onClose}>
              Cancel
            </button>
          )}
          <button type="submit" className="primary" disabled={!actor.trim()}>
            Save
          </button>
        </div>
      </form>
    </div>
  );
}

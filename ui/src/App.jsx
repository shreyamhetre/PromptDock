import { useEffect, useState } from "react";
import { onUnauthorized, settings } from "./api.js";
import PromptDetail from "./components/PromptDetail.jsx";
import PromptList from "./components/PromptList.jsx";
import Settings from "./components/Settings.jsx";

// Hash routes keep the UI from clashing with API paths:
//   #/                       prompts list
//   #/p/<name>/<tab>         prompt detail (tags, versions, leaderboard, diff, history)
function parseRoute() {
  const parts = window.location.hash.replace(/^#\/?/, "").split("/").map(decodeURIComponent);
  if (parts[0] === "p" && parts[1]) return { page: "prompt", name: parts[1], tab: parts[2] || "tags" };
  return { page: "list" };
}

export default function App() {
  const [route, setRoute] = useState(parseRoute);
  const [showSettings, setShowSettings] = useState(!settings.actor);
  const [needsToken, setNeedsToken] = useState(false);
  const [settingsVersion, setSettingsVersion] = useState(0);

  useEffect(() => {
    const onHash = () => setRoute(parseRoute());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(
    () =>
      onUnauthorized(() => {
        setNeedsToken(true);
        setShowSettings(true);
      }),
    [],
  );

  const saved = () => {
    setShowSettings(false);
    setNeedsToken(false);
    setSettingsVersion((v) => v + 1); // re-fetch with the new name/token
  };

  const initial = (settings.actor || "?").trim().charAt(0).toUpperCase();
  return (
    <>
      <header className="topbar">
        <a className="brand" href="#/">
          <span className="brand-mark">P</span>
          PromptDock
        </a>
        <nav className="topnav">
          <a href="#/" className={route.page === "list" ? "active" : ""}>
            Prompts
          </a>
        </nav>
        <span className="spacer" />
        <button className="user-chip" onClick={() => setShowSettings(true)} title="Settings">
          <span className="avatar">{initial}</span>
          {settings.actor || "Set your name"}
        </button>
      </header>
      <main key={settingsVersion}>
        {route.page === "prompt" ? (
          <PromptDetail name={route.name} tab={route.tab} />
        ) : (
          <PromptList />
        )}
      </main>
      {showSettings && (
        <Settings
          needsToken={needsToken}
          onSaved={saved}
          onClose={settings.actor ? () => setShowSettings(false) : null}
        />
      )}
    </>
  );
}

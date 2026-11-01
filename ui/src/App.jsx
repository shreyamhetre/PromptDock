import { useEffect, useState } from "react";
import { onUnauthorized, settings } from "./api.js";
import PromptList from "./components/PromptList.jsx";
import PromptDetail from "./components/PromptDetail.jsx";
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

  return (
    <>
      <header className="topbar">
        <a className="brand" href="#/">PromptDock</a>
        <span className="spacer" />
        <span className="who">{settings.actor ? `Signed as ${settings.actor}` : "No name set"}</span>
        <button onClick={() => setShowSettings(true)}>Settings</button>
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

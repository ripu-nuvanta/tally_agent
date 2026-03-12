import { useEffect, useState } from "react";
import { getHealth, getTallyMode, setTallyMode } from "../api/client";
import CompanySelector from "./CompanySelector";

export default function Header() {
  const [connected, setConnected] = useState<boolean | null>(null);
  const [tallyMode, setTallyModeState] = useState<"mock" | "live">("live");

  useEffect(() => {
    // Initialize tally mode from backend
    getTallyMode()
      .then((res) => setTallyModeState(res.mode))
      .catch(() => {});

    // Health polling
    const checkHealth = () => {
      getHealth()
        .then((res) => {
          setConnected(res.tally_connected);
          if (res.mode) setTallyModeState(res.mode);
        })
        .catch(() => setConnected(false));
    };

    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleToggleMode = async () => {
    const newMode = tallyMode === "live" ? "mock" : "live";
    try {
      const res = await setTallyMode(newMode);
      setTallyModeState(res.mode);
      // Re-check health after mode switch
      getHealth()
        .then((res) => {
          setConnected(res.tally_connected);
        })
        .catch(() => setConnected(false));
    } catch {
      // Reconcile on error
      getTallyMode()
        .then((res) => setTallyModeState(res.mode))
        .catch(() => {});
    }
  };

  const isMock = tallyMode === "mock";

  return (
    <header className="border-b border-gray-200 bg-white px-4 py-3 flex items-center justify-between">
      <h1 className="text-lg font-semibold text-gray-900">TallyPrime AI</h1>
      <div className="flex items-center gap-3">
        <button
          onClick={handleToggleMode}
          data-testid="tally-mode-toggle"
          className="flex items-center gap-1.5 px-2 py-1 rounded text-xs border border-gray-200 hover:bg-gray-50 transition-colors"
          title={isMock ? "Switch to Live Tally" : "Switch to Mock Tally"}
        >
          <div
            data-testid="tally-mode-indicator"
            className={`w-2 h-2 rounded-full ${
              isMock
                ? "bg-green-500"
                : connected === null
                  ? "bg-gray-300"
                  : connected
                    ? "bg-green-500"
                    : "bg-red-500"
            }`}
          />
          <span data-testid="tally-mode-label">
            {isMock ? "Mock Tally" : "Tally"}
          </span>
        </button>
        <CompanySelector />
      </div>
    </header>
  );
}

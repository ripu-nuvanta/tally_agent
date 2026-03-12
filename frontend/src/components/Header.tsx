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
      await setTallyMode(newMode);
      window.location.reload();
    } catch {
      // Reconcile on error — don't refresh
      getTallyMode()
        .then((res) => setTallyModeState(res.mode))
        .catch(() => {});
    }
  };

  const isMock = tallyMode === "mock";

  // Status dot color: green for mock or live+connected, red for live+disconnected, gray for checking
  const dotColor = isMock
    ? "bg-green-500"
    : connected === null
      ? "bg-gray-300"
      : connected
        ? "bg-green-500"
        : "bg-red-500";

  return (
    <header className="border-b border-gray-200 bg-white px-4 py-3 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-semibold text-gray-900">TallyPrime AI</h1>
        {/* Demo Mode toggle switch */}
        <label
          data-testid="demo-mode-toggle"
          className="flex items-center gap-2 cursor-pointer select-none"
        >
          <span className="text-xs text-gray-600">Demo Mode</span>
          <div className="relative">
            <input
              type="checkbox"
              data-testid="demo-mode-checkbox"
              className="sr-only peer"
              checked={isMock}
              onChange={handleToggleMode}
            />
            <div className="w-9 h-5 bg-gray-200 rounded-full peer peer-checked:bg-blue-500 transition-colors" />
            <div className="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform peer-checked:translate-x-4" />
          </div>
        </label>
      </div>
      <div className="flex items-center gap-3">
        {/* Status indicator (non-clickable) */}
        <span
          data-testid="tally-status-indicator"
          className="flex items-center gap-1.5 text-xs text-gray-600"
        >
          <span
            data-testid="tally-status-dot"
            className={`w-2 h-2 rounded-full ${dotColor}`}
          />
          <span data-testid="tally-status-label">
            {isMock ? "Demo" : "Tally"}
          </span>
        </span>
        <CompanySelector />
      </div>
    </header>
  );
}

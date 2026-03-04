import { useEffect, useState } from "react";
import { getHealth } from "../api/client";
import CompanySelector from "./CompanySelector";

export default function Header() {
  const [connected, setConnected] = useState<boolean | null>(null);

  useEffect(() => {
    getHealth()
      .then((res) => setConnected(res.tally_connected))
      .catch(() => setConnected(false));

    const interval = setInterval(() => {
      getHealth()
        .then((res) => setConnected(res.tally_connected))
        .catch(() => setConnected(false));
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  return (
    <header className="border-b border-gray-200 bg-white px-4 py-3 flex items-center justify-between">
      <h1 className="text-lg font-semibold text-gray-900">TallyPrime AI</h1>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5" title={connected ? "Tally connected" : "Tally disconnected"}>
          <div
            className={`w-2 h-2 rounded-full ${
              connected === null
                ? "bg-gray-300"
                : connected
                  ? "bg-green-500"
                  : "bg-red-500"
            }`}
          />
          <span className="text-xs text-gray-500">Tally</span>
        </div>
        <CompanySelector />
      </div>
    </header>
  );
}

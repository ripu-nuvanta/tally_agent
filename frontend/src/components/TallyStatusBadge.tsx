import { useEffect, useState } from "react";
import { getHealth } from "../api/client";

interface TallyStatusBadgeProps {
  config: Record<string, unknown>; // active workspace config
}

type Status = "checking" | "connected" | "disconnected";

const POLL_MS = 30000;

/** Heartbeat badge: polls /api/health for the active workspace's Tally host
 *  every 30s. Demo workspaces render a static Demo badge (no polling). */
export default function TallyStatusBadge({ config }: TallyStatusBadgeProps) {
  const mockMode = config.mock_mode === true;
  const host = (config.tally_host as string) || "localhost";
  const port = (config.tally_port as number) || 9000;
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    if (mockMode) return;
    let cancelled = false;
    setStatus("checking");
    const check = async () => {
      try {
        const h = await getHealth({ host, port });
        if (!cancelled) setStatus(h.tally_connected ? "connected" : "disconnected");
      } catch {
        if (!cancelled) setStatus("disconnected");
      }
    };
    check();
    const id = setInterval(check, POLL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, [mockMode, host, port]);

  if (mockMode) {
    return (
      <span data-testid="header-workspace-badge" data-status="demo" className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full bg-orange-100 text-orange-700 shrink-0">
        <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
        Demo
      </span>
    );
  }

  const styles: Record<Status, { badge: string; dot: string; label: string }> = {
    checking: { badge: "bg-gray-100 text-gray-500", dot: "bg-gray-400 animate-pulse", label: "Checking…" },
    connected: { badge: "bg-green-100 text-green-700", dot: "bg-green-500", label: "Live" },
    disconnected: { badge: "bg-red-100 text-red-700", dot: "bg-red-500", label: "Offline" },
  };
  const s = styles[status];
  return (
    <span
      data-testid="header-workspace-badge"
      data-status={status}
      title={`Tally at ${host}:${port}`}
      className={`inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full shrink-0 ${s.badge}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  );
}

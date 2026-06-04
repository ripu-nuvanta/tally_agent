import { useState } from "react";
import { createWorkspace, getCompanies } from "../api/client";
import type { WorkspaceData } from "../types";

interface ConnectCompanyModalProps {
  onClose: () => void;
  onCreated: (workspace: WorkspaceData) => void;
}

export default function ConnectCompanyModal({ onClose, onCreated }: ConnectCompanyModalProps) {
  const [step, setStep] = useState<"form" | "connected">("form");
  const [name, setName] = useState("");
  const [tallyHost, setTallyHost] = useState("localhost");
  const [tallyPort, setTallyPort] = useState("9000");
  const [mockMode, setMockMode] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [companyName, setCompanyName] = useState("");
  const [workspace, setWorkspace] = useState<WorkspaceData | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    const portNum = parseInt(tallyPort, 10);
    const safePort = Number.isNaN(portNum) ? 9000 : portNum;
    try {
      const res = await getCompanies(
        mockMode ? { mock: true } : { host: tallyHost, port: safePort },
      );
      if (!res.companies.length) throw new Error("No companies loaded in Tally");
      const actualCompany = res.companies[0].name;
      const ws = await createWorkspace({
        name,
        config: {
          tally_host: tallyHost,
          tally_port: safePort,
          mock_mode: mockMode,
          tally_company: actualCompany,
        },
      });
      setCompanyName(actualCompany);
      setWorkspace(ws);
      setStep("connected");
    } catch (err) {
      if (err instanceof Error && err.message === "No companies loaded in Tally") {
        setError("Connected, but no company is loaded in Tally. Open a company in Tally and try again.");
      } else {
        setError("Failed to connect. Check that Tally is running at the given host/port with a company loaded.");
      }
    } finally {
      setLoading(false);
    }
  };

  if (step === "connected" && workspace) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg shadow-lg p-6 w-full mx-4 md:mx-auto md:max-w-md">
          <div className="flex items-center gap-2 mb-4">
            <span className="w-6 h-6 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-sm">✓</span>
            <h2 className="text-lg font-semibold text-gray-900">Company Connected</h2>
          </div>
          <dl className="space-y-2 mb-6">
            <div>
              <dt className="text-xs uppercase tracking-wide text-gray-500">Tally Company</dt>
              <dd data-testid="connect-confirm-company" className="text-sm font-medium text-gray-900">{companyName}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-gray-500">Friendly Name</dt>
              <dd data-testid="connect-confirm-name" className="text-sm font-medium text-gray-900">{workspace.name}</dd>
            </div>
          </dl>
          <div className="flex gap-3 justify-end">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-md">Close</button>
            <button type="button" data-testid="connect-start-chat" onClick={() => onCreated(workspace)} className="px-4 py-2 text-sm text-white bg-blue-600 hover:bg-blue-700 rounded-md">Start chat</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-lg p-6 w-full mx-4 md:mx-auto md:max-w-md">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Connect Tally Company</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && <div className="bg-red-50 text-red-700 p-3 rounded text-sm">{error}</div>}
          <div>
            <label htmlFor="connect-name" className="block text-sm font-medium text-gray-700">Friendly Name</label>
            <input id="connect-name" type="text" required value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Bharat Traders — Main Books"
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500" />
          </div>
          <div>
            <label htmlFor="connect-host" className="block text-sm font-medium text-gray-700">Tally Host</label>
            <input id="connect-host" type="text" required value={tallyHost} onChange={(e) => setTallyHost(e.target.value)} placeholder="localhost or 192.168.1.5"
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500" />
          </div>
          <div>
            <label htmlFor="connect-port" className="block text-sm font-medium text-gray-700">Tally Port</label>
            <input id="connect-port" type="number" required value={tallyPort} onChange={(e) => setTallyPort(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500" />
          </div>
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <span className="text-sm font-medium text-gray-700">Demo Mode</span>
            <div className="relative">
              <input type="checkbox" className="sr-only peer" checked={mockMode} onChange={(e) => setMockMode(e.target.checked)} />
              <div className="w-9 h-5 bg-gray-200 rounded-full peer peer-checked:bg-blue-500 transition-colors" />
              <div className="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform peer-checked:translate-x-4" />
            </div>
            <span className="text-xs text-gray-500">{mockMode ? "Uses sample data" : "Connects to live Tally"}</span>
          </label>
          <div className="flex gap-3 justify-end">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-md">Cancel</button>
            <button type="submit" disabled={loading} className="px-4 py-2 text-sm text-white bg-blue-600 hover:bg-blue-700 rounded-md disabled:opacity-50">
              {loading ? "Connecting..." : "Connect"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

import { useState } from "react";
import { createWorkspace, testConnection } from "../api/client";
import type { WorkspaceData } from "../types";

interface ConnectCompanyModalProps {
  onClose: () => void;
  onCreated: (workspace: WorkspaceData) => void;
}

type ConnectionState = "idle" | "connecting" | "connected" | "error";

const MOCK_COMPANY = "Bharat Traders Pvt Ltd";

export default function ConnectCompanyModal({ onClose, onCreated }: ConnectCompanyModalProps) {
  const [tallyHost, setTallyHost] = useState("localhost");
  const [tallyPort, setTallyPort] = useState("9000");
  const [mockMode, setMockMode] = useState(false);
  const [connectionState, setConnectionState] = useState<ConnectionState>("idle");
  const [companies, setCompanies] = useState<string[]>([]);
  const [selectedCompany, setSelectedCompany] = useState("");
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [workspace, setWorkspace] = useState<WorkspaceData | null>(null);

  const handleTestConnection = async () => {
    setConnectionState("connecting");
    setError("");
    const portNum = parseInt(tallyPort, 10);
    const safePort = Number.isNaN(portNum) ? 9000 : portNum;
    try {
      const result = await testConnection(tallyHost, safePort);
      if (result.connected && result.companies.length > 0) {
        setCompanies(result.companies);
        setSelectedCompany(result.companies.length === 1 ? result.companies[0] : "");
        setConnectionState("connected");
      } else {
        setError(result.error || "Connected, but no company is loaded in Tally.");
        setConnectionState("error");
      }
    } catch {
      setError("Could not reach Tally. Check host and port.");
      setConnectionState("error");
    }
  };

  const handleMockToggle = (checked: boolean) => {
    setMockMode(checked);
    setError("");
    if (checked) {
      setCompanies([MOCK_COMPANY]);
      setSelectedCompany(MOCK_COMPANY);
      setConnectionState("connected");
    } else {
      setCompanies([]);
      setSelectedCompany("");
      setConnectionState("idle");
    }
  };

  const handleCreate = async () => {
    if (!selectedCompany) return;
    setCreating(true);
    setError("");
    const portNum = parseInt(tallyPort, 10);
    const safePort = Number.isNaN(portNum) ? 9000 : portNum;
    try {
      const ws = await createWorkspace({
        name: selectedCompany,
        config: {
          tally_host: tallyHost,
          tally_port: safePort,
          tally_company: selectedCompany,
          mock_mode: mockMode,
        },
      });
      setWorkspace(ws);
    } catch {
      setError("Failed to create workspace.");
    } finally {
      setCreating(false);
    }
  };

  const canCreate = connectionState === "connected" && selectedCompany !== "";
  const fieldsLocked = connectionState === "connected" && !mockMode;

  // Confirmation screen after workspace is created.
  if (workspace) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg shadow-lg p-6 w-full mx-4 md:mx-auto md:max-w-md">
          <div className="flex items-center gap-2 mb-4">
            <span className="w-6 h-6 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-sm">
              ✓
            </span>
            <h2 className="text-lg font-semibold text-gray-900">Company Connected</h2>
          </div>
          <dl className="space-y-2 mb-6">
            <div>
              <dt className="text-xs uppercase tracking-wide text-gray-500">Tally Company</dt>
              <dd data-testid="connect-confirm-company" className="text-sm font-medium text-gray-900">
                {selectedCompany}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-gray-500">Workspace</dt>
              <dd data-testid="connect-confirm-name" className="text-sm font-medium text-gray-900">
                {workspace.name}
              </dd>
            </div>
          </dl>
          <div className="flex gap-3 justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-md"
            >
              Close
            </button>
            <button
              type="button"
              data-testid="connect-start-chat"
              onClick={() => onCreated(workspace)}
              className="px-4 py-2 text-sm text-white bg-blue-600 hover:bg-blue-700 rounded-md"
            >
              Start chat
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-lg p-6 w-full mx-4 md:mx-auto md:max-w-md">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Connect Tally Company</h2>
        <div className="space-y-4">
          {error && <div className="bg-red-50 text-red-700 p-3 rounded text-sm">{error}</div>}
          <div>
            <label htmlFor="connect-host" className="block text-sm font-medium text-gray-700">
              Tally Host
            </label>
            <input
              id="connect-host"
              type="text"
              value={tallyHost}
              onChange={(e) => setTallyHost(e.target.value)}
              disabled={fieldsLocked}
              placeholder="localhost or 192.168.1.5"
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"
            />
          </div>
          <div>
            <label htmlFor="connect-port" className="block text-sm font-medium text-gray-700">
              Tally Port
            </label>
            <input
              id="connect-port"
              type="number"
              value={tallyPort}
              onChange={(e) => setTallyPort(e.target.value)}
              disabled={fieldsLocked}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"
            />
          </div>

          <label className="flex items-center gap-2 cursor-pointer select-none">
            <span className="text-sm font-medium text-gray-700">Demo Mode</span>
            <div className="relative">
              <input
                type="checkbox"
                className="sr-only peer"
                checked={mockMode}
                onChange={(e) => handleMockToggle(e.target.checked)}
              />
              <div className="w-9 h-5 bg-gray-200 rounded-full peer peer-checked:bg-blue-500 transition-colors" />
              <div className="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform peer-checked:translate-x-4" />
            </div>
            <span className="text-xs text-gray-500">
              {mockMode ? "Uses sample data" : "Connects to live Tally"}
            </span>
          </label>

          {!mockMode && connectionState !== "connected" && (
            <button
              type="button"
              onClick={handleTestConnection}
              disabled={connectionState === "connecting"}
              className="w-full px-4 py-2 text-sm text-white bg-blue-600 hover:bg-blue-700 rounded-md disabled:opacity-50"
            >
              {connectionState === "connecting" ? "Connecting..." : "Test Connection"}
            </button>
          )}

          {connectionState === "connected" && companies.length > 0 && (
            <div>
              <label htmlFor="connect-company" className="block text-sm font-medium text-gray-700">
                Company
              </label>
              {companies.length === 1 ? (
                <div
                  id="connect-company"
                  className="mt-1 px-3 py-2 bg-green-50 border border-green-200 rounded-md text-sm text-green-800"
                >
                  {companies[0]}
                </div>
              ) : (
                <select
                  id="connect-company"
                  aria-label="Company"
                  value={selectedCompany}
                  onChange={(e) => setSelectedCompany(e.target.value)}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="">Select a company...</option>
                  {companies.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              )}
            </div>
          )}

          <div className="flex gap-3 justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-md"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleCreate}
              disabled={!canCreate || creating}
              className="px-4 py-2 text-sm text-white bg-green-600 hover:bg-green-700 rounded-md disabled:opacity-50"
            >
              {creating ? "Creating..." : "Create Workspace"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

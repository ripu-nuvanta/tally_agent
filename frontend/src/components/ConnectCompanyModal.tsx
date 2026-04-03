import { useState } from "react";
import { createWorkspace } from "../api/client";

interface ConnectCompanyModalProps {
  onClose: () => void;
  onCreated: () => void;
}

export default function ConnectCompanyModal({ onClose, onCreated }: ConnectCompanyModalProps) {
  const [name, setName] = useState("");
  const [tallyHost, setTallyHost] = useState("localhost");
  const [tallyPort, setTallyPort] = useState("9000");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await createWorkspace({ name, config: { tally_host: tallyHost, tally_port: parseInt(tallyPort, 10) } });
      onCreated();
    } catch {
      setError("Failed to connect company. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Connect Tally Company</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && <div className="bg-red-50 text-red-700 p-3 rounded text-sm">{error}</div>}
          <div>
            <label className="block text-sm font-medium text-gray-700">Company Name</label>
            <input type="text" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Bharat Traders Pvt Ltd"
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Tally Host</label>
            <input type="text" required value={tallyHost} onChange={(e) => setTallyHost(e.target.value)} placeholder="localhost or 192.168.1.5"
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Tally Port</label>
            <input type="number" required value={tallyPort} onChange={(e) => setTallyPort(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500" />
          </div>
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

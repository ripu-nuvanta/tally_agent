import { useEffect, useState } from "react";
import { ChevronDown } from "lucide-react";
import { getCompanies } from "../api/client";
import { useSession } from "../context/SessionContext";
import type { Company } from "../types";

export default function CompanySelector() {
  const { company, setCompany } = useSession();
  const [companies, setCompanies] = useState<Company[]>([]);

  useEffect(() => {
    getCompanies()
      .then((res) => {
        setCompanies(res.companies);
        if (res.companies.length > 0 && !company) {
          setCompany(res.companies[0].name);
        }
      })
      .catch(() => setCompanies([]));
  }, []);

  if (companies.length === 0) return null;

  return (
    <div className="relative">
      <select
        value={company ?? ""}
        onChange={(e) => setCompany(e.target.value)}
        className="appearance-none bg-white border border-gray-200 rounded-lg px-3 py-1.5 pr-8 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {companies.map((c) => (
          <option key={c.name} value={c.name}>
            {c.name}
          </option>
        ))}
      </select>
      <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
    </div>
  );
}

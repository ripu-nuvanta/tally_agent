import { useState } from "react";
import { ArrowUpDown, Download } from "lucide-react";
import type { TableData } from "../types";
import { formatIndianNumber, isNumericValue } from "../utils/format";

interface DataTableProps {
  data: TableData;
}

export default function DataTable({ data }: DataTableProps) {
  const { headers, rows } = data;
  const [sortCol, setSortCol] = useState<number | null>(null);
  const [sortAsc, setSortAsc] = useState(true);

  if (rows.length === 0) return null;

  function handleSort(colIndex: number) {
    if (sortCol === colIndex) {
      setSortAsc(!sortAsc);
    } else {
      setSortCol(colIndex);
      setSortAsc(true);
    }
  }

  const sortedRows = [...rows];
  if (sortCol !== null) {
    sortedRows.sort((a, b) => {
      const aVal = a[sortCol];
      const bVal = b[sortCol];
      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return 1;
      if (bVal == null) return -1;
      if (typeof aVal === "number" && typeof bVal === "number") {
        return sortAsc ? aVal - bVal : bVal - aVal;
      }
      const aStr = String(aVal);
      const bStr = String(bVal);
      return sortAsc ? aStr.localeCompare(bStr) : bStr.localeCompare(aStr);
    });
  }

  function exportCSV() {
    const csvRows = [
      headers.join(","),
      ...sortedRows.map((row) =>
        row.map((cell) => {
          const val = cell == null ? "" : String(cell);
          return val.includes(",") ? `"${val}"` : val;
        }).join(",")
      ),
    ];
    const blob = new Blob([csvRows.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "tally-data.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  function formatCell(val: string | number | null): string {
    if (val == null) return "";
    if (isNumericValue(val)) return formatIndianNumber(val);
    return String(val);
  }

  return (
    <div className="mt-3 border border-gray-200 rounded-lg overflow-hidden">
      <div className="flex justify-end px-3 py-1.5 bg-gray-50 border-b border-gray-200">
        <button
          onClick={exportCSV}
          className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700"
        >
          <Download className="w-3 h-3" /> CSV
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              {headers.map((header, i) => (
                <th
                  key={i}
                  onClick={() => handleSort(i)}
                  className="px-3 py-2 text-left font-medium text-gray-600 cursor-pointer hover:bg-gray-100 select-none whitespace-nowrap"
                >
                  <span className="flex items-center gap-1">
                    {header}
                    <ArrowUpDown className="w-3 h-3 text-gray-400" />
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row, ri) => (
              <tr key={ri} className="border-b border-gray-100 hover:bg-gray-50">
                {row.map((cell, ci) => (
                  <td
                    key={ci}
                    className={`px-3 py-1.5 whitespace-nowrap ${
                      isNumericValue(cell) ? "text-right tabular-nums" : ""
                    }`}
                  >
                    {formatCell(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

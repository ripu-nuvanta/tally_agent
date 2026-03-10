import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  ComposedChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { ChartSpec } from "../types";
import { formatAxisAmount, formatINR } from "../utils/format";

const DEFAULT_COLORS = [
  "#4F46E5", "#10B981", "#F59E0B", "#EF4444",
  "#8B5CF6", "#EC4899", "#06B6D4",
];

interface ChartRendererProps {
  chart: ChartSpec;
}

export default function ChartRenderer({ chart }: ChartRendererProps) {
  const { chart_type, title, data, config } = chart;
  const colors = (config?.colors as string[]) || DEFAULT_COLORS;

  if (!data || data.length === 0) return null;

  const allKeys = Object.keys(data[0]);
  const labelKey = (config?.x_key as string) || allKeys[0];
  const valueKeys = (config?.y_keys as string[]) || allKeys.filter(k => k !== labelKey);

  const useCurrencyFormat = config?.currency_format !== false;
  const tickFormatter = useCurrencyFormat ? formatAxisAmount : undefined;
  const showLegend = config?.show_legend !== false;

  const tooltipFormatter = (value: number) => {
    return useCurrencyFormat ? formatINR(value) : value;
  };

  return (
    <div className="mt-3 border border-gray-200 rounded-lg p-4 bg-white" data-testid="chart-container" data-chart-spec={JSON.stringify(chart)}>
      <h3 className="text-sm font-medium text-gray-700 mb-3">{title}</h3>
      <ResponsiveContainer width="100%" height={300}>
        {chart_type === "pie" ? (
          <PieChart>
            <Pie
              data={data}
              dataKey={valueKeys[0]}
              nameKey={labelKey}
              cx="50%"
              cy="50%"
              outerRadius={100}
              label={({ name, percent }: { name?: string; percent?: number }) =>
                `${name ?? ""}: ${((percent ?? 0) * 100).toFixed(0)}%`
              }
            >
              {data.map((_, i) => (
                <Cell key={i} fill={colors[i % colors.length]} />
              ))}
            </Pie>
            <Tooltip />
            {showLegend && <Legend />}
          </PieChart>
        ) : chart_type === "composed" ? (
          (() => {
            const secondaryKeys = (config?.secondary_y_keys as string[]) || [];
            const secondaryColors = (config?.secondary_colors as string[]) || ["#9CA3AF"];
            return (
              <ComposedChart data={data}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey={labelKey} tick={{ fontSize: 12 }} />
                <YAxis yAxisId="left" orientation="left" tickFormatter={tickFormatter} tick={{ fontSize: 12 }} />
                {secondaryKeys.length > 0 && (
                  <YAxis yAxisId="right" orientation="right" tickFormatter={(v: number) => `${v}%`} tick={{ fontSize: 12 }} />
                )}
                <Tooltip formatter={(value: number, name: string) => {
                  if (secondaryKeys.includes(name)) return [`${value}%`, name];
                  return [formatINR(value), name];
                }} />
                {showLegend && <Legend />}
                {valueKeys.map((key, i) => (
                  <Bar key={key} yAxisId="left" dataKey={key} fill={colors[i % colors.length]} />
                ))}
                {secondaryKeys.map((key, i) => (
                  <Line
                    key={key}
                    yAxisId="right"
                    type="monotone"
                    dataKey={key}
                    stroke={secondaryColors[i % secondaryColors.length]}
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    dot={false}
                  />
                ))}
              </ComposedChart>
            );
          })()
        ) : chart_type === "line" ? (
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={labelKey} tick={{ fontSize: 12 }} />
            <YAxis tickFormatter={tickFormatter} tick={{ fontSize: 12 }} />
            <Tooltip formatter={tooltipFormatter} />
            {showLegend && <Legend />}
            {valueKeys.map((key, i) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={colors[i % colors.length]}
                strokeWidth={2}
              />
            ))}
          </LineChart>
        ) : (
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={labelKey} tick={{ fontSize: 12 }} />
            <YAxis tickFormatter={tickFormatter} tick={{ fontSize: 12 }} />
            <Tooltip formatter={tooltipFormatter} />
            {showLegend && <Legend />}
            {valueKeys.map((key, i) => (
              <Bar key={key} dataKey={key} fill={colors[i % colors.length]} />
            ))}
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

"use client";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart } from "recharts";

interface ChartLineProps {
  data: { name: string; value: number; value2?: number }[];
  height?: number;
  showArea?: boolean;
  color?: string;
  color2?: string;
}

const CustomTooltip = ({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number; color: string; dataKey: string }>; label?: string }) => {
  if (!active || !payload) return null;
  return (
    <div className="glass p-3 !rounded-lg text-xs">
      <p className="text-[var(--foreground-muted)] mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }} className="font-semibold">{p.dataKey}: {p.value}</p>
      ))}
    </div>
  );
};

export function ChartLine({ data, height = 300, showArea, color = "#3b82f6", color2 }: ChartLineProps) {
  const Chart = showArea ? AreaChart : LineChart;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <Chart data={data}>
        <defs>
          <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
          {color2 && (
            <linearGradient id="lineGrad2" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color2} stopOpacity={0.3} />
              <stop offset="100%" stopColor={color2} stopOpacity={0} />
            </linearGradient>
          )}
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.1)" />
        <XAxis dataKey="name" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
        <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
        <Tooltip content={<CustomTooltip />} />
        {showArea ? (
          <>
            <Area type="monotone" dataKey="value" stroke={color} fill="url(#lineGrad)" strokeWidth={2} />
            {color2 && <Area type="monotone" dataKey="value2" stroke={color2} fill="url(#lineGrad2)" strokeWidth={2} />}
          </>
        ) : (
          <>
            <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2} dot={false} />
            {color2 && <Line type="monotone" dataKey="value2" stroke={color2} strokeWidth={2} dot={false} />}
          </>
        )}
      </Chart>
    </ResponsiveContainer>
  );
}

"use client";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

interface ChartBarProps {
  data: { name: string; value: number; value2?: number }[];
  height?: number;
  color?: string;
  color2?: string;
}

const CustomTooltip = ({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number; color: string }>; label?: string }) => {
  if (!active || !payload) return null;
  return (
    <div className="glass p-3 !rounded-lg text-xs">
      <p className="text-[var(--foreground-muted)] mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }} className="font-semibold">{p.value}</p>
      ))}
    </div>
  );
};

export function ChartBar({ data, height = 300, color = "#3b82f6", color2 }: ChartBarProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.1)" />
        <XAxis dataKey="name" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
        <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
        <Tooltip content={<CustomTooltip />} />
        <Bar dataKey="value" fill={color} radius={[6, 6, 0, 0]} />
        {color2 && <Bar dataKey="value2" fill={color2} radius={[6, 6, 0, 0]} />}
      </BarChart>
    </ResponsiveContainer>
  );
}

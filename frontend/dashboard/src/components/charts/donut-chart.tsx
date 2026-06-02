"use client";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";

interface ChartDonutProps {
  data: { name: string; value: number; color: string }[];
  height?: number;
}

const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ payload: { name: string; value: number; color: string } }> }) => {
  if (!active || !payload?.[0]) return null;
  const d = payload[0].payload;
  return (
    <div className="glass p-3 !rounded-lg text-xs">
      <p className="font-semibold" style={{ color: d.color }}>{d.name}: {d.value}</p>
    </div>
  );
};

export function ChartDonut({ data, height = 250 }: ChartDonutProps) {
  const total = data.reduce((s, d) => s + d.value, 0);
  return (
    <div className="relative" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} cx="50%" cy="50%" innerRadius="60%" outerRadius="80%" paddingAngle={4} dataKey="value" strokeWidth={0}>
            {data.map((d, i) => <Cell key={i} fill={d.color} />)}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="text-center">
          <p className="text-2xl font-bold">{total}</p>
          <p className="text-xs text-[var(--foreground-muted)]">Total</p>
        </div>
      </div>
    </div>
  );
}

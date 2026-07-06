import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  icon: LucideIcon;
  label: string;
  value: string;
}

/** One metric tile in the analytics KPI row — value is the whole point,
 * so it's the largest, boldest thing in the card; the icon+label above it
 * just names what's being measured. */
export function StatCard({ icon: Icon, label, value }: StatCardProps) {
  return (
    <div className="rounded-xl border border-border bg-bg-surface p-4">
      <div className="flex items-center gap-1.5 text-text-muted">
        <Icon size={14} className="shrink-0" />
        <span className="text-xs font-medium">{label}</span>
      </div>
      <p className="mt-2 font-heading text-2xl font-bold text-text">{value}</p>
    </div>
  );
}

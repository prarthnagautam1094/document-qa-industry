import { BarChart3, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";

export default function AnalyticsPage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader title="Analytics" subtitle="Usage and performance insights" />

      <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
        <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-accent/20 to-accent-cyan/20 text-accent-cyan">
          <BarChart3 size={26} />
          <div className="absolute -right-1.5 -top-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-accent to-accent-cyan text-[#0B0E14]">
            <Sparkles size={12} />
          </div>
        </div>
        <div className="max-w-sm">
          <h2 className="font-heading text-lg font-bold text-text">Coming soon</h2>
          <p className="mt-2 text-sm text-text-muted">
            Query volume, response latency, and answer/fallback rates will land here once the
            backend exposes an analytics endpoint. The chat and document experience is fully
            wired up in the meantime.
          </p>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import {
  BarChart3,
  CheckCircle2,
  Clock,
  FileText,
  Loader2,
  MessageSquare,
  Sparkles,
  XCircle,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { PageHeader } from "@/components/PageHeader";
import { StatCard } from "@/components/StatCard";
import { ApiError, fetchAnalytics } from "@/lib/api";
import type { AnalyticsResponse, DocumentQueryCount, QueryCountByDate } from "@/lib/types";
import { cn, formatTimestamp } from "@/lib/utils";

function formatShortDate(iso: string): string {
  const date = new Date(`${iso}T00:00:00`);
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function formatFullDate(iso: string): string {
  const date = new Date(`${iso}T00:00:00`);
  return date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

function formatResponseTime(seconds: number): string {
  if (seconds <= 0) return "0s";
  return seconds < 1 ? `${Math.round(seconds * 1000)}ms` : `${seconds.toFixed(1)}s`;
}

function truncateFilename(name: string, max = 22): string {
  return name.length > max ? `${name.slice(0, max - 1)}…` : name;
}

interface QueriesTooltipProps {
  active?: boolean;
  label?: string;
  payload?: Array<{ value?: number | string }>;
}

/** Minimal chart tooltip: value leads (bold, high-contrast), the series
 * name/date follows as secondary text — a short line-key (not a filled
 * box) keys it to the series color, matching the app's existing citation
 * badges rather than recharts' default tooltip chrome. */
function QueriesTooltip({ active, label, payload }: QueriesTooltipProps) {
  if (!active || !payload || payload.length === 0 || !label) return null;
  return (
    <div className="shadow-elevated rounded-lg border border-border bg-bg-surface px-3 py-2">
      <p className="text-xs text-text-muted">{formatFullDate(label)}</p>
      <p className="mt-0.5 flex items-center gap-1.5 text-sm font-semibold text-text">
        <span className="inline-block h-0.5 w-3 shrink-0 rounded-full bg-accent" />
        {payload[0].value} {payload[0].value === 1 ? "query" : "queries"}
      </p>
    </div>
  );
}

interface DocumentTooltipProps {
  active?: boolean;
  payload?: Array<{ payload: DocumentQueryCount }>;
}

function DocumentTooltip({ active, payload }: DocumentTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0].payload;
  return (
    <div className="shadow-elevated max-w-[220px] rounded-lg border border-border bg-bg-surface px-3 py-2">
      <p className="truncate text-xs text-text-muted" title={point.filename}>
        {point.filename}
      </p>
      <p className="mt-0.5 flex items-center gap-1.5 text-sm font-semibold text-text">
        <span className="inline-block h-0.5 w-3 shrink-0 rounded-full bg-accent" />
        {point.count} {point.count === 1 ? "citation" : "citations"}
      </p>
    </div>
  );
}

function ChartCard({
  title,
  subtitle,
  isEmpty,
  emptyMessage,
  children,
}: {
  title: string;
  subtitle: string;
  isEmpty: boolean;
  emptyMessage: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-bg-surface p-4 sm:p-5">
      <h2 className="font-heading text-sm font-bold text-text">{title}</h2>
      <p className="text-xs text-text-muted">{subtitle}</p>
      <div className="mt-3">
        {isEmpty ? (
          <div className="flex h-[220px] items-center justify-center text-center text-xs text-text-muted">
            {emptyMessage}
          </div>
        ) : (
          children
        )}
      </div>
    </div>
  );
}

function QueriesOverTimeChart({ data }: { data: QueryCountByDate[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
        <CartesianGrid stroke="var(--color-border)" strokeDasharray="0" vertical={false} />
        <XAxis
          dataKey="date"
          tickFormatter={formatShortDate}
          tick={{ fill: "var(--color-text-muted)", fontSize: 11 }}
          axisLine={{ stroke: "var(--color-border)" }}
          tickLine={false}
          minTickGap={32}
        />
        <YAxis
          allowDecimals={false}
          tick={{ fill: "var(--color-text-muted)", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={32}
        />
        <Tooltip content={<QueriesTooltip />} cursor={{ stroke: "var(--color-border)" }} />
        <Line
          type="monotone"
          dataKey="count"
          stroke="var(--color-accent)"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: "var(--color-accent)", stroke: "var(--color-bg-surface)", strokeWidth: 2 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

function MostQueriedDocumentsChart({ data }: { data: DocumentQueryCount[] }) {
  return (
    <ResponsiveContainer width="100%" height={Math.max(220, data.length * 40)}>
      <BarChart data={data} layout="vertical" margin={{ top: 8, right: 20, left: 8, bottom: 0 }}>
        <CartesianGrid stroke="var(--color-border)" strokeDasharray="0" horizontal={false} />
        <XAxis
          type="number"
          allowDecimals={false}
          tick={{ fill: "var(--color-text-muted)", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="filename"
          tickFormatter={(name: string) => truncateFilename(name)}
          tick={{ fill: "var(--color-text-muted)", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={130}
        />
        <Tooltip content={<DocumentTooltip />} cursor={{ fill: "var(--color-tint)" }} />
        <Bar dataKey="count" fill="var(--color-accent)" radius={[0, 4, 4, 0]} maxBarSize={20} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function RecentConversationsTable({ analytics }: { analytics: AnalyticsResponse }) {
  return (
    <div className="rounded-xl border border-border bg-bg-surface p-4 sm:p-5">
      <h2 className="font-heading text-sm font-bold text-text">Recent conversations</h2>
      <p className="text-xs text-text-muted">
        The last {analytics.recent_conversations.length}{" "}
        {analytics.recent_conversations.length === 1 ? "question" : "questions"} asked.
      </p>

      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[420px] text-left text-sm">
          <thead>
            <tr className="border-b border-border text-xs text-text-muted">
              <th className="pb-2 pr-3 font-medium">Question</th>
              <th className="pb-2 pr-3 font-medium">Asked</th>
              <th className="pb-2 font-medium">Answered</th>
            </tr>
          </thead>
          <tbody>
            {analytics.recent_conversations.map((row, i) => (
              <tr key={i} className="border-b border-border/60 last:border-0">
                <td className="max-w-[280px] truncate py-2 pr-3 text-text" title={row.question}>
                  {row.question}
                </td>
                <td className="whitespace-nowrap py-2 pr-3 text-text-muted">
                  {formatTimestamp(row.timestamp)}
                </td>
                <td className="py-2">
                  {row.was_answered ? (
                    <CheckCircle2 size={16} className="text-emerald-400" aria-label="Answered" />
                  ) : (
                    <XCircle size={16} className="text-red-400" aria-label="Not answered" />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AnalyticsEmptyState() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
      <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-accent/20 to-accent-cyan/20 text-accent-cyan">
        <BarChart3 size={26} />
        <div className="absolute -right-1.5 -top-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-accent to-accent-cyan text-[#0B0E14]">
          <Sparkles size={12} />
        </div>
      </div>
      <div className="max-w-sm">
        <h2 className="font-heading text-lg font-bold text-text">No queries yet</h2>
        <p className="mt-2 text-sm text-text-muted">
          Ask a question in the Chat tab to start seeing usage and performance analytics here.
        </p>
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // A bare `cancelled` boolean only guards the *state updates* below —
    // it doesn't stop the underlying request from actually being made.
    // In development, React's Strict Mode intentionally double-invokes
    // this effect (mount → cleanup → mount) to surface exactly this kind
    // of bug: without an AbortController, the first invocation's
    // fetchAnalytics() (and its supabase.auth.getSession() call) is left
    // running concurrently with the second's, and the two calls can race
    // — observed here as the surviving request occasionally resolving
    // with a stale/missing session, so no Authorization header ever gets
    // attached (surfacing as the backend's "Missing bearer token" 401).
    // Aborting the stale request in the cleanup — not just ignoring its
    // result — removes the race instead of papering over it.
    const controller = new AbortController();
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchAnalytics(controller.signal);
        if (!cancelled) setAnalytics(data);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Failed to load analytics.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, []);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader title="Analytics" subtitle="Usage and performance insights" />

      <div className={cn("min-h-0 flex-1", !loading && !error && analytics && analytics.total_queries > 0 && "overflow-y-auto")}>
        {loading ? (
          <div className="flex h-full items-center justify-center">
            <Loader2 size={22} className="animate-spin text-accent" />
          </div>
        ) : error ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
            <p className="text-sm text-text-muted">{error}</p>
          </div>
        ) : !analytics || analytics.total_queries === 0 ? (
          <AnalyticsEmptyState />
        ) : (
          <div className="mx-auto flex max-w-5xl flex-col gap-4 px-4 py-6 sm:px-6">
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <StatCard icon={FileText} label="Total documents" value={analytics.total_documents.toLocaleString()} />
              <StatCard icon={MessageSquare} label="Total queries" value={analytics.total_queries.toLocaleString()} />
              <StatCard icon={CheckCircle2} label="Success rate" value={`${analytics.success_rate}%`} />
              <StatCard icon={Clock} label="Avg response time" value={formatResponseTime(analytics.avg_response_time)} />
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <ChartCard
                title="Queries over time"
                subtitle="Last 30 days"
                isEmpty={false}
                emptyMessage=""
              >
                <QueriesOverTimeChart data={analytics.queries_over_time} />
              </ChartCard>

              <ChartCard
                title="Most-queried documents"
                subtitle="By citation frequency"
                isEmpty={analytics.most_queried_documents.length === 0}
                emptyMessage="No documents have been cited in an answer yet."
              >
                <MostQueriedDocumentsChart data={analytics.most_queried_documents} />
              </ChartCard>
            </div>

            <RecentConversationsTable analytics={analytics} />
          </div>
        )}
      </div>
    </div>
  );
}

import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  right?: ReactNode;
}

export function PageHeader({ title, subtitle, right }: PageHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-border px-4 py-3.5 sm:px-6">
      <div className="min-w-0 pl-10 md:pl-0">
        <h1 className="font-heading text-base font-bold text-text">{title}</h1>
        {subtitle && <p className="text-xs text-text-muted">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

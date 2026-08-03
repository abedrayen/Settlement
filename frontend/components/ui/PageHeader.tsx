import { ReactNode } from "react";

export function PageHeader({
  title,
  description,
  actions,
  badge,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  badge?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 pb-1">
      <div>
        <div className="flex items-center gap-2.5 flex-wrap">
          <h1 className="text-xl font-semibold tracking-tight text-slate-900">{title}</h1>
          {badge}
        </div>
        {description && <p className="text-slate-500 text-sm mt-1 max-w-2xl leading-relaxed">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 flex-wrap">{actions}</div>}
    </div>
  );
}

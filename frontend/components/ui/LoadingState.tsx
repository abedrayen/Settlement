import { ReactNode } from "react";

export function LoadingState({ message = "Loading..." }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-4">
      <div className="flex gap-1">
        <span className="w-2 h-2 rounded-full bg-blue-500 typing-dot" />
        <span className="w-2 h-2 rounded-full bg-blue-500 typing-dot" />
        <span className="w-2 h-2 rounded-full bg-blue-500 typing-dot" />
      </div>
      <p className="text-sm text-slate-500">{message}</p>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="card p-12 text-center">
      <div className="text-4xl mb-3 opacity-40">📭</div>
      <h3 className="font-semibold text-slate-900">{title}</h3>
      {description && <p className="text-sm text-slate-500 mt-1 max-w-sm mx-auto">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

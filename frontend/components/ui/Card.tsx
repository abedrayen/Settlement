import clsx from "clsx";
import { ReactNode } from "react";

export function Card({
  children,
  className,
  hover,
  padding = true,
}: {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  padding?: boolean;
}) {
  return (
    <div className={clsx(hover ? "card-hover" : "card", padding && "p-5", className)}>
      {children}
    </div>
  );
}

export function ChartCard({
  title,
  subtitle,
  action,
  children,
  className,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card className={className}>
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="section-title">{title}</h3>
          {subtitle && <p className="section-sub">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </Card>
  );
}

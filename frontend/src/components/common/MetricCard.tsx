import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

type Tone = "default" | "success" | "danger" | "warning" | "info";
const toneStyles: Record<Tone, string> = {
  default: "text-foreground",
  success: "text-emerald-500",
  danger: "text-rose-500",
  warning: "text-amber-500",
  info: "text-sky-500",
};

export function MetricCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "default",
  loading,
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon?: LucideIcon;
  tone?: Tone;
  loading?: boolean;
}) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="text-xs uppercase tracking-wider text-muted-foreground">{label}</div>
          {Icon && <Icon className={cn("h-4 w-4", toneStyles[tone])} />}
        </div>
        {loading ? (
          <Skeleton className="mt-3 h-7 w-24" />
        ) : (
          <div className={cn("mt-3 text-2xl font-semibold", toneStyles[tone])}>{value}</div>
        )}
        {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
      </CardContent>
    </Card>
  );
}

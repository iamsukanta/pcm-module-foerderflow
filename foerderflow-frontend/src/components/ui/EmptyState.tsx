import Link from "next/link";
import { type LucideIcon } from "lucide-react";
import { Button } from "./Button";

type EmptyStateProps = {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: {
    label: string;
    onClick?: () => void; // für Client Components
    href?: string; // für Server Components
  };
};

export function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <div className="rounded-full bg-soft-line2 p-4 mb-4">
        <Icon className="h-8 w-8 text-soft-ink3" aria-hidden="true" />
      </div>
      <h3 className="text-lg font-semibold text-soft-ink mb-1">{title}</h3>
      <p className="text-sm text-soft-ink2 max-w-sm mb-6">{description}</p>
      {action &&
        (action.href ? (
          <Link href={action.href}>
            <Button variant="primary">{action.label}</Button>
          </Link>
        ) : (
          <Button variant="primary" onClick={action.onClick}>
            {action.label}
          </Button>
        ))}
    </div>
  );
}

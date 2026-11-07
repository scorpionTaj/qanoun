import {
  Flag,
  Briefcase,
  Building2,
  Car,
  Gavel,
  GraduationCap,
  HandCoins,
  Home,
  Landmark,
  Map,
  Scale,
  ShieldHalf,
  Users,
  type LucideIcon,
} from "lucide-react";

/** One recognisable icon per legal domain (keys mirror qanoun_pipeline.catalog.DOMAINS). */
const ICONS: Record<string, LucideIcon> = {
  family: Users,
  labour: Briefcase,
  civil: Scale,
  housing: Home,
  commercial: Building2,
  education: GraduationCap,
  penal: ShieldHalf,
  nationality: Flag,
  social: HandCoins,
  justice: Gavel,
  transport: Car,
  property: Map,
  governance: Landmark,
};

export function DomainIcon({ domain, className }: { domain: string; className?: string }) {
  const Icon = ICONS[domain] ?? Scale;
  return <Icon className={className} aria-hidden />;
}

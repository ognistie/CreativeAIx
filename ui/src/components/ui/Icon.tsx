import {
  Activity,
  ArrowUp,
  BookOpen,
  Brain,
  ChartBar,
  Check,
  CircleUser,
  ClockFading,
  Code,
  Command,
  Eye,
  FileText,
  FlaskConical,
  Folder,
  FolderOpen,
  Globe,
  Hand,
  Info,
  type LucideIcon,
  MessagesSquare,
  Mic,
  Minus,
  NotebookPen,
  PanelLeft,
  Paperclip,
  Plus,
  Search,
  Settings,
  ShieldAlert,
  SlidersHorizontal,
  Sparkles,
  Square,
  SquarePen,
  Terminal,
  X,
  Zap,
} from "lucide-react";
import { ICONS } from "../../lib/icons.gen";
import { EXTRA_ICONS } from "../../lib/icons.extra";

const ALL = { ...ICONS, ...EXTRA_ICONS };
export type IconName = keyof typeof ALL;

// Os icones mais vistos (barra lateral, caixa de pedido, conversa) usam o Lucide: traco uniforme, geometria
// refinada e o mesmo desenho que apps como Linear e Cursor usam. Os demais continuam nos desenhos do app.
const LUCIDE: Partial<Record<IconName, LucideIcon>> = {
  "nav-new": SquarePen,
  "nav-search": Search,
  "nav-history": ClockFading,
  "nav-activity": Activity,
  "nav-brain": Brain,
  "nav-user": CircleUser,
  "nav-journal": NotebookPen,
  "nav-library": BookOpen,
  "nav-lab": FlaskConical,
  "nav-harness": SlidersHorizontal,
  "nav-settings": Settings,
  "nav-info": Info,
  pen: SquarePen,
  search: Search,
  sidebar: PanelLeft,
  "arrow-up": ArrowUp,
  mic: Mic,
  plus: Plus,
  paperclip: Paperclip,
  eye: Eye,
  "file-text": FileText,
  messages: MessagesSquare,
  x: X,
  folder: Folder,
  "folder-open": FolderOpen,
  terminal: Terminal,
  bolt: Zap,
  hand: Hand,
  shield: ShieldAlert,
  command: Command,
  check: Check,
  chart: ChartBar,
  globe: Globe,
  code: Code,
  sparkle: Sparkles,
};

/** Icone de linha do app: viewBox 24, traco fino. Sem label, decorativo. */
export function Icon({
  name,
  size = 16,
  weight = 1.7,
  className,
  label,
}: {
  name: IconName;
  size?: number;
  weight?: number;
  className?: string;
  /** Texto para leitor de tela. Sem label, o icone e decorativo. */
  label?: string;
}) {
  // Compensacao: o traco fica visualmente igual em tamanhos diferentes
  const stroke = ((weight * 24) / Math.max(12, size)) * (size >= 20 ? 0.9 : 1);
  const a11y = { role: label ? "img" : undefined, "aria-label": label, "aria-hidden": label ? undefined : true } as const;
  const Lucide = LUCIDE[name];
  if (Lucide) return <Lucide size={size} strokeWidth={Math.min(2.2, stroke)} absoluteStrokeWidth={false} className={className} {...a11y} />;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" className={className} {...a11y}>
      <path d={ALL[name]} />
    </svg>
  );
}

/** Controles da janela (barra de titulo propria): os mesmos desenhos do Lucide. */
export const WindowGlyph = { minimize: Minus, maximize: Square, close: X } as const;

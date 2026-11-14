import * as Dialog from "@radix-ui/react-dialog";
import * as Menu from "@radix-ui/react-dropdown-menu";
import * as Tip from "@radix-ui/react-tooltip";
import { cn } from "../../lib/cn";
import { Icon, type IconName } from "./Icon";

/** GlassPanel.qml: vidro sobre o ambiente, borda de luz no escuro e sombra macia no claro. */
export function GlassPanel({
  className,
  raised = true,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { raised?: boolean }) {
  return (
    <div
      className={cn(
        "relative rounded-r4 border border-edge bg-glass backdrop-blur-xl",
        raised && "shadow-[0_1px_2px_var(--shadow-soft),0_8px_24px_var(--shadow-soft)]",
        className,
      )}
      {...props}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-[inherit]"
        style={{ background: "linear-gradient(to bottom, var(--sheen), transparent 35%)" }}
      />
      <div className="relative">{children}</div>
    </div>
  );
}

/** AppDialog.qml: modal com titulo, texto e acoes. Foco preso, Esc fecha. */
export function AppDialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  actions,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]" />
        <Dialog.Content
          className={cn(
            "animate-enter fixed left-1/2 top-1/2 z-50 w-[min(440px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2",
            "rounded-r4 border border-edge bg-glass-hi p-6 shadow-[0_24px_60px_var(--shadow)] backdrop-blur-2xl",
          )}
        >
          <Dialog.Title className="font-display text-lg font-medium tracking-[-0.01em] text-fg">{title}</Dialog.Title>
          {description ? (
            <Dialog.Description className="mt-1.5 text-[13px] text-fg-muted">{description}</Dialog.Description>
          ) : (
            <Dialog.Description className="sr-only">{title}</Dialog.Description>
          )}
          {children && <div className="mt-4">{children}</div>}
          {actions && <div className="mt-6 flex justify-end gap-2">{actions}</div>}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export const DialogClose = Dialog.Close;

/** AppMenu.qml + AppMenuItem.qml: menu suspenso com itens e icones. */
export function AppMenu({
  trigger,
  items,
}: {
  trigger: React.ReactNode;
  items: ReadonlyArray<{ label: string; icon?: IconName; danger?: boolean; onSelect: () => void } | "separator">;
}) {
  return (
    <Menu.Root>
      <Menu.Trigger asChild>{trigger}</Menu.Trigger>
      <Menu.Portal>
        <Menu.Content
          sideOffset={6}
          align="end"
          className="animate-enter z-50 min-w-44 rounded-r3 border border-edge bg-glass-hi p-1 shadow-[0_12px_32px_var(--shadow)] backdrop-blur-2xl"
        >
          {items.map((item, i) =>
            item === "separator" ? (
              <Menu.Separator key={i} className="mx-2 my-1 h-px bg-hairline" />
            ) : (
              <Menu.Item
                key={item.label}
                onSelect={item.onSelect}
                className={cn(
                  "flex h-8 cursor-default items-center gap-2 rounded-r2 px-2.5 text-[13px] outline-none",
                  "data-[highlighted]:bg-row-hover",
                  item.danger ? "text-bad" : "text-fg",
                )}
              >
                {item.icon && <Icon name={item.icon} size={14} />}
                {item.label}
              </Menu.Item>
            ),
          )}
        </Menu.Content>
      </Menu.Portal>
    </Menu.Root>
  );
}

/** ToolTipHint.qml: dica curta ao passar o mouse ou focar. */
export function Hint({ text, children }: { text: string; children: React.ReactElement }) {
  return (
    <Tip.Root delayDuration={400}>
      <Tip.Trigger asChild>{children}</Tip.Trigger>
      <Tip.Portal>
        <Tip.Content
          sideOffset={6}
          className="z-50 rounded-r2 bg-primary px-2 py-1 text-xs text-fg-inverse shadow-[0_6px_18px_var(--shadow)]"
        >
          {text}
        </Tip.Content>
      </Tip.Portal>
    </Tip.Root>
  );
}

export const HintProvider = Tip.Provider;

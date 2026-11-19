import { useCallback, useEffect, useRef, useState } from "react";
import { Button, Icon, Segmented } from "../components/ui";
import { GenerativeCanvas } from "../components/GenerativeCanvas";
import type { Appearance } from "../lib/appearance";
import { GENERATIVE_LABEL, GENERATIVE_NOTE, GENERATIVE_STYLES, generativeOf, wallpaperOf, type Generative } from "../lib/generative";
import { SCENES } from "../lib/scenes";
import { readPrefs, type ArtPrefs } from "../lib/wallpaper/art";
import { core, inQt, pickFiles, wallpaperUrl } from "../lib/host";
import { Switch } from "./Page";
import type { Harness } from "./HarnessView";

// Aparencia (Configuracoes): cada mudanca aparece na hora e e gravada em seguida, sem botao Salvar.
// A prévia completa vai para a janela antes da gravação. A fila grava a versão mais recente, uma de cada vez.

type Look = Appearance & { wallpaper?: string; dim?: number; [k: string]: unknown };
type Reply = { ok?: boolean; error?: string } & Record<string, unknown>;
const call = (p: Promise<unknown>) => p.then((r) => r as Reply).catch((e: Error) => ({ ok: false, error: e.message }) as Reply);

export const PALETTES: Array<[id: string, label: string]> = [
  ["abismo", "Abismo"], ["oceano", "Oceano"], ["gelo", "Gelo"], ["brisa", "Brisa"], ["nevoa", "Névoa"],
  ["menta", "Menta"], ["matcha", "Matcha"], ["floresta", "Floresta"], ["fosforo", "Fósforo"], ["areia", "Areia"],
  ["sepia", "Sépia"], ["aurora", "Aurora"], ["coral", "Coral"], ["crepusculo", "Crepúsculo"], ["seda", "Seda"],
  ["ameixa", "Ameixa"], ["lavanda", "Lavanda"], ["neon", "Neon"], ["aurora-boreal", "Aurora boreal"], ["grafite", "Grafite"],
];
export const ACCENTS: Array<[hex: string, name: string]> = [
  ["#16897E", "Verde-água"], ["#0EA5A4", "Turquesa"], ["#2F6FDB", "Azul"], ["#4F46E5", "Anil"], ["#7A4FD6", "Violeta"],
  ["#A855F7", "Roxo neon"], ["#C2417A", "Magenta"], ["#E11D48", "Carmim"], ["#D9622B", "Laranja"], ["#B45309", "Âmbar"],
  ["#3F8F3A", "Verde"], ["#22C55E", "Fósforo"], ["#64748B", "Grafite"],
];
interface Combo { id: string; name: string; note: string; mode: string; palette: string; accent: string; wallpaper: string }
/** Combinacoes prontas: cada uma com cenario, estilo, paleta e destaque proprios (um clique, uma gravacao). */
export const COMBOS: Combo[] = [
  { id: "abismo", name: "Abismo", note: "O padrão: escuro e calmo, só luzes", mode: "escuro", palette: "abismo", accent: "#16897E", wallpaper: "" },
  { id: "synthwave", name: "Synthwave", note: "Sol listrado em dithering", mode: "escuro", palette: "neon", accent: "#A855F7", wallpaper: "gen:dither:retro" },
  { id: "terminal", name: "Terminal", note: "Fósforo verde em pontos", mode: "escuro", palette: "fosforo", accent: "#22C55E", wallpaper: "gen:halftone:retro" },
  { id: "aquario", name: "Aquário", note: "Peixes e bolhas em pontos", mode: "escuro", palette: "oceano", accent: "#0EA5A4", wallpaper: "gen:halftone:aquario" },
  { id: "gatinhos", name: "Gatinhos", note: "Gatos no telhado ao luar", mode: "escuro", palette: "ameixa", accent: "#C2417A", wallpaper: "gen:dither:gatinhos" },
  { id: "frutas", name: "Frutas", note: "Natureza-morta impressa em pontos", mode: "claro", palette: "coral", accent: "#D9622B", wallpaper: "gen:halftone:frutas" },
  { id: "rio", name: "Rio de Janeiro", note: "Cristo, Pão de Açúcar e calçadão", mode: "escuro", palette: "crepusculo", accent: "#E11D48", wallpaper: "gen:dither:rio" },
  { id: "oeste", name: "Velho Oeste", note: "Cactos e mesas ao pôr do sol", mode: "claro", palette: "areia", accent: "#B45309", wallpaper: "gen:dither:texas" },
  { id: "noite", name: "Noite estrelada", note: "Redemoinhos no céu", mode: "escuro", palette: "gelo", accent: "#4F46E5", wallpaper: "gen:dither:noite" },
  { id: "jardim", name: "Jardim", note: "Flores e borboletas em pontos", mode: "claro", palette: "menta", accent: "#E11D48", wallpaper: "gen:halftone:jardim" },
  { id: "bosque", name: "Bosque", note: "Pinheiros na névoa, em pixels", mode: "escuro", palette: "floresta", accent: "#3F8F3A", wallpaper: "gen:dither:bosque" },
  { id: "lago", name: "Lago", note: "Montanhas refletidas na água", mode: "escuro", palette: "nevoa", accent: "#2F6FDB", wallpaper: "gen:halftone:lago" },
  { id: "praia", name: "Praia", note: "Coqueiro, ondas e guarda-sol em pixels", mode: "claro", palette: "brisa", accent: "#0891B2", wallpaper: "gen:dither:praia" },
  { id: "grafite", name: "Grafite", note: "Neutro, sem distração", mode: "claro", palette: "grafite", accent: "#7A4FD6", wallpaper: "" },
];

const same = (a: unknown, b: unknown) => String(a ?? "").toUpperCase() === String(b ?? "").toUpperCase();

/** Grupo de opcoes com setas do teclado (um item focavel por vez), como um grupo de botoes de radio. */
function RadioGroup({ label, className, children }: { label: string; className?: string; children: React.ReactNode }) {
  return (
    <div role="radiogroup" aria-label={label} className={className}
      onKeyDown={(event) => {
        const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
        if (!step) return;
        const items = [...event.currentTarget.querySelectorAll<HTMLElement>('[role="radio"]')];
        const index = items.indexOf(document.activeElement as HTMLElement);
        if (index < 0) return;
        event.preventDefault();
        const next = items[(index + step + items.length) % items.length]!;
        next.focus();
        next.click();
      }}>
      {children}
    </div>
  );
}

function Section({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section className="look-section">
      <header><h3>{title}</h3>{note && <p>{note}</p>}</header>
      {children}
    </section>
  );
}

export function AppearancePanel({ harness, writable, onPreview, onSaved }: {
  harness: Harness;
  writable: boolean;
  onPreview: (look: Look | null) => void;
  /** a gravacao mais recente terminou (o app aplica a aparencia e o papel de parede) */
  onSaved: (h: Harness) => void;
}) {
  const [look, setLook] = useState<Look>(() => ({ ...(harness.appearance as Look) }));
  const lookRef = useRef(look);
  const base = useRef(harness);
  useEffect(() => { base.current = harness; }, [harness]);
  const [error, setError] = useState("");
  const [status, setStatus] = useState<"" | "saving" | "saved">("");

  // Fila de gravacao: so a versao mais recente vai para o nucleo, uma por vez
  const queue = useRef<{ inflight: boolean; next: Look | null; timer: number }>({ inflight: false, next: null, timer: 0 });
  const flush = useCallback(async () => {
    const q = queue.current;
    if (q.inflight || !q.next) return;
    const appearance = q.next;
    q.next = null;
    q.inflight = true;
    setStatus("saving");
    try {
      const r = await call(core().call("harnessPatch", JSON.stringify({ appearance }), "Aparência"));
      if (r.ok) base.current = r.harness as Harness;
      if (q.next) return;                       // uma resposta antiga não deve substituir a prévia mais recente
      if (!r.ok) {
        setError(r.error || "Não deu para salvar a aparência.");
        lookRef.current = base.current.appearance;
        setLook(lookRef.current);
        setStatus("");
      } else {
        setError("");
        setStatus("saved");
      }
      onSaved(base.current);
      onPreview(null);
    } finally {
      q.inflight = false;
      if (q.next) void flush();
    }
  }, [onPreview, onSaved]);
  useEffect(() => () => {
    window.clearTimeout(queue.current.timer);
    void flush();
  }, [flush]);

  /** Muda uma ou mais opcoes: aparece na hora; grava em seguida (sliders esperam um pouco o fim do arraste). */
  const change = useCallback((patch: Partial<Look>, wait = 0) => {
    if (!writable) return;
    const next = { ...lookRef.current, ...patch };
    lookRef.current = next;
    setLook(next);
    onPreview(next);
    queue.current.next = next;
    window.clearTimeout(queue.current.timer);
    queue.current.timer = window.setTimeout(() => void flush(), wait);
  }, [flush, onPreview, writable]);

  const mode = String(look.mode ?? "escuro");
  const wallpaper = String(look.wallpaper ?? "");
  const customAccent = !ACCENTS.some(([hex]) => same(hex, look.accent));
  const prefs = readPrefs(look.art);
  const setPref = <K extends keyof ArtPrefs>(key: K, value: ArtPrefs[K]) =>
    change({ art: { ...readPrefs(lookRef.current.art), [key]: value } });

  return (
    <div className="look-panel" aria-disabled={!writable || undefined}>
      <div className="look-status" role="status" aria-live="polite">
        {error ? <span className="text-bad-ink">{error}</span>
          : status === "saving" ? <><span className="look-dot" data-busy /> Salvando…</>
          : status === "saved" ? <><Icon name="check" size={14} /> Salvo. A versão anterior fica em Versões.</>
          : "Tudo aqui muda na hora e fica salvo sozinho."}
      </div>

      <AppearancePreview wallpaper={wallpaper} look={`${mode}|${look.palette}|${look.accent}`} prefs={prefs} />

      <Section title="Combinações" note="Tema, paleta, destaque e fundo pensados juntos. Um clique aplica tudo.">
        <RadioGroup label="Combinações" className="look-combos">
          {COMBOS.map((combo) => {
            const on = same(look.palette, combo.palette) && same(look.mode, combo.mode) && same(look.accent, combo.accent) && same(wallpaper, combo.wallpaper);
            const gen = generativeOf(combo.wallpaper);
            return (
              <button key={combo.id} type="button" role="radio" aria-checked={on} tabIndex={on ? 0 : -1} className="look-combo"
                onClick={() => change({ mode: combo.mode, palette: combo.palette, accent: combo.accent, wallpaper: combo.wallpaper })}>
                <span className="look-combo-art" data-theme={combo.mode} data-palette={combo.palette} style={{ "--accent": combo.accent } as React.CSSProperties}>
                  {gen ? <GenerativeCanvas art={gen} look={combo.id} className="size-full" deferred /> : <span className="look-lights" />}
                  <i />
                  {gen && <span className="look-combo-style">{GENERATIVE_LABEL[gen.style]}</span>}
                </span>
                <span className="look-combo-text"><strong>{combo.name}</strong><small>{combo.note}</small></span>
                {on && <Icon name="check" size={14} className="look-check" />}
              </button>
            );
          })}
        </RadioGroup>
      </Section>

      <Section title="Tema">
        <Segmented label="Tema" value={mode as "escuro" | "claro"} onValueChange={(v) => change({ mode: v })}
          options={[{ value: "escuro", label: "Escuro" }, { value: "claro", label: "Claro" }]} />
      </Section>

      <Section title="Paleta" note="As cores de fundo e das luzes. Use as setas para percorrer.">
        <RadioGroup label="Paleta" className="look-palettes">
          {PALETTES.map(([id, label]) => {
            const on = same(look.palette, id);
            return (
              <button key={id} type="button" role="radio" aria-checked={on} tabIndex={on ? 0 : -1} className="look-palette"
                onClick={() => change({ palette: id })}>
                <span className="look-swatch" data-theme={mode} data-palette={id}><i /><i /><i /><i /></span>
                <span>{label}</span>
                {on && <Icon name="check" size={13} className="look-check" />}
              </button>
            );
          })}
        </RadioGroup>
      </Section>

      <Section title="Destaque" note="A cor de botões, seleções e foco.">
        <div className="look-accents">
          <RadioGroup label="Cor de destaque" className="contents">
            {ACCENTS.map(([hex, name]) => {
              const on = same(look.accent, hex);
              return (
                <button key={hex} type="button" role="radio" aria-checked={on} tabIndex={on || (customAccent && hex === ACCENTS[0]![0]) ? 0 : -1}
                  aria-label={name} title={name} className="look-accent" style={{ background: hex }} onClick={() => change({ accent: hex })}>
                  {on && <Icon name="check" size={14} />}
                </button>
              );
            })}
          </RadioGroup>
          <label className="look-accent look-accent-custom" data-on={customAccent || undefined} title="Escolher outra cor"
            style={customAccent ? { background: String(look.accent) } : undefined}>
            <input type="color" aria-label="Escolher outra cor de destaque" value={String(look.accent ?? "#16897E").toLowerCase()}
              onChange={(e) => change({ accent: e.target.value.toUpperCase() }, 250)} />
            {customAccent ? <Icon name="check" size={14} /> : <Icon name="plus" size={14} />}
          </label>
          <code className="look-hex">{String(look.accent ?? "").toUpperCase()}</code>
        </div>
      </Section>

      <Section title="Fundo" note="Só as luzes da paleta, uma arte gerativa (cena e estilo) com as suas cores, ou uma foto.">
        <Backdrops current={wallpaper} look={`${mode}|${look.palette}|${look.accent}`} prefs={prefs} onPick={(id) => change({ wallpaper: id })} />
        <div className="look-sliders">
          {wallpaper ? (
            <label className="look-slider">
              <span>Escurecer o fundo</span>
              <input type="range" min={0.15} max={0.85} step={0.05} value={Number(look.dim ?? 0.35)}
                onChange={(e) => change({ dim: Number(e.target.value) }, 300)} aria-label="Escurecer o fundo" />
              <output>{Math.round(Number(look.dim ?? 0.35) * 100)}%</output>
            </label>
          ) : (
            <label className="look-slider">
              <span>Intensidade das luzes</span>
              <input type="range" min={0} max={1} step={0.05} value={Number(look.ambient ?? 0.55)}
                onChange={(e) => change({ ambient: Number(e.target.value) }, 300)} aria-label="Intensidade das luzes de fundo" />
              <output>{Math.round(Number(look.ambient ?? 0.55) * 100)}%</output>
            </label>
          )}
        </div>
        {generativeOf(wallpaper) && (
          // Opcoes tecnicas fora do caminho principal (escolher, ver, aplicar): "Auto" segue a cena e o aparelho
          <details className="look-advanced">
            <summary>Avançado</summary>
            <div className="look-toggles">
              <div className="look-toggle">
                <span><strong>Dithering</strong><small>Bayer é a trama clássica; ruído azul deixa degradês lisos; Atkinson dá textura.</small></span>
                <Segmented label="Algoritmo do dithering" value={prefs.dither} onValueChange={(v) => setPref("dither", v)}
                  options={[{ value: "auto", label: "Auto" }, { value: "bayer", label: "Bayer" }, { value: "blue", label: "Ruído azul" }, { value: "atkinson", label: "Atkinson" }]} />
              </div>
              <div className="look-toggle">
                <span><strong>Qualidade</strong><small>Eco usa marcas maiores e menos processamento; Alto, mais detalhe. Auto escolhe pelo computador.</small></span>
                <Segmented label="Qualidade do papel de parede" value={prefs.quality} onValueChange={(v) => setPref("quality", v)}
                  options={[{ value: "auto", label: "Auto" }, { value: "eco", label: "Eco" }, { value: "equilibrado", label: "Equilibrado" }, { value: "alto", label: "Alto" }]} />
              </div>
              <div className="look-toggle">
                <span><strong>Movimento do fundo</strong><small>Estrelas, bolhas, pétalas, brilhos na água. Para sozinho com a janela sem foco.</small></span>
                <Segmented label="Movimento do fundo" value={prefs.motion} onValueChange={(v) => setPref("motion", v)}
                  options={[{ value: "auto", label: "Auto" }, { value: "parado", label: "Parado" }, { value: "sutil", label: "Sutil" }, { value: "animado", label: "Animado" }]} />
              </div>
            </div>
          </details>
        )}
      </Section>

      <Section title="Vidro e movimento">
        <div className="look-toggles">
          <div className="look-toggle">
            <span><strong>Desfoque</strong><small>Barra lateral, painéis e a caixa de conversa viram vidro fosco sobre o fundo.</small></span>
            <Switch label="Vidro com desfoque" checked={look.blur !== false} onChange={(v) => change({ blur: v })} />
          </div>
          <div className="look-toggle">
            <span><strong>Movimento</strong><small>Transições e animações. Desligado, tudo muda sem animar.</small></span>
            <Switch label="Movimento" checked={look.motion !== false} onChange={(v) => change({ motion: v })} />
          </div>
          <div className="look-toggle">
            <span><strong>Cantos</strong><small>Arredondamento de painéis e botões.</small></span>
            <Segmented label="Cantos" value={String(look.radius ?? "suave") as "suave" | "reto" | "redondo"} onValueChange={(v) => change({ radius: v })}
              options={[{ value: "reto", label: "Reto" }, { value: "suave", label: "Suave" }, { value: "redondo", label: "Redondo" }]} />
          </div>
        </div>
      </Section>
    </div>
  );
}

interface Photo { id: string; title: string; author?: string }
type Kind = "luzes" | "arte" | "foto";

/** Fundo em dois passos: o tipo (luzes, arte gerativa, foto) e, na arte, a cena e o estilo separados.
 *  As miniaturas das cenas sao desenhadas ao vivo no estilo e nas cores atuais. */
function Backdrops({ current, look, prefs, onPick }: { current: string; look: string; prefs: ArtPrefs; onPick: (id: string) => void }) {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [error, setError] = useState("");
  const art = generativeOf(current);
  const kind: Kind = !current ? "luzes" : art ? "arte" : "foto";
  const [shown, setShown] = useState<Kind>(kind);
  useEffect(() => setShown(kind), [kind]);
  const lastArt = useRef<Generative>(art ?? { style: "dither", scene: "retro" });
  if (art) lastArt.current = art;
  const load = useCallback(() => {
    if (inQt) void call(core().call("wallpapersList")).then((r) => r.ok && setPhotos((r.items as Photo[]) ?? []));
  }, []);
  useEffect(load, [load]);

  const importPhoto = async () => {
    const [path] = await pickFiles();
    if (!path) return;
    const r = await call(core().call("wallpaperImport", path));
    if (!r.ok) return setError(r.error || "Não deu para importar.");
    setError("");
    load();
    const item = r.item as Photo | undefined;
    if (item?.id) onPick(item.id);
  };

  const pickKind = (next: Kind) => {
    setShown(next);
    if (next === "luzes") onPick("");
    else if (next === "arte") onPick(wallpaperOf(lastArt.current));
    else if (photos[0] && kind !== "foto") onPick(photos[0].id);
  };
  const style = lastArt.current.style;

  return (
    <div className="look-backdrop-studio">
      <Segmented label="Tipo de fundo" value={shown} onValueChange={pickKind}
        options={[{ value: "luzes", label: "Luzes" }, { value: "arte", label: "Arte gerativa" }, { value: "foto", label: "Foto" }]} />

      {shown === "arte" && <>
        <div className="look-style-row">
          <Segmented label="Estilo" value={style} onValueChange={(next) => onPick(wallpaperOf({ ...lastArt.current, style: next }))}
            options={GENERATIVE_STYLES.map((item) => ({ value: item, label: GENERATIVE_LABEL[item] }))} />
          <small>{GENERATIVE_NOTE[style]}</small>
        </div>
        <RadioGroup label="Cena" className="look-scenes">
          {SCENES.map((scene) => {
            const on = art?.scene === scene.id;
            return (
              <button key={scene.id} type="button" role="radio" aria-checked={on} tabIndex={on || (!art && scene.id === "retro") ? 0 : -1}
                className="look-backdrop" onClick={() => onPick(wallpaperOf({ style, scene: scene.id }))}>
                <span className="look-backdrop-art"><GenerativeCanvas art={{ style, scene: scene.id }} look={look} prefs={prefs} className="size-full" deferred /></span>
                <span className="look-backdrop-text"><strong>{scene.label}</strong></span>
                {on && <Icon name="check" size={14} className="look-check" />}
              </button>
            );
          })}
        </RadioGroup>
      </>}

      {shown === "foto" && <>
        {photos.length ? (
          <RadioGroup label="Foto" className="look-backdrops">
            {photos.map((photo) => {
              const on = photo.id === current;
              const url = wallpaperUrl(photo.id);
              return (
                <button key={photo.id} type="button" role="radio" aria-checked={on} tabIndex={on ? 0 : -1} className="look-backdrop" onClick={() => onPick(photo.id)}>
                  <span className="look-backdrop-art">{url && <img src={url} alt="" decoding="async" loading="lazy" />}</span>
                  <span className="look-backdrop-text"><strong>{photo.title}</strong><small>{photo.author || "Foto"}</small></span>
                  {on && <Icon name="check" size={14} className="look-check" />}
                </button>
              );
            })}
          </RadioGroup>
        ) : <p className="text-sm text-fg-muted">Nenhuma foto ainda. Importe uma imagem PNG, JPG ou WebP.</p>}
        {inQt && <div className="flex items-center gap-3">
          <Button size="compact" icon="image" onClick={() => void importPhoto()}>Importar foto</Button>
          {error && <span className="text-sm text-bad-ink">{error}</span>}
        </div>}
      </>}
    </div>
  );
}

/** Previa ao vivo no alto da secao: uma janela em miniatura com as cores e o fundo atuais. */
export function AppearancePreview({ wallpaper, look, prefs }: { wallpaper: string; look: string; prefs?: ArtPrefs }) {
  const gen = generativeOf(wallpaper);
  const url = wallpaperUrl(wallpaper);
  return (
    <div className="look-preview" aria-hidden>
      <div className="look-preview-bg">
        {gen ? <GenerativeCanvas art={gen} look={look} prefs={prefs} className="size-full" /> : url ? <img src={url} alt="" /> : <span className="look-lights" />}
      </div>
      <div className="look-preview-side"><i /><i /><i /><i /></div>
      <div className="look-preview-main">
        <span className="look-preview-bubble">Abra o site do projeto no navegador</span>
        <span className="look-preview-answer">Pronto! Abri o index.html.</span>
        <span className="look-preview-composer"><em>Escreva um pedido…</em><b /></span>
      </div>
    </div>
  );
}

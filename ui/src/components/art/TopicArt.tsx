import { memo, useId } from "react";
import type { Motif, TopicLook } from "../../lib/topics";

// Capa generativa de um tema: SVG puro, sem imagem nem rede (leve e nitida em qualquer tamanho).
//   variant="dots"  arte pontilhada sobre papel (cards da grade)
//   variant="glass" gradiente vivo com linhas finas (carrossel e capa do leitor)
// O desenho e decorativo (aria-hidden); o titulo do tema fica no texto do card.

const W = 300;
const H = 220;

function MotifShape({ motif }: { motif: Motif }) {
  switch (motif) {
    case "dial":
      return (
        <g fill="none" stroke="#fff">
          <circle cx="150" cy="110" r="78" strokeWidth="16" />
          <circle cx="150" cy="110" r="46" strokeWidth="10" />
          <path d="M150 110 L228 110 A78 78 0 0 1 150 188 Z" fill="#fff" stroke="none" />
          {Array.from({ length: 12 }, (_, i) => {
            const a = (i / 12) * Math.PI * 2;
            return <circle key={i} cx={150 + Math.cos(a) * 98} cy={110 + Math.sin(a) * 98} r="3.5" fill="#fff" stroke="none" />;
          })}
        </g>
      );
    case "layers":
      return (
        <g fill="#fff">
          {[0, 1, 2, 3, 4].map((i) => (
            <path key={i} d={`M${60 + i * 6} ${150 - i * 26} l90 -34 l90 34 l-90 34 z`} opacity={1 - i * 0.12} />
          ))}
        </g>
      );
    case "arrow":
      return (
        <g fill="#fff">
          <path d="M40 30 L230 110 L40 190 L95 110 Z" />
          <path d="M150 64 L262 110 L150 156 L180 110 Z" opacity="0.7" />
        </g>
      );
    case "network":
      return (
        <g stroke="#fff" fill="#fff" strokeWidth="9" strokeLinecap="round">
          <path d="M150 50 L70 160 M150 50 L230 160 M70 160 L230 160 M150 50 L150 120 M70 160 L150 120 L230 160" fill="none" />
          <circle cx="150" cy="50" r="22" />
          <circle cx="70" cy="160" r="22" />
          <circle cx="230" cy="160" r="22" />
          <circle cx="150" cy="120" r="14" />
        </g>
      );
    case "rings":
      return (
        <g fill="none" stroke="#fff">
          <circle cx="150" cy="110" r="88" strokeWidth="14" />
          <circle cx="150" cy="110" r="56" strokeWidth="14" />
          <circle cx="150" cy="110" r="22" fill="#fff" />
          <path d="M150 0 V220 M40 110 H260" strokeWidth="3" />
        </g>
      );
    case "hourglass":
      return (
        <g fill="#fff">
          <path d="M90 22 H210 L150 110 Z" />
          <path d="M150 110 L210 198 H90 Z" opacity="0.65" />
          <path d="M150 110 L250 60 M150 110 L250 160 M150 110 L50 60 M150 110 L50 160" stroke="#fff" strokeWidth="5" />
        </g>
      );
    case "nested":
      return (
        <g fill="none" stroke="#fff" strokeWidth="12">
          <rect x="45" y="18" width="210" height="184" rx="10" />
          <rect x="85" y="50" width="130" height="120" rx="8" />
          <rect x="120" y="80" width="60" height="60" rx="6" fill="#fff" />
        </g>
      );
    case "sphere":
      return (
        <g fill="none" stroke="#fff" strokeWidth="5">
          <circle cx="150" cy="110" r="90" strokeWidth="9" />
          {[30, 58, 82].map((rx) => (
            <ellipse key={rx} cx="150" cy="110" rx={rx} ry="90" />
          ))}
          {[-55, -20, 20, 55].map((dy) => (
            <path key={dy} d={`M${150 - Math.sqrt(8100 - dy * dy)} ${110 + dy} H${150 + Math.sqrt(8100 - dy * dy)}`} />
          ))}
        </g>
      );
    case "globe":
      return (
        <g fill="#fff">
          <circle cx="150" cy="110" r="84" opacity="0.35" />
          <path d="M98 70 q30 -24 58 -6 q14 18 -6 30 q-22 8 -14 30 q-30 6 -40 -20 q-12 -20 2 -34z" />
          <path d="M170 120 q30 -10 44 10 q6 30 -22 44 q-24 4 -26 -24 q-2 -18 4 -30z" />
          <ellipse cx="150" cy="110" rx="128" ry="26" fill="none" stroke="#fff" strokeWidth="5" transform="rotate(-18 150 110)" />
        </g>
      );
    case "streams":
      return (
        <g fill="none" stroke="#fff" strokeLinecap="round">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <path key={i} d={`M10 ${40 + i * 28} C 90 ${40 + i * 28}, 110 110, 160 110 S 240 ${40 + i * 28}, 292 ${40 + i * 28}`} strokeWidth={10 - i} />
          ))}
        </g>
      );
  }
}

export const TopicArt = memo(function TopicArt({
  look,
  variant = "dots",
  className,
}: {
  look: TopicLook;
  variant?: "dots" | "glass";
  className?: string;
}) {
  const uid = useId().replace(/:/g, "");
  if (variant === "glass") {
    return (
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" className={className} aria-hidden>
        <defs>
          <radialGradient id={`g1${uid}`} cx="30%" cy="25%" r="80%">
            <stop offset="0" stopColor={look.glow} />
            <stop offset="0.45" stopColor={look.c} />
            <stop offset="1" stopColor={look.deep} />
          </radialGradient>
          <radialGradient id={`g2${uid}`} cx="85%" cy="90%" r="60%">
            <stop offset="0" stopColor={look.glow} stopOpacity="0.75" />
            <stop offset="1" stopColor={look.glow} stopOpacity="0" />
          </radialGradient>
          <mask id={`m${uid}`}>
            <MotifShape motif={look.motif} />
          </mask>
        </defs>
        <rect width={W} height={H} fill={`url(#g1${uid})`} />
        <rect width={W} height={H} fill={`url(#g2${uid})`} />
        <rect width={W} height={H} fill="#fff" opacity="0.28" mask={`url(#m${uid})`} />
      </svg>
    );
  }
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" className={className} aria-hidden>
      <defs>
        <pattern id={`p${uid}`} width="6" height="6" patternUnits="userSpaceOnUse">
          <circle cx="3" cy="3" r="1.55" fill={look.c} />
        </pattern>
        <radialGradient id={`f${uid}`} cx="50%" cy="50%" r="60%">
          <stop offset="0" stopColor="#fff" />
          <stop offset="1" stopColor="#fff" stopOpacity="0.35" />
        </radialGradient>
        <mask id={`m${uid}`}>
          <rect width={W} height={H} fill="#000" />
          <g opacity="0.95">
            <MotifShape motif={look.motif} />
          </g>
          <rect width={W} height={H} fill={`url(#f${uid})`} style={{ mixBlendMode: "multiply" }} />
        </mask>
      </defs>
      <rect width={W} height={H} fill="var(--art-paper)" />
      <g className="art-drift">
        <rect x="-12" y="-12" width={W + 24} height={H + 24} fill={`url(#p${uid})`} mask={`url(#m${uid})`} />
      </g>
    </svg>
  );
});

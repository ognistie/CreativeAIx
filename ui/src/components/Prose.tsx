import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { slug } from "../lib/slug";

// Leitura longa (artigos da Biblioteca). Tipografia em .prose (styles/index.css). Titulos ## ganham id
// para o indice lateral; links abrem fora pelo host (o app nunca navega a pagina para outro site).

const text = (children: React.ReactNode): string =>
  Array.isArray(children) ? children.map(text).join("") : typeof children === "string" || typeof children === "number" ? String(children) : "";

export function Prose({ markdown, onLink, className }: { markdown: string; onLink: (href: string) => void; className?: string }) {
  return (
    <div className={className ? `prose select-text ${className}` : "prose select-text"}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h2: ({ children }) => <h2 id={slug(text(children))}>{children}</h2>,
          a: ({ href, children }) => (
            <a
              href={href}
              onClick={(e) => {
                e.preventDefault();
                if (href) onLink(href);
              }}
            >
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div className="prose-table">
              <table>{children}</table>
            </div>
          ),
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}

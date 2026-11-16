import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "./ui";

// Uma tela que quebra nao derruba o app inteiro: sem isto o React desmonta a arvore toda e sobra uma
// janela em branco ate reiniciar. Aqui a falha fica contida na tela, com o motivo e um jeito de voltar.

interface Props {
  children: ReactNode;
  /** Mudou (ex.: a tela atual)? A falha anterior e esquecida. */
  resetKey?: unknown;
  onHome?: () => void;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Vai para o log do app (web_host.Page.javaScriptConsoleMessage)
    console.error(`[tela] ${error.message}\n${info.componentStack ?? ""}`);
  }

  componentDidUpdate(prev: Props) {
    if (this.state.error && prev.resetKey !== this.props.resetKey) this.setState({ error: null });
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div role="alert" className="animate-enter mx-auto flex h-full max-w-md flex-col items-center justify-center px-6 text-center">
        <div className="glass-solid rounded-r4 px-8 py-7">
          <p className="font-display text-xl font-medium text-fg">Esta tela teve um problema</p>
          <p className="mt-2 text-sm text-fg-muted">O resto do app continua funcionando. O detalhe foi para o log.</p>
          <p className="mt-3 break-words font-mono text-xs text-fg-subtle">{this.state.error.message}</p>
          <div className="mt-5 flex justify-center gap-2">
            <Button variant="primary" icon="refresh" onClick={() => this.setState({ error: null })}>
              Tentar de novo
            </Button>
            {this.props.onHome && <Button onClick={this.props.onHome}>Ir para a conversa</Button>}
          </div>
        </div>
      </div>
    );
  }
}

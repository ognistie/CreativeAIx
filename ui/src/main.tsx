import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { Gallery } from "./Gallery";
import { applyAppearance, readLook } from "./lib/appearance";
import "@fontsource-variable/inter/opsz.css";
import "@fontsource-variable/geist/wght.css";
import "./styles/index.css";

// Tema e paleta da ultima vez antes do primeiro quadro: a abertura nao nasce no tema padrao.
applyAppearance(readLook().appearance);

// #galeria abre o design system (revisao visual sem o nucleo)
const Root = window.location.hash === "#galeria" ? Gallery : App;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);

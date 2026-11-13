import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { Gallery } from "./Gallery";
import "./styles/index.css";

// #galeria abre o design system (revisao visual sem o nucleo)
const Root = window.location.hash === "#galeria" ? Gallery : App;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import MapPage from "./MapPage.tsx";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MapPage />
  </StrictMode>
);

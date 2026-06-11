import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@/i18n";
import "./index.css";
import App from "./App.tsx";
import { ErrorBoundary } from "@/components/ErrorBoundary";

// Deploy marker. Answers "quelle version tourne en prod ?" in 2 seconds:
// open the console (gridar build <sha>) or inspect <html data-build>.
// Set from VERCEL_GIT_COMMIT_SHA at build time; "dev" locally.
console.info(`gridar build ${__BUILD_SHA__}`);
document.documentElement.dataset.build = __BUILD_SHA__;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>
);

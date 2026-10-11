import type { Metadata } from "next";
import { Sidebar } from "@/components/Sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "Job Funnel",
  description: "Decide faster, apply more, measure what happened.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:wght@400&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        {/* El menú va a la izquierda y es el mismo en todas las pantallas. El orden
            es el del trabajo real: decidir, aplicar, seguir, medir. */}
        <div className="app">
          <Sidebar />
          <div className="content">{children}</div>
        </div>
      </body>
    </html>
  );
}

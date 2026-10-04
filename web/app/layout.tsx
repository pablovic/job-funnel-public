import type { Metadata } from "next";
import Link from "next/link";
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
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Serif:wght@400&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <div className="shell">
          <header className="masthead">
            <h1>Job Funnel</h1>
            {/* El orden es el del trabajo real: decidir, aplicar, seguir, medir. */}
            <nav>
              <Link href="/triage">Decide</Link>
              <Link href="/apply">Apply</Link>
              <Link href="/pipeline">Applications</Link>
              <Link href="/analytics">Funnel</Link>
            </nav>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}

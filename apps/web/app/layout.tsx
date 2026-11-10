import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import { fontVariables } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: "Медархив",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru" className={fontVariables}>
      <body>{children}</body>
    </html>
  );
}

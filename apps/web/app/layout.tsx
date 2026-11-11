import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import type { ReactNode } from "react";

import { themeScript } from "@/components/ui/theme";
import { texts } from "@/lib/texts";

import { fontVariables } from "./fonts";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: texts["app.name"],
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const nonce = (await headers()).get("x-nonce") ?? undefined;

  return (
    // The theme script sets data-theme before hydration, so the attribute differs from the server HTML.
    <html lang="ru" className={fontVariables} suppressHydrationWarning>
      <head>
        {/* Static constant, no user data: the only way to set the theme before first paint.
            Browsers hide the nonce attribute after load, so hydration sees it empty. */}
        <script
          nonce={nonce}
          suppressHydrationWarning
          dangerouslySetInnerHTML={{ __html: themeScript }}
        />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

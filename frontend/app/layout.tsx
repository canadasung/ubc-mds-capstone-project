import "@mantine/core/styles.css";
import "@xyflow/react/dist/style.css";
import "./globals.css";

import type { Metadata } from "next";
import { ColorSchemeScript, MantineProvider } from "@mantine/core";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Species Name Synonym Search",
  description:
    "Beaty Biodiversity Museum — synthesize species name synonyms and taxonomy across databases.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <ColorSchemeScript />
      </head>
      <body>
        <MantineProvider defaultColorScheme="light">
          <Providers>{children}</Providers>
        </MantineProvider>
      </body>
    </html>
  );
}

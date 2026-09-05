import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "Lenny Growth Assistant", description: "Grounded podcast knowledge" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  // Browser extensions commonly add attributes to the document before React hydrates.
  return <html lang="en" suppressHydrationWarning><body suppressHydrationWarning>{children}</body></html>;
}

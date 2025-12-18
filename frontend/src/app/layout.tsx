import type { Metadata } from "next";
import "./globals.css";
import { SessionProvider } from "@/contexts/SessionContext";

export const metadata: Metadata = {
  title: "Leaf - Discover Your Next Favorite Book",
  description:
    "Get personalized book recommendations powered by AI. Tell us about your reading preferences and discover books you'll love.",
  icons: {
    icon: "/svgs/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <SessionProvider>{children}</SessionProvider>
      </body>
    </html>
  );
}

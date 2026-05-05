import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Rufus Twin — Amazon AEO Diagnostics Platform",
  description:
    "Reverse-engineer how Amazon Rufus AI sees your product listing. Get a full AEO report card, competitor gap analysis, and market size estimate — powered by Gemini 2.5 Flash.",
  keywords: [
    "Amazon Rufus",
    "AEO",
    "Answer Engine Optimization",
    "Amazon listing optimizer",
    "AI shopping assistant",
    "Amazon seller tools",
    "market size estimator",
  ],
  openGraph: {
    title: "Rufus Twin — Amazon AEO Diagnostics",
    description: "See your product through Rufus's eyes. Fix what the AI penalizes.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

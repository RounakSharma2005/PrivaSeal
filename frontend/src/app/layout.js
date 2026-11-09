import "./globals.css";

export const metadata = {
  title: "Privaseal – Privacy-First Document Protection",
  description:
    "Analyze, understand, and control every redaction decision. Built for trust and transparency.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="h-full overflow-hidden bg-[#F7F6F3] text-[#2F3437]">
        {children}
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import "./globals.css";
import { getCurrentSite, getThemeStyle } from "@/lib/site-context";

export async function generateMetadata(): Promise<Metadata> {
  const site = await getCurrentSite();
  if (!site) {
    return {
      title: "Blog",
      description: "Site non configuré.",
    };
  }
  return {
    title: { default: site.name, template: `%s — ${site.name}` },
    description: site.description || `Blog de ${site.name}`,
    openGraph: {
      title: site.name,
      description: site.description || "",
      images: site.og_image_url ? [{ url: site.og_image_url }] : [],
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
      title: site.name,
      description: site.description || "",
      images: site.og_image_url ? [site.og_image_url] : [],
    },
  };
}

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const site = await getCurrentSite();
  const themeStyle = site ? getThemeStyle(site) : {};
  const lang = site?.default_language || "fr";

  return (
    <html lang={lang} style={themeStyle}>
      <body className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 min-h-screen flex flex-col">
        {site && <Header site={site} />}
        <main className="flex-1">{children}</main>
        {site && <Footer site={site} />}
        {/* Schema.org Person — boost EEAT */}
        {site?.person_schema && (
          <script
            type="application/ld+json"
            dangerouslySetInnerHTML={{ __html: JSON.stringify(site.person_schema) }}
          />
        )}
      </body>
    </html>
  );
}

function Header({ site }: { site: NonNullable<Awaited<ReturnType<typeof getCurrentSite>>> }) {
  const logo = site.theme_config?.logo_url;
  return (
    <header className="border-b">
      <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
        <a href="/" className="flex items-center gap-2">
          {logo && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={logo} alt={site.name} className="h-8 w-auto" />
          )}
          <span className="font-display text-xl font-semibold">{site.name}</span>
        </a>
        <nav className="flex items-center gap-6 text-sm">
          <a href="/" className="hover:text-brand">Articles</a>
        </nav>
      </div>
    </header>
  );
}

function Footer({ site }: { site: NonNullable<Awaited<ReturnType<typeof getCurrentSite>>> }) {
  return (
    <footer className="border-t mt-16">
      <div className="max-w-4xl mx-auto px-4 py-8 text-sm text-zinc-600 dark:text-zinc-400">
        <p>
          © {new Date().getFullYear()} {site.name}.
        </p>
        {site.author?.bio && (
          <p className="mt-2">
            <strong>{site.author.name}</strong>
            {site.author.role && ` · ${site.author.role}`}
            {site.author.bio && ` — ${site.author.bio}`}
          </p>
        )}
      </div>
    </footer>
  );
}

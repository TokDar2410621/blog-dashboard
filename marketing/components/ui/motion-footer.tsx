"use client";

import * as React from "react";
import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Link from "next/link";
import { Search, ArrowUpRight, ChevronDown } from "lucide-react";
import { NAV_TOOLS } from "@/lib/tools-nav";
import { cn } from "@/lib/utils";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

// -------------------------------------------------------------------------
// Styles (theme-adaptive, tokens shadcn)
// -------------------------------------------------------------------------
const STYLES = `
.cinematic-footer-wrapper {
  -webkit-font-smoothing: antialiased;

  --pill-bg-1: color-mix(in oklch, var(--foreground) 3%, transparent);
  --pill-bg-2: color-mix(in oklch, var(--foreground) 1%, transparent);
  --pill-shadow: color-mix(in oklch, var(--background) 50%, transparent);
  --pill-highlight: color-mix(in oklch, var(--foreground) 10%, transparent);
  --pill-inset-shadow: color-mix(in oklch, var(--background) 80%, transparent);
  --pill-border: color-mix(in oklch, var(--foreground) 8%, transparent);

  --pill-bg-1-hover: color-mix(in oklch, var(--foreground) 8%, transparent);
  --pill-bg-2-hover: color-mix(in oklch, var(--foreground) 2%, transparent);
  --pill-border-hover: color-mix(in oklch, var(--foreground) 20%, transparent);
  --pill-shadow-hover: color-mix(in oklch, var(--background) 70%, transparent);
  --pill-highlight-hover: color-mix(in oklch, var(--foreground) 20%, transparent);
}

@keyframes footer-breathe {
  0% { transform: translate(-50%, -50%) scale(1); opacity: 0.6; }
  100% { transform: translate(-50%, -50%) scale(1.1); opacity: 1; }
}
@keyframes footer-scroll-marquee {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}
@keyframes footer-heartbeat {
  0%, 100% { transform: scale(1); filter: drop-shadow(0 0 5px color-mix(in oklch, var(--destructive) 50%, transparent)); }
  15%, 45% { transform: scale(1.2); filter: drop-shadow(0 0 10px color-mix(in oklch, var(--destructive) 80%, transparent)); }
  30% { transform: scale(1); }
}

.animate-footer-breathe { animation: footer-breathe 8s ease-in-out infinite alternate; }
.animate-footer-scroll-marquee { animation: footer-scroll-marquee 40s linear infinite; }
.animate-footer-heartbeat { animation: footer-heartbeat 2s cubic-bezier(0.25, 1, 0.5, 1) infinite; }

@media (prefers-reduced-motion: reduce) {
  .animate-footer-breathe, .animate-footer-scroll-marquee, .animate-footer-heartbeat { animation: none; }
}

.footer-bg-grid {
  background-size: 60px 60px;
  background-image:
    linear-gradient(to right, color-mix(in oklch, var(--foreground) 3%, transparent) 1px, transparent 1px),
    linear-gradient(to bottom, color-mix(in oklch, var(--foreground) 3%, transparent) 1px, transparent 1px);
  mask-image: linear-gradient(to bottom, transparent, black 30%, black 70%, transparent);
  -webkit-mask-image: linear-gradient(to bottom, transparent, black 30%, black 70%, transparent);
}

.footer-glass-pill {
  background: linear-gradient(145deg, var(--pill-bg-1) 0%, var(--pill-bg-2) 100%);
  box-shadow:
      0 10px 30px -10px var(--pill-shadow),
      inset 0 1px 1px var(--pill-highlight),
      inset 0 -1px 2px var(--pill-inset-shadow);
  border: 1px solid var(--pill-border);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
.footer-glass-pill:hover {
  background: linear-gradient(145deg, var(--pill-bg-1-hover) 0%, var(--pill-bg-2-hover) 100%);
  border-color: var(--pill-border-hover);
  box-shadow:
      0 20px 40px -10px var(--pill-shadow-hover),
      inset 0 1px 1px var(--pill-highlight-hover);
  color: var(--foreground);
}

.footer-giant-bg-text {
  font-size: 26vw;
  line-height: 0.75;
  font-weight: 900;
  letter-spacing: -0.05em;
  color: transparent;
  -webkit-text-stroke: 1px color-mix(in oklch, var(--foreground) 5%, transparent);
  background: linear-gradient(180deg, color-mix(in oklch, var(--foreground) 10%, transparent) 0%, transparent 60%);
  -webkit-background-clip: text;
  background-clip: text;
}

/* Le rideau tourne partout, telephone compris. Deux choses le rendent possible
 * malgre un pied plus haut que l'ecran : le plan du site part replie sous md,
 * et le bloc central absorbe le surplus en defilement interne, ce qui garde la
 * barre du bas collee en bas. Mesure du 2026-08-23 : la barre reste a l'ecran
 * jusqu'a 560px de haut. En dessous, le pied n'aurait plus de place du tout
 * (paysage de telephone), donc on repasse en flux normal. Le critere est la
 * HAUTEUR disponible, jamais la largeur. */
@media (max-height: 30rem) {
  .cinematic-footer-curtain {
    clip-path: none !important;
    height: auto !important;
  }
  .cinematic-footer-wrapper {
    position: static !important;
    height: auto !important;
  }
}

/* Le triangle natif du <details> jure avec le reste : on met notre chevron. */
.footer-plan-resume::-webkit-details-marker { display: none; }
.footer-plan-resume { list-style: none; }
details[open] .footer-plan-chevron { transform: rotate(180deg); }

.footer-text-glow {
  background: linear-gradient(180deg, var(--foreground) 0%, color-mix(in oklch, var(--foreground) 40%, transparent) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  filter: drop-shadow(0px 0px 20px color-mix(in oklch, var(--foreground) 15%, transparent));
}
`;

// -------------------------------------------------------------------------
// Magnetic button (GSAP)
// -------------------------------------------------------------------------
export type MagneticButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> &
  React.AnchorHTMLAttributes<HTMLAnchorElement> & {
    as?: React.ElementType;
  };

const MagneticButton = React.forwardRef<HTMLElement, MagneticButtonProps>(
  ({ className, children, as: Component = "button", ...props }, forwardedRef) => {
    const localRef = useRef<HTMLElement>(null);

    useEffect(() => {
      if (typeof window === "undefined") return;
      const element = localRef.current;
      if (!element) return;

      const ctx = gsap.context(() => {
        const handleMouseMove = (e: MouseEvent) => {
          const rect = element.getBoundingClientRect();
          const h = rect.width / 2;
          const w = rect.height / 2;
          const x = e.clientX - rect.left - h;
          const y = e.clientY - rect.top - w;
          gsap.to(element, {
            x: x * 0.4,
            y: y * 0.4,
            rotationX: -y * 0.15,
            rotationY: x * 0.15,
            scale: 1.05,
            ease: "power2.out",
            duration: 0.4,
          });
        };
        const handleMouseLeave = () => {
          gsap.to(element, {
            x: 0,
            y: 0,
            rotationX: 0,
            rotationY: 0,
            scale: 1,
            ease: "elastic.out(1, 0.3)",
            duration: 1.2,
          });
        };
        element.addEventListener("mousemove", handleMouseMove as EventListener);
        element.addEventListener("mouseleave", handleMouseLeave);
        return () => {
          element.removeEventListener("mousemove", handleMouseMove as EventListener);
          element.removeEventListener("mouseleave", handleMouseLeave);
        };
      }, element);

      return () => ctx.revert();
    }, []);

    return (
      <Component
        ref={(node: HTMLElement) => {
          (localRef as React.MutableRefObject<HTMLElement | null>).current = node;
          if (typeof forwardedRef === "function") forwardedRef(node);
          else if (forwardedRef)
            (forwardedRef as React.MutableRefObject<HTMLElement | null>).current = node;
        }}
        className={cn("cursor-pointer", className)}
        {...props}
      >
        {children}
      </Component>
    );
  }
);
MagneticButton.displayName = "MagneticButton";

// -------------------------------------------------------------------------
// Marquee (value props Gridar)
// -------------------------------------------------------------------------
const MarqueeItem = () => (
  <div className="flex items-center space-x-12 px-6">
    <span>SEO en français</span> <span className="text-primary/60">✦</span>
    <span>Audit en 60 secondes</span> <span className="text-secondary/60">✦</span>
    <span>Visibilité IA</span> <span className="text-primary/60">✦</span>
    <span>Suivi des positions Google</span> <span className="text-secondary/60">✦</span>
    <span>Fait au Québec</span> <span className="text-primary/60">✦</span>
  </div>
);

// -------------------------------------------------------------------------
// Plan du site : liens sobres, pas de magnetisme. Une vingtaine d'elements
// magnetiques cote a cote, ce serait du bruit et vingt contextes GSAP pour
// rien.
// -------------------------------------------------------------------------
function ColonneLiens({
  titre,
  children,
}: {
  titre: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2">
      <span className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-foreground/70 md:text-xs">
        {titre}
      </span>
      {children}
    </div>
  );
}

function LienPied({
  href,
  externe,
  children,
}: {
  href: string;
  externe?: boolean;
  children: React.ReactNode;
}) {
  const classe =
    "text-xs text-muted-foreground transition-colors hover:text-foreground md:text-sm";
  // mailto: et les domaines externes ne passent pas par le routeur client.
  if (externe) {
    return (
      <a
        href={href}
        className={classe}
        {...(href.startsWith("http")
          ? { target: "_blank", rel: "noopener noreferrer" }
          : {})}
      >
        {children}
      </a>
    );
  }
  return (
    <Link href={href} className={classe}>
      {children}
    </Link>
  );
}

export function CinematicFooter() {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const giantTextRef = useRef<HTMLDivElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const linksRef = useRef<HTMLDivElement>(null);

  // Le rideau plein ecran exige que le pied tienne dans un ecran. Sur
  // telephone, le plan du site deploye le faisait deborder de 160px et la
  // barre du bas devenait inatteignable. Il part donc replie sous md, et le
  // visiteur l'ouvre s'il le veut. Les liens restent dans le DOM dans les deux
  // cas : un <details> ferme n'est pas un lien perdu pour l'indexation.
  // Ouvert au rendu serveur, ce qui donne le cas desktop et laisse le HTML
  // complet aux robots ; l'effet le replie ensuite sur les petits ecrans.
  const [planOuvert, setPlanOuvert] = React.useState(true);
  useEffect(() => {
    const mql = window.matchMedia("(width < 48rem)");
    const sync = () => setPlanOuvert(!mql.matches);
    sync();
    mql.addEventListener("change", sync);
    return () => mql.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!wrapperRef.current) return;

    const ctx = gsap.context(() => {
      gsap.fromTo(
        giantTextRef.current,
        { y: "10vh", scale: 0.8, opacity: 0 },
        {
          y: "0vh",
          scale: 1,
          opacity: 1,
          ease: "power1.out",
          scrollTrigger: {
            trigger: wrapperRef.current,
            start: "top 80%",
            end: "bottom bottom",
            scrub: 1,
          },
        }
      );
      gsap.fromTo(
        [headingRef.current, linksRef.current],
        { y: 50, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          stagger: 0.15,
          ease: "power3.out",
          scrollTrigger: {
            trigger: wrapperRef.current,
            start: "top 40%",
            end: "bottom bottom",
            scrub: 1,
          },
        }
      );
    }, wrapperRef);

    return () => ctx.revert();
  }, []);

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: STYLES }} />

      <div
        ref={wrapperRef}
        className="cinematic-footer-curtain relative h-screen w-full"
        style={{ clipPath: "polygon(0% 0, 100% 0%, 100% 100%, 0 100%)" }}
      >
        <footer className="cinematic-footer-wrapper fixed bottom-0 left-0 flex h-screen w-full flex-col justify-between overflow-hidden bg-background text-foreground">
          {/* Grille de fond */}
          <div className="footer-bg-grid pointer-events-none absolute inset-0 z-0" />

          {/* Giant background wordmark */}
          <div
            ref={giantTextRef}
            className="footer-giant-bg-text pointer-events-none absolute -bottom-[5vh] left-1/2 z-0 -translate-x-1/2 select-none whitespace-nowrap"
          >
            GRIDAR
          </div>

          {/* Diagonal marquee */}
          <div className="absolute left-0 top-12 z-10 w-full -rotate-2 scale-110 overflow-hidden border-y border-border/50 bg-background/60 py-4 shadow-2xl backdrop-blur-md">
            <div className="flex w-max animate-footer-scroll-marquee text-xs font-bold uppercase tracking-[0.3em] text-muted-foreground md:text-sm">
              <MarqueeItem />
              <MarqueeItem />
            </div>
          </div>

          {/* Center content. min-h-0 + overflow-y-auto : le pied est un element
              fixed de la hauteur d'un ecran, il ne peut pas grandir. Si le
              visiteur deplie le plan du site sur telephone, le surplus se
              scrolle ici au lieu de passer sous la barre du bas. */}
          <div className="relative z-10 mx-auto mt-16 flex w-full min-h-0 max-w-5xl flex-1 flex-col items-center justify-center overflow-y-auto px-6 md:mt-20">
            <h2
              ref={headingRef}
              className="footer-text-glow mb-8 text-center text-4xl font-black tracking-tighter sm:text-5xl md:mb-12 md:text-8xl"
            >
              Prêt à ranker au Québec?
            </h2>

            <div ref={linksRef} className="flex w-full flex-col items-center gap-4 md:gap-6">
              {/* CTA primaires */}
              <div className="flex w-full flex-wrap justify-center gap-4">
                <MagneticButton
                  as="a"
                  href="/audit"
                  className="footer-glass-pill group flex items-center gap-3 rounded-full px-6 py-3.5 text-sm font-bold text-foreground md:px-10 md:py-5 md:text-base"
                >
                  <Search className="h-5 w-5 text-muted-foreground transition-colors group-hover:text-foreground" />
                  Auditer mon site
                </MagneticButton>

                <MagneticButton
                  as="a"
                  href="/tools"
                  className="footer-glass-pill group flex items-center gap-3 rounded-full px-6 py-3.5 text-sm font-bold text-foreground md:px-10 md:py-5 md:text-base"
                >
                  Tous les outils
                  <ArrowUpRight className="h-5 w-5 text-muted-foreground transition-colors group-hover:text-foreground" />
                </MagneticButton>
              </div>

              {/* Plan du site. Discret par rapport aux pastilles, mais present :
                  c'est le seul chemin interne vers les 8 pages d'outils depuis
                  le bas de page, et un footer cinematique ne doit pas couter
                  son maillage au site. */}
              <details
                open={planOuvert}
                onToggle={(e) => setPlanOuvert(e.currentTarget.open)}
                className="mt-4 w-full max-w-3xl md:mt-10"
              >
                <summary className="footer-plan-resume mx-auto flex w-fit cursor-pointer items-center gap-2 rounded-full px-4 py-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400/70 md:hidden">
                  Plan du site
                  <ChevronDown
                    aria-hidden="true"
                    className="footer-plan-chevron h-3.5 w-3.5 transition-transform duration-200"
                  />
                </summary>
                <nav
                  aria-label="Plan du site"
                  className="mt-4 grid w-full grid-cols-2 gap-x-8 gap-y-6 text-left sm:grid-cols-3 md:mt-0 md:gap-y-8"
                >
                <ColonneLiens titre="Outils gratuits">
                  {NAV_TOOLS.map((outil) => (
                    <LienPied key={outil.href} href={outil.href}>
                      {outil.label}
                    </LienPied>
                  ))}
                </ColonneLiens>

                <ColonneLiens titre="Ressources">
                  <LienPied href="/tools">Tous les outils</LienPied>
                  <LienPied href="/blog">Blogue</LienPied>
                  <LienPied href="/docs">Documentation</LienPied>
                  <LienPied href="/api-docs">API REST</LienPied>
                  <LienPied href="/docs/integrations">Intégrations</LienPied>
                </ColonneLiens>

                <ColonneLiens titre="Gridar">
                  <LienPied href="/#pricing">Tarifs</LienPied>
                  <LienPied href="/audit">Auditer mon site</LienPied>
                  <LienPied href="/login">Créer un compte</LienPied>
                  <LienPied href="mailto:tokamdarius@gmail.com" externe>
                    Contact
                  </LienPied>
                  <LienPied href="https://github.com/TokDar2410621/blog-dashboard" externe>
                    GitHub
                  </LienPied>
                </ColonneLiens>
                </nav>
              </details>
            </div>
          </div>

          {/* Bottom bar */}
          <div className="relative z-20 flex w-full flex-col items-center justify-between gap-3 px-6 pb-6 md:flex-row md:gap-6 md:px-12 md:pb-8">
            <div className="order-2 flex flex-col items-center gap-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground md:order-1 md:items-start md:text-xs">
              {/* Annee calculee : un millesime en dur finit toujours par mentir. */}
              <span>© {new Date().getFullYear()} Gridar - Arivex Studio</span>
              <span className="normal-case tracking-normal">Fait à Saint-Hyacinthe, QC.</span>
            </div>

            <div className="order-1 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground md:order-2 md:text-xs">
              <Link href="/privacy" className="transition-colors hover:text-foreground">
                Confidentialité
              </Link>
              <Link href="/terms" className="transition-colors hover:text-foreground">
                Conditions
              </Link>
            </div>

            <MagneticButton
              as="button"
              onClick={scrollToTop}
              aria-label="Retour en haut"
              className="footer-glass-pill group order-3 flex h-12 w-12 items-center justify-center rounded-full text-muted-foreground hover:text-foreground"
            >
              <svg className="h-5 w-5 transform transition-transform duration-300 group-hover:-translate-y-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 10l7-7m0 0l7 7m-7-7v18" />
              </svg>
            </MagneticButton>
          </div>
        </footer>
      </div>
    </>
  );
}

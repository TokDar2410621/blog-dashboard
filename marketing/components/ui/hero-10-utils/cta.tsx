import Link from 'next/link'

import { Button } from '@/components/ui/button'

/** Un bouton du hero. `link` vide rend un bouton inerte, ce qui laisse poser
 *  un CTA avant d'avoir decide ou il mene. Un lien interne passe par
 *  next/link pour garder la navigation client. */
export interface CtaProps {
  ctaEnabled?: boolean
  text: string
  link?: string
  variant?: React.ComponentProps<typeof Button>['variant']
  size?: React.ComponentProps<typeof Button>['size']
  external?: boolean
}

export function Cta({ cta }: Readonly<{ cta: CtaProps }>) {
  const { text, link, variant = 'default', size = 'default', external } = cta

  if (!link) {
    return (
      <Button variant={variant} size={size}>
        {text}
      </Button>
    )
  }

  // Une ancre ou une URL absolue sort de next/link.
  const estExterne = external ?? (/^https?:\/\//.test(link) || link.startsWith('#'))

  return (
    <Button asChild variant={variant} size={size}>
      {estExterne ? <a href={link}>{text}</a> : <Link href={link}>{text}</Link>}
    </Button>
  )
}

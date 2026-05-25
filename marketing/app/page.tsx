import Link from "next/link";
import { GridarMark } from "@/components/GridarMark";

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-6 p-12">
      <div className="flex items-center gap-3">
        <GridarMark className="h-10 w-10" />
        <h1 className="text-3xl font-bold">Gridar marketing site</h1>
      </div>
      <p className="text-muted-foreground text-center max-w-md">
        Bootstrap Next.js OK. La vraie landing arrive a la Phase 3. En attendant tu peux tester :
      </p>
      <ul className="flex gap-6 text-primary underline">
        <li><Link href="/privacy">/privacy</Link></li>
        <li><Link href="/terms">/terms</Link></li>
      </ul>
    </main>
  );
}

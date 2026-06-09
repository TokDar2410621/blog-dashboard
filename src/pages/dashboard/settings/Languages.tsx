import { Languages as LanguagesIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { useSettings } from "./useSettings";

export default function Languages() {
  const {
    availableLanguages, toggleLanguage,
    defaultLanguage, setDefaultLanguage,
  } = useSettings();

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <LanguagesIcon className="h-5 w-5" />
            Langues disponibles
          </CardTitle>
          <CardDescription>
            Sélectionnez les langues acceptées par le backend de ce site. Si rien n'est coché, toutes les langues sont autorisées (fr/en/es).
          </CardDescription>
        </CardHeader>
        <CardContent className="flex gap-3 flex-wrap">
          {[
            { code: "fr", label: "Français" },
            { code: "en", label: "English" },
            { code: "es", label: "Español" },
          ].map((l) => {
            const active = availableLanguages.includes(l.code);
            return (
              <Button
                key={l.code}
                type="button"
                variant={active ? "default" : "outline"}
                size="sm"
                onClick={() => toggleLanguage(l.code)}
              >
                {l.label}
              </Button>
            );
          })}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <LanguagesIcon className="h-5 w-5" />
            Langue par défaut
          </CardTitle>
          <CardDescription>
            Présélectionnée dans l'éditeur et la génération IA.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <Label className="text-sm">Langue principale</Label>
          <select
            value={defaultLanguage}
            onChange={(e) => setDefaultLanguage(e.target.value)}
            className="flex h-9 w-full max-w-xs rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
          >
            <option value="fr">Français</option>
            <option value="en">English</option>
            <option value="es">Español</option>
          </select>
        </CardContent>
      </Card>
    </div>
  );
}

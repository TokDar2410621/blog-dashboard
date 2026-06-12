"use client";

import { Award, ImageIcon, Linkedin, Twitter, Globe, User as UserIcon, Languages } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useSettings } from "./useSettings";

export default function Author() {
  const {
    defaultAuthor, setDefaultAuthor,
    defaultLanguage, setDefaultLanguage,
    authorRole, setAuthorRole,
    authorBio, setAuthorBio,
    authorCredentials, setAuthorCredentials,
    authorImageUrl, setAuthorImageUrl,
    authorLinkedin, setAuthorLinkedin,
    authorTwitter, setAuthorTwitter,
    authorWebsite, setAuthorWebsite,
  } = useSettings();

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <UserIcon className="h-5 w-5" />
            Auteur et langue par défaut
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="flex items-center gap-1.5 text-sm">
                <UserIcon className="h-3.5 w-3.5" />
                Auteur par défaut
              </Label>
              <Input
                value={defaultAuthor}
                onChange={(e) => setDefaultAuthor(e.target.value)}
                placeholder="Admin"
              />
              <p className="text-xs text-muted-foreground">
                Nom attribué aux articles générés par l'IA et utilisé dans le Schema.org
              </p>
            </div>

            <div className="space-y-2">
              <Label className="flex items-center gap-1.5 text-sm">
                <Languages className="h-3.5 w-3.5" />
                Langue par défaut
              </Label>
              <select
                value={defaultLanguage}
                onChange={(e) => setDefaultLanguage(e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
              >
                <option value="fr">Français</option>
                <option value="en">English</option>
                <option value="es">Español</option>
              </select>
              <p className="text-xs text-muted-foreground">
                Présélectionnée dans l'éditeur et la génération IA
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Award className="h-5 w-5" />
            Profil auteur (E-E-A-T)
          </CardTitle>
          <CardDescription>
            Renseigne ces champs pour booster les signaux Experience, Expertise, Authority, Trust de Google. Utilisé en JSON-LD <code className="text-xs">Person</code> sur les articles.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="text-sm">Rôle / titre</Label>
              <Input
                value={authorRole}
                onChange={(e) => setAuthorRole(e.target.value)}
                placeholder="Ex: Fondateur, Consultant SEO, Avocat fiscaliste"
              />
              <p className="text-xs text-muted-foreground">
                JSON-LD <code>jobTitle</code>. Aide Google à classer ton expertise.
              </p>
            </div>
            <div className="space-y-2">
              <Label className="text-sm flex items-center gap-1.5">
                <ImageIcon className="h-3.5 w-3.5" />
                Photo (URL)
              </Label>
              <div className="flex gap-2">
                <Input
                  value={authorImageUrl}
                  onChange={(e) => setAuthorImageUrl(e.target.value)}
                  placeholder="https://..."
                  type="url"
                  className="flex-1"
                />
                {authorImageUrl && (
                  <img
                    src={authorImageUrl}
                    alt="Author preview"
                    className="h-10 w-10 rounded-full object-cover border"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = "none";
                    }}
                  />
                )}
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <Label className="text-sm">Bio (2-4 phrases)</Label>
            <Textarea
              value={authorBio}
              onChange={(e) => setAuthorBio(e.target.value)}
              placeholder="Ex: Fondateur de Gridar, j'aide les PME québécoises à atteindre la première page de Google. 10 ans d'expérience SEO."
              rows={3}
              className="resize-y"
            />
            <p className="text-xs text-muted-foreground">
              {authorBio.length} caractères - vise une bio concise qui établit ton expérience pratique.
            </p>
          </div>

          <div className="space-y-2">
            <Label className="text-sm">Credentials / qualifications</Label>
            <Textarea
              value={authorCredentials}
              onChange={(e) => setAuthorCredentials(e.target.value)}
              placeholder="Ex: MBA HEC Montréal, certifié Google Analytics, ancien consultant chez Shopify..."
              rows={2}
              className="resize-y"
            />
            <p className="text-xs text-muted-foreground">
              JSON-LD <code>hasCredential</code>. Diplômes, certifications, expériences pertinentes.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="space-y-1">
              <Label className="text-xs flex items-center gap-1.5">
                <Linkedin className="h-3.5 w-3.5" />
                LinkedIn
              </Label>
              <Input
                value={authorLinkedin}
                onChange={(e) => setAuthorLinkedin(e.target.value)}
                placeholder="https://linkedin.com/in/..."
                type="url"
                className="h-9 text-sm"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs flex items-center gap-1.5">
                <Twitter className="h-3.5 w-3.5" />
                Twitter / X
              </Label>
              <Input
                value={authorTwitter}
                onChange={(e) => setAuthorTwitter(e.target.value)}
                placeholder="https://x.com/..."
                type="url"
                className="h-9 text-sm"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs flex items-center gap-1.5">
                <Globe className="h-3.5 w-3.5" />
                Site personnel
              </Label>
              <Input
                value={authorWebsite}
                onChange={(e) => setAuthorWebsite(e.target.value)}
                placeholder="https://..."
                type="url"
                className="h-9 text-sm"
              />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Ces 3 URLs alimentent <code>sameAs</code> dans le JSON-LD Person - Google les utilise pour vérifier ton identité.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

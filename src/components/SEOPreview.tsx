import { useTranslation } from "react-i18next";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface SEOPreviewProps {
  title: string;
  slug: string;
  description: string;
  coverImage?: string;
  siteUrl?: string;
}

export function SEOPreview({
  title,
  slug,
  description,
  coverImage,
  siteUrl = "monsite.com",
}: SEOPreviewProps) {
  const { t } = useTranslation();
  const url = `${siteUrl}/blog/${slug}`;
  const truncTitle = title.length > 60 ? title.slice(0, 57) + "..." : title;
  const truncDesc =
    description.length > 160 ? description.slice(0, 157) + "..." : description;

  return (
    <Tabs defaultValue="google">
      <TabsList className="w-full">
        <TabsTrigger value="google" className="flex-1">
          Google
        </TabsTrigger>
        <TabsTrigger value="facebook" className="flex-1">
          Facebook
        </TabsTrigger>
        <TabsTrigger value="twitter" className="flex-1">
          Twitter
        </TabsTrigger>
      </TabsList>

      {/* Google Preview */}
      <TabsContent value="google">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t("seo.googlePreview")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <p className="text-xs text-green-600 dark:text-green-400">
              {url}
            </p>
            <p className="text-blue-600 dark:text-blue-400 text-base font-medium hover:underline cursor-pointer">
              {truncTitle || t("seo.titleDefault")}
            </p>
            <p className="text-sm text-muted-foreground">
              {truncDesc || t("seo.descDefault")}
            </p>
            <div className="flex gap-4 text-xs text-muted-foreground mt-2">
              <span>
                {t("seo.titleLabel")}: {title.length}/60{" "}
                {title.length > 60 && (
                  <span className="text-destructive">{t("seo.tooLong")}</span>
                )}
              </span>
              <span>
                {t("seo.descLabel")}: {description.length}/160{" "}
                {description.length > 160 && (
                  <span className="text-destructive">{t("seo.tooLong")}</span>
                )}
              </span>
            </div>
          </CardContent>
        </Card>
      </TabsContent>

      {/* Facebook Preview */}
      <TabsContent value="facebook">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t("seo.facebookPreview")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="border rounded-md overflow-hidden">
              {coverImage ? (
                <img
                  src={coverImage}
                  alt="OG"
                  className="w-full h-48 object-cover"
                />
              ) : (
                <div className="w-full h-48 bg-muted flex items-center justify-center text-muted-foreground text-sm">
                  {t("seo.noImage")}
                </div>
              )}
              <div className="p-3 bg-muted/50">
                <p className="text-xs text-muted-foreground uppercase">
                  {siteUrl}
                </p>
                <p className="font-semibold text-sm mt-1">
                  {title || t("seo.titleDefault")}
                </p>
                <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                  {description || t("seo.descDefault")}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </TabsContent>

      {/* Twitter Preview */}
      <TabsContent value="twitter">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t("seo.twitterPreview")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="border rounded-xl overflow-hidden">
              {coverImage ? (
                <img
                  src={coverImage}
                  alt="Twitter card"
                  className="w-full h-48 object-cover"
                />
              ) : (
                <div className="w-full h-48 bg-muted flex items-center justify-center text-muted-foreground text-sm">
                  {t("seo.noImage")}
                </div>
              )}
              <div className="p-3">
                <p className="font-semibold text-sm">
                  {title || t("seo.titleDefault")}
                </p>
                <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                  {description || t("seo.descDefault")}
                </p>
                <p className="text-xs text-muted-foreground mt-1">{siteUrl}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>
  );
}

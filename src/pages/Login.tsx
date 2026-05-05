import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { login } from "@/lib/api-client";
import { setTokens, getToken } from "@/lib/sites";
import { useAuth } from "@/hooks/useAuth";
import { getApiErrorMessage } from "@/lib/api-errors";
import { Loader2, Newspaper } from "lucide-react";
import { toast } from "sonner";
import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

export default function Login() {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const { user, isLoading, checkAuth } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  if (!isLoading && user) {
    return <Navigate to="/sites" replace />;
  }

  if (isLoading && getToken()) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const tokens = await login(username, password);
      setTokens(tokens.access);
      await checkAuth();
      toast.success(t("login.success"));
      navigate("/sites");
    } catch (e) {
      toast.error(getApiErrorMessage(e, t));
    } finally {
      setLoading(false);
    }
  };

  const toggleLang = () => {
    i18n.changeLanguage(i18n.language === "fr" ? "en" : "fr");
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="flex items-center justify-center gap-2 mb-2">
            <Newspaper className="h-7 w-7 text-primary" />
            <CardTitle className="text-2xl">{t("login.title")}</CardTitle>
          </div>
          <p className="text-sm text-muted-foreground">
            {t("login.subtitle")}
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">{t("login.username")}</Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">{t("login.password")}</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {t("login.loading")}
                </>
              ) : (
                t("login.submit")
              )}
            </Button>
          </form>
          <div className="mt-4 text-center">
            <Button variant="ghost" size="sm" onClick={toggleLang}>
              {i18n.language === "fr" ? "EN" : "FR"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

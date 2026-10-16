// Adapted from Laravel's React starter kit (github.com/laravel/react-starter-kit), MIT. See
// LICENSES/laravel-react-starter-kit.md. Per T-07 "The JavaScript entry point": the `error` page
// also renders without the app chrome (it is shown to guests and authenticated users alike), and
// `settings/` pages get the nested [AppLayout, SettingsLayout] array (T-25).
import { createInertiaApp } from "@inertiajs/react";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { initializeTheme } from "@/hooks/use-appearance";
import AppLayout from "@/layouts/app-layout";
import AuthLayout from "@/layouts/auth-layout";
import SettingsLayout from "@/layouts/settings/layout";

const appName = import.meta.env.VITE_APP_NAME || "Aso";

void createInertiaApp({
    title: (title) => (title ? `${title} - ${appName}` : appName),
    layout: (name) => {
        if (name === "welcome" || name === "error") return null;
        if (name.startsWith("auth/")) return AuthLayout;
        if (name.startsWith("settings/")) return [AppLayout, SettingsLayout];
        return AppLayout;
    },
    strictMode: true,
    withApp(app) {
        return (
            <TooltipProvider delayDuration={0}>
                {app}
                <Toaster />
            </TooltipProvider>
        );
    },
    progress: {
        color: "#4B5563",
    },
});

// Sets light/dark mode on load (T-07's anti-flash-of-wrong-theme script in app.html handles the
// very first paint; this keeps `localStorage`/the cookie and later navigations in sync).
initializeTheme();

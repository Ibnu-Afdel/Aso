// Adapted from Laravel's React starter kit (github.com/laravel/react-starter-kit), MIT, and
// docs/guide/T-07-vite.md. Drops the kit's `vite-plus`/Wayfinder-plugin/React-Compiler/Bunny-font
// tooling (D-017, T-05 open question 3): Aso stays on plain Vite 8 and generates routes
// with its own `aso routes:generate` (T-28) instead of a Vite plugin.
import inertia from "@inertiajs/vite";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import aso from "./vite/aso.ts";

export default defineConfig({
    plugins: [
        aso({
            input: ["resources/css/app.css", "resources/js/app.tsx"],
            refresh: ["routes/**", "resources/views/**", "app/**/*.py"],
        }),
        inertia(),
        react(),
        tailwindcss(),
    ],
    resolve: {
        alias: { "@": "/resources/js" },
    },
    server: {
        watch: {
            ignored: ["**/.venv/**", "**/storage/**", "**/.claude/**", "**/.cursor/**"],
        },
    },
});

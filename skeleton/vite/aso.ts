// Aso's Vite plugin (T-07). It connects Vite to the Python side the way
// `aso.inertia.vite` expects:
//
// - `vite dev` writes the dev-server URL to `public/hot` (and removes it on exit), so the
//   `vite()` template helper emits dev-server tags instead of manifest tags.
// - `vite build` writes hashed assets and `manifest.json` to `public/build/`.
// - A change to a Python route/controller or a template triggers a full page reload.
// - Opening the Vite URL directly shows a pointer to the app URL instead of a blank 404.
import fs from "node:fs";
import path from "node:path";
import { loadEnv, type Plugin, type ResolvedConfig, type ViteDevServer } from "vite";

export interface AsoOptions {
    /** Entry points, e.g. ["resources/css/app.css", "resources/js/app.tsx"]. */
    input: string | string[];
    /** Globs that trigger a full page reload when they change. */
    refresh?: string[];
    /** Defaults to "public". */
    publicDirectory?: string;
    /** Defaults to "build" (inside `publicDirectory`). */
    buildDirectory?: string;
}

export default function aso(options: AsoOptions): Plugin {
    const publicDirectory = options.publicDirectory ?? "public";
    const buildDirectory = options.buildDirectory ?? "build";
    const hotFile = path.join(publicDirectory, "hot");
    let resolved: ResolvedConfig;
    let exitHandlersBound = false;

    return {
        name: "aso",
        enforce: "post",

        config(userConfig, { command, mode }) {
            const env = loadEnv(mode, userConfig.envDir || process.cwd(), "");
            const port = userConfig.server?.port ?? 5173;
            const origin = userConfig.server?.origin ?? `http://localhost:${port}`;
            return {
                base: userConfig.base ?? (command === "build" ? `/${buildDirectory}/` : ""),
                publicDir: userConfig.publicDir ?? false,
                build: {
                    manifest: userConfig.build?.manifest ?? "manifest.json",
                    outDir: userConfig.build?.outDir ?? path.join(publicDirectory, buildDirectory),
                    rolldownOptions: { input: userConfig.build?.rolldownOptions?.input ?? options.input },
                    assetsInlineLimit: userConfig.build?.assetsInlineLimit ?? 0,
                },
                server: {
                    port,
                    // `aso dev` picks a free port and passes it in; never drift from it,
                    // or `public/hot` and the CORS origin would point at the wrong place.
                    strictPort: userConfig.server?.strictPort ?? true,
                    origin,
                    cors: userConfig.server?.cors ?? {
                        origin: [
                            /^https?:\/\/(?:(?:[^:]+\.)?localhost|127\.0\.0\.1|\[::1\])(?::\d+)?$/,
                            ...(env.APP_URL ? [new URL(env.APP_URL).origin] : []),
                        ],
                    },
                },
            };
        },

        configResolved(config) {
            resolved = config;
        },

        configureServer(server: ViteDevServer) {
            const appUrl = process.env.APP_URL || loadEnv(resolved.mode, resolved.envDir || process.cwd(), "").APP_URL || "http://127.0.0.1:8000";

            server.httpServer?.once("listening", () => {
                fs.mkdirSync(path.dirname(hotFile), { recursive: true });
                fs.writeFileSync(hotFile, resolved.server.origin ?? `http://localhost:${resolved.server.port}`);
                setTimeout(() => {
                    server.config.logger.info(`\n  ${color("1;36", "Aso")}  this server only serves assets (URL written to ${hotFile})`);
                    server.config.logger.info(`  ${color("32", "➜")}  Open the app at: ${color("36", appUrl)}\n`);
                }, 100);
            });

            if (!exitHandlersBound) {
                const clean = () => fs.existsSync(hotFile) && fs.rmSync(hotFile);
                process.on("exit", clean);
                for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"] as const) {
                    process.on(signal, () => process.exit());
                }
                exitHandlersBound = true;
            }

            const refresh = options.refresh ?? [];
            if (refresh.length) {
                server.watcher.add(refresh);
                let timer: ReturnType<typeof setTimeout> | undefined;
                const matchers = refresh.map(globToRegExp);
                const reload = (file: string) => {
                    const relative = path.relative(resolved.root, file).split(path.sep).join("/");
                    if (!matchers.some((re) => re.test(relative))) return;
                    // Give uvicorn's reloader a moment to restart before the browser asks again.
                    clearTimeout(timer);
                    timer = setTimeout(() => server.ws.send({ type: "full-reload", path: "*" }), 400);
                };
                server.watcher.on("change", reload);
                server.watcher.on("add", reload);
            }

            server.middlewares.use((req, res, next) => {
                if (req.url !== "/" && req.url !== "/index.html") return next();
                res.statusCode = 200;
                res.setHeader("Content-Type", "text/html; charset=utf-8");
                res.end(
                    `<!doctype html><meta charset="utf-8"><title>Aso · Vite</title>` +
                        `<body style="font-family:system-ui,sans-serif;display:grid;place-items:center;min-height:100vh;margin:0;background:#0b1020;color:#e2e8f0">` +
                        `<div style="text-align:center;max-width:32rem;padding:1rem"><p style="opacity:.7">This is the Vite dev server. It only serves assets.</p>` +
                        `<p>Your app is at <a style="color:#38bdf8" href="${appUrl}">${appUrl}</a></p></div></body>`,
                );
            });
        },
    };
}

/** ANSI colour only on a real terminal (piped through `aso dev`, Vite drops colour too). */
function color(code: string, text: string): string {
    return process.stdout.isTTY ? `\x1b[${code}m${text}\x1b[0m` : text;
}

/** `**` matches across folders, `*` within one folder segment. */
function globToRegExp(glob: string): RegExp {
    const source = glob
        .split("**")
        .map((part) => part.replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, "[^/]*").replace(/\?/g, "[^/]"))
        .join(".*");
    return new RegExp(`^${source}$`);
}

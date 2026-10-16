// The Aso welcome page. Replace it with your own landing page; it is served by
// `Route.inertia("/", "welcome")` in routes/web.py.
import { Head, Link, usePage } from '@inertiajs/react';
import { ArrowUpRight, FileCode2, Route as RouteIcon, Terminal } from 'lucide-react';
import AppLogoIcon from '@/components/app-logo-icon';
import { dashboard, login, register } from '@/routes';

const steps = [
    {
        icon: RouteIcon,
        title: 'Add a route',
        file: 'routes/web.py',
        body: 'Map URLs to controllers or straight to a page.',
    },
    {
        icon: FileCode2,
        title: 'Build a page',
        file: 'resources/js/pages/',
        body: 'React components, rendered with Inertia. No API to write.',
    },
    {
        icon: Terminal,
        title: 'Use the CLI',
        file: 'uv run aso list',
        body: 'Generators, migrations, queues, and more.',
    },
];

export default function Welcome() {
    const { auth, name } = usePage().props;

    const linkClass =
        'rounded-md px-4 py-1.5 text-sm font-medium text-neutral-700 transition hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800';

    return (
        <>
            <Head title="Welcome" />
            <div className="relative flex min-h-screen flex-col overflow-hidden bg-white text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100">
                <div
                    aria-hidden
                    className="pointer-events-none absolute inset-x-0 -top-40 mx-auto h-96 max-w-3xl rounded-full bg-gradient-to-r from-sky-400/30 to-indigo-500/30 blur-3xl dark:from-sky-500/20 dark:to-indigo-500/20"
                />

                <header className="relative mx-auto flex w-full max-w-5xl items-center justify-between p-6">
                    <div className="flex items-center gap-2 font-semibold">
                        <AppLogoIcon className="size-6 fill-current text-sky-500" />
                        <span>{name}</span>
                    </div>
                    <nav className="flex items-center gap-2">
                        {auth.user ? (
                            <Link href={dashboard()} className={linkClass}>
                                Dashboard
                            </Link>
                        ) : (
                            <>
                                <Link href={login()} className={linkClass}>
                                    Log in
                                </Link>
                                <Link
                                    href={register()}
                                    className="rounded-md bg-neutral-900 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-neutral-700 dark:bg-white dark:text-neutral-900 dark:hover:bg-neutral-200"
                                >
                                    Register
                                </Link>
                            </>
                        )}
                    </nav>
                </header>

                <main className="relative mx-auto flex w-full max-w-5xl flex-1 flex-col items-center justify-center px-6 pb-16 text-center">
                    <div className="mb-8 flex size-20 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500 to-indigo-500 shadow-lg shadow-indigo-500/25">
                        <AppLogoIcon className="size-11 fill-current text-white" />
                    </div>
                    <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
                        <span className="bg-gradient-to-r from-sky-500 to-indigo-500 bg-clip-text text-transparent">Aso</span>
                    </h1>
                    <p className="mt-4 max-w-xl text-lg text-neutral-600 dark:text-neutral-400">
                        The batteries-included Python web framework. FastAPI on the server, React on the client, Inertia in between.
                    </p>
                    <p className="mt-6 rounded-md border border-neutral-200 bg-neutral-50 px-3 py-1.5 font-mono text-sm text-neutral-600 dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-400">
                        Edit <span className="text-neutral-900 dark:text-neutral-100">resources/js/pages/welcome.tsx</span> to change this page
                    </p>

                    <div className="mt-14 grid w-full gap-4 text-left sm:grid-cols-3">
                        {steps.map(({ icon: Icon, title, file, body }) => (
                            <div
                                key={title}
                                className="rounded-xl border border-neutral-200 bg-white/60 p-5 backdrop-blur dark:border-neutral-800 dark:bg-neutral-900/60"
                            >
                                <Icon className="size-5 text-sky-500" />
                                <h2 className="mt-3 font-semibold">{title}</h2>
                                <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">{body}</p>
                                <code className="mt-3 block truncate font-mono text-xs text-neutral-500">{file}</code>
                            </div>
                        ))}
                    </div>

                    <a
                        href="https://github.com/Ibnu-Afdel/FastGram"
                        target="_blank"
                        rel="noreferrer"
                        className="mt-10 inline-flex items-center gap-1 text-sm font-medium text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-100"
                    >
                        Read the docs on GitHub <ArrowUpRight className="size-4" />
                    </a>
                </main>
            </div>
        </>
    );
}

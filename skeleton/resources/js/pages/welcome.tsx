// The Aso welcome page. Replace it with your own landing page; it is served by
// `Route.inertia("/", "welcome")` in routes/web.py.
import { Head, Link, usePage } from '@inertiajs/react';
import { ArrowUpRight } from 'lucide-react';
import AppLogoIcon from '@/components/app-logo-icon';
import AsoWordmark from '@/components/aso-wordmark';
import { dashboard, login, register } from '@/routes';

const steps = [
    {
        title: 'Add a route',
        file: 'routes/web.py',
        body: 'Map URLs to controllers or straight to a page.',
    },
    {
        title: 'Build a page',
        file: 'resources/js/pages/',
        body: 'React components, rendered with Inertia. No API to write.',
    },
    {
        title: 'Use the CLI',
        file: 'uv run aso list',
        body: 'Generators, migrations, queues, and more.',
    },
];

export default function Welcome() {
    const { auth, name } = usePage().props;

    const linkClass =
        'rounded-full px-4 py-1.5 text-sm font-medium text-[#213231]/75 transition hover:text-[#213231] dark:text-[#ece6da]/70 dark:hover:text-[#ece6da]';

    return (
        <>
            <Head title="Welcome" />
            <div className="flex min-h-screen flex-col bg-[#f6f1e8] text-[#213231] dark:bg-[#121917] dark:text-[#ece6da]">
                <header className="mx-auto flex w-full max-w-5xl items-center justify-between p-6">
                    <div className="flex items-center gap-2.5 font-medium">
                        <AppLogoIcon className="size-6 fill-current text-[#213231] dark:text-[#ece6da]" />
                        <span>{name}</span>
                    </div>
                    <nav className="flex items-center gap-1">
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
                                    className="rounded-full bg-[#213231] px-4 py-1.5 text-sm font-medium text-[#f6f1e8] transition hover:bg-[#2e4441] dark:bg-[#ece6da] dark:text-[#121917] dark:hover:bg-white"
                                >
                                    Register
                                </Link>
                            </>
                        )}
                    </nav>
                </header>

                <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col items-center justify-center px-6 pt-8 pb-20 text-center">
                    <AppLogoIcon className="size-20 fill-current text-[#213231] dark:text-[#ece6da]" />
                    <h1 className="mt-9">
                        <span className="sr-only">aso</span>
                        <AsoWordmark aria-hidden className="h-12 w-auto fill-current sm:h-14" />
                    </h1>
                    <p className="mt-5 max-w-lg text-lg leading-relaxed text-[#213231]/70 dark:text-[#ece6da]/65">
                        The batteries-included Python web framework. FastAPI on the server, React on the client, Inertia in between.
                    </p>
                    <p className="mt-8 inline-flex flex-wrap items-center justify-center gap-x-2.5 gap-y-1 font-mono text-sm text-[#213231]/60 dark:text-[#ece6da]/55">
                        <span className="size-1.5 rounded-full bg-[#6d8b71]" />
                        Edit <span className="text-[#213231] dark:text-[#ece6da]">resources/js/pages/welcome.tsx</span> to change this page
                    </p>

                    <div className="mt-20 grid w-full gap-10 text-left sm:grid-cols-3 sm:gap-8">
                        {steps.map(({ title, file, body }, index) => (
                            <div key={title} className="border-t border-[#213231]/15 pt-5 dark:border-[#ece6da]/15">
                                <span className="font-mono text-xs text-[#6d8b71] dark:text-[#8fae93]">0{index + 1}</span>
                                <h2 className="mt-2 font-medium">{title}</h2>
                                <p className="mt-1 text-sm leading-relaxed text-[#213231]/65 dark:text-[#ece6da]/60">{body}</p>
                                <code className="mt-3 block truncate font-mono text-xs text-[#213231]/50 dark:text-[#ece6da]/45">{file}</code>
                            </div>
                        ))}
                    </div>

                    <a
                        href="https://github.com/Ibnu-Afdel/Aso"
                        target="_blank"
                        rel="noreferrer"
                        className="mt-16 inline-flex items-center gap-1 text-sm font-medium text-[#213231]/70 underline-offset-4 hover:text-[#213231] hover:underline dark:text-[#ece6da]/65 dark:hover:text-[#ece6da]"
                    >
                        Read the docs on GitHub <ArrowUpRight className="size-4" />
                    </a>
                </main>
            </div>
        </>
    );
}

// FastoGram addition (no equivalent page in Laravel's React starter kit): renders whatever
// `fastogram.exceptions` passes to `inertia_error_page` (T-20) -- `status` and an optional
// `message`. Not wrapped in AppLayout/AuthLayout (see app.tsx): an error page must render for
// guests and signed-in users alike.
import { Head, Link } from "@inertiajs/react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { home } from "@/routes";

const TITLES: Record<number, string> = {
    403: "Forbidden",
    404: "Page not found",
    419: "Page expired",
    429: "Too many requests",
    500: "Server error",
    503: "Service unavailable",
};

type Props = {
    status: number;
    message?: string;
};

export default function ErrorPage({ status, message }: Props) {
    const title = TITLES[status] ?? "Something went wrong";

    return (
        <>
            <Head title={title} />
            <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-background p-6 text-center">
                <AlertTriangle className="size-10 text-muted-foreground" />
                <div className="space-y-2">
                    <h1 className="text-3xl font-semibold tracking-tight">
                        {status} — {title}
                    </h1>
                    {message && (
                        <p className="text-muted-foreground">{message}</p>
                    )}
                </div>
                <Button asChild>
                    <Link href={home()}>Go back home</Link>
                </Button>
            </div>
        </>
    );
}

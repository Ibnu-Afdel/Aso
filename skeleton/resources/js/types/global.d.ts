// Ported from Laravel's React starter kit (github.com/laravel/react-starter-kit), MIT. See
// LICENSES/laravel-react-starter-kit.md. The `sharedPageProps` shape mirrors
// `app/http/middleware/handle_inertia_requests.py`'s `share()` (T-17) and
// `app/http/middleware/handle_appearance.py`'s `appearance` prop (T-05); keep them in sync.
// `flashDataType`/`errorValueType` follow T-17's TypeScript section.
import type { Auth } from "@/types/auth";

declare module "react" {
    interface InputHTMLAttributes<T> {
        passwordrules?: string;
    }
}

declare module "@inertiajs/core" {
    export interface InertiaConfig {
        sharedPageProps: {
            name: string;
            auth: Auth;
            sidebarOpen: boolean;
            appearance: "light" | "dark" | "system";
            [key: string]: unknown;
        };
        flashDataType: {
            status?: string;
            success?: string;
            error?: string;
        };
        errorValueType: string;
    }
}

export {};

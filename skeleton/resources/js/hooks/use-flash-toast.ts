// Adapted from Laravel's React starter kit (github.com/laravel/react-starter-kit), MIT. See
// LICENSES/laravel-react-starter-kit.md. FastoGram's backend flashes plain string values under
// `success`/`error` (D-024, T-05 "How it works"), not the kit's `{ type, message }` toast
// object, so this hook shows a toast for those two keys directly instead of reading a `toast`
// sub-object.
import { router } from "@inertiajs/react";
import { useEffect } from "react";
import { toast } from "sonner";

export function useFlashToast(): void {
    useEffect(() => {
        return router.on("flash", (event) => {
            const flash = (event as CustomEvent).detail?.flash as
                | { success?: string; error?: string }
                | undefined;

            if (!flash) {
                return;
            }

            if (flash.success) {
                toast.success(flash.success);
            }

            if (flash.error) {
                toast.error(flash.error);
            }
        });
    }, []);
}

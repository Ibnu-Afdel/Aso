// Ported from Laravel's React starter kit (github.com/laravel/react-starter-kit), MIT. See LICENSES/laravel-react-starter-kit.md.
import { useCallback } from 'react';

export type CleanupFn = () => void;

export function useMobileNavigation(): CleanupFn {
    return useCallback(() => {
        // Remove pointer-events style from body...
        document.body.style.removeProperty('pointer-events');
    }, []);
}

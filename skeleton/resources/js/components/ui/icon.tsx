// Ported from the Laravel React starter kit's shadcn/ui primitives (github.com/laravel/react-starter-kit), MIT. See LICENSES/laravel-react-starter-kit.md.
import type { LucideIcon } from 'lucide-react';

interface IconProps {
    iconNode?: LucideIcon | null;
    className?: string;
}

export function Icon({ iconNode: IconComponent, className }: IconProps) {
    if (!IconComponent) {
        return null;
    }

    return <IconComponent className={className} />;
}

// Ported from Laravel's React starter kit (github.com/laravel/react-starter-kit), MIT. See
// LICENSES/laravel-react-starter-kit.md.
import type { InertiaLinkProps } from "@inertiajs/react";
import type { LucideIcon } from "lucide-react";

export type BreadcrumbItem = {
    title: string;
    href: NonNullable<InertiaLinkProps["href"]>;
};

export type NavItem = {
    title: string;
    href: NonNullable<InertiaLinkProps["href"]>;
    icon?: LucideIcon | null;
    isActive?: boolean;
};

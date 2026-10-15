// Ported from Laravel's React starter kit (github.com/laravel/react-starter-kit), MIT. See
// LICENSES/laravel-react-starter-kit.md. Trimmed: no two-factor/passkey fields (Phase 5, D-009).
export type User = {
    id: number;
    name: string;
    email: string;
    avatar?: string;
    email_verified_at: string | null;
    created_at: string;
    updated_at: string;
    [key: string]: unknown;
};

export type Auth = {
    user: User | null;
};

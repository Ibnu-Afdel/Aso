// The Aso mark: an open "A" with a diamond in place of the crossbar. Single colour, so it
// follows `fill-current`/`text-*` like any icon.
import type { SVGAttributes } from 'react';

export default function AppLogoIcon(props: SVGAttributes<SVGElement>) {
    return (
        <svg {...props} viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
            <path d="M16.5 4h7L38 36h-7.5L20 13.5 9.5 36H2L16.5 4Z" />
            <path d="M20 22.5l4.5 4.5-4.5 4.5-4.5-4.5Z" />
        </svg>
    );
}

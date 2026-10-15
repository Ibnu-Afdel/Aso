// The FastoGram mark: a forward-leaning "F" with two speed lines. Single colour, so it follows
// `fill-current`/`text-*` like any icon.
import type { SVGAttributes } from 'react';

export default function AppLogoIcon(props: SVGAttributes<SVGElement>) {
    return (
        <svg {...props} viewBox="0 0 42 40" xmlns="http://www.w3.org/2000/svg">
            <g transform="translate(7 0) skewX(-14)">
                <rect x="13" y="4" width="7" height="32" rx="1.5" />
                <rect x="13" y="4" width="22" height="7" rx="1.5" />
                <rect x="13" y="17" width="16" height="6.5" rx="1.5" />
                <rect x="1" y="17" width="8" height="2.5" rx="1.25" />
                <rect x="4" y="21" width="5" height="2.5" rx="1.25" />
            </g>
        </svg>
    );
}

// The Aso mark: a faceted crystal. The three dark facets follow `fill-current`/`text-*` like
// any icon; the sage facet keeps the brand accent in every theme.
import type { SVGAttributes } from 'react';

export default function AppLogoIcon(props: SVGAttributes<SVGElement>) {
    return (
        <svg {...props} viewBox="-62 0 440 440" xmlns="http://www.w3.org/2000/svg">
            <g stroke="currentColor" strokeWidth={12} strokeLinejoin="round">
                <polygon points="71,94 75,98 111,265 114,310 104,395 12,306 10,157" />
                <polygon points="157,10 218,80 220,98 159,268 143,271 98,85 100,75" />
                <polygon points="151,305 240,360 239,364 154,429 144,430 129,419 141,308" />
                <polygon points="245,119 305,171 305,265 263,331 252,334 183,287 182,279" fill="#6d8b71" stroke="#6d8b71" />
            </g>
        </svg>
    );
}

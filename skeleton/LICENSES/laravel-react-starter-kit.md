# Laravel React Starter Kit

The React side of this kit (layouts, components, pages, hooks under `resources/js/`) is ported
from the [Laravel React starter kit](https://github.com/laravel/react-starter-kit), which is
MIT-licensed (its `README.md` and `composer.json` say so; the repository has no separate
`LICENSE` file, checked 2026-10-09). See T-05 ("Licence") in the FastoGram docs.

```
MIT License

Copyright (c) Taylor Otwell

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Every ported file keeps a one-line header comment naming its origin (T-05): layouts, components,
hooks and pages ported from the kit say so directly; shadcn/ui primitives under
`resources/js/components/ui/` (vendored inside the kit's repo, not authored by Laravel, but MIT
either way) say "Ported from the Laravel React starter kit's shadcn/ui primitives".

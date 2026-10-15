// Ported from the Laravel React starter kit's shadcn/ui primitives (github.com/laravel/react-starter-kit), MIT. See LICENSES/laravel-react-starter-kit.md.
import { Loader2Icon } from "lucide-react"

import { cn } from "@/lib/utils"

function Spinner({ className, ...props }: React.ComponentProps<"svg">) {
  return (
    <Loader2Icon
      role="status"
      aria-label="Loading"
      className={cn("size-4 animate-spin", className)}
      {...props}
    />
  )
}

export { Spinner }

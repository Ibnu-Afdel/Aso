// Ported from the Laravel React starter kit's shadcn/ui primitives (github.com/laravel/react-starter-kit), MIT. See LICENSES/laravel-react-starter-kit.md.
import { cn } from "@/lib/utils"

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("bg-primary/10 animate-pulse rounded-md", className)}
      {...props}
    />
  )
}

export { Skeleton }

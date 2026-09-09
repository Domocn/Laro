import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-pill text-sm font-semibold tracking-tight transition-all duration-200 ease-[ease] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 active:scale-[0.95]",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground border border-primary hover:bg-primary/92",
        destructive:
          "bg-destructive text-destructive-foreground border border-destructive hover:bg-destructive/90",
        outline:
          "border border-primary bg-transparent text-primary hover:bg-primary/5",
        secondary:
          "bg-secondary text-secondary-foreground border border-transparent hover:bg-secondary/80",
        ghost: "hover:bg-muted hover:text-foreground",
        link: "text-primary underline-offset-4 hover:underline",
        black:
          "bg-black text-white border border-black hover:bg-black/90",
        inverted:
          "bg-white text-primary border border-white hover:bg-white/95",
        "outline-dark":
          "border border-white bg-transparent text-white hover:bg-white/10",
      },
      size: {
        default: "h-10 px-4 py-[7px]",
        sm: "h-9 rounded-pill px-3 text-xs",
        lg: "h-12 rounded-pill px-8 text-[15px]",
        icon: "h-10 w-10 rounded-full",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

const Button = React.forwardRef(({ className, variant, size, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "button"
  return (
    <Comp
      className={cn(buttonVariants({ variant, size, className }))}
      ref={ref}
      {...props} />
  );
})
Button.displayName = "Button"

export { Button, buttonVariants }

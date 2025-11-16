import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "../../lib/utils"

const buttonVariants = cva(
  "btn-base",
  {
      variants: {
        variant: {
          default: "bg-brand-500 text-white hover:bg-brand-600 shadow-sm",
          destructive: "bg-error text-white hover:bg-error-dark",
          outline: "border border-slate-300 dark:border-slate-700 bg-white dark:bg-[#1a1d29] hover:bg-slate-50 dark:hover:bg-[#252836] text-primary",
          secondary: "bg-slate-100 dark:bg-slate-700 text-slate-900 dark:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-600",
          ghost: "hover:bg-slate-100 dark:hover:bg-slate-700 text-primary",
          link: "text-brand-500 dark:text-blue-400 underline-offset-4 hover:underline",
          success: "bg-success text-white hover:bg-success-dark shadow-sm",
          warning: "bg-warning text-white hover:bg-warning-dark shadow-sm",
          primary: "bg-brand-500 text-white hover:bg-brand-600 shadow-sm",
        },
      size: {
        default: "h-10 px-4 py-2 text-sm",
        sm: "h-9 px-3 text-sm",
        lg: "h-11 px-6 text-base",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }

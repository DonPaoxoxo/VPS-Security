"use client";

import { type ButtonHTMLAttributes, forwardRef } from "react";

import { cn } from "@/lib/cn";

type Variant = "default" | "outline" | "ghost" | "destructive";

const variantClasses: Record<Variant, string> = {
  default: "bg-accent text-white hover:opacity-90",
  outline: "border border-card-border bg-transparent hover:bg-muted",
  ghost: "bg-transparent hover:bg-muted",
  destructive: "bg-critical text-white hover:opacity-90",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none",
        variantClasses[variant],
        className
      )}
      {...props}
    />
  )
);
Button.displayName = "Button";

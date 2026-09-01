import * as React from "react";
import { cn } from "@/lib/utils";
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> { variant?: "default" | "outline" | "ghost"; size?: "default" | "sm" | "lg"; }
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant="default", size="default", ...props }, ref) => (
  <button ref={ref} className={cn("inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none disabled:opacity-50", variant==="default" && "bg-slate-900 text-white hover:bg-slate-800", variant==="outline" && "border bg-white hover:bg-slate-50", variant==="ghost" && "hover:bg-slate-100", size==="default" && "h-10 px-4 py-2", size==="sm" && "h-8 px-3", size==="lg" && "h-11 px-8", className)} {...props} />
));
Button.displayName = "Button";

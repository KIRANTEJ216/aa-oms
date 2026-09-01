import * as React from "react";
import { cn } from "@/lib/utils";
export const Label = React.forwardRef<HTMLLabelElement, React.LabelHTMLAttributes<HTMLLabelElement>>(({ className, ...p }, ref) => (
  <label ref={ref} className={cn("text-sm font-medium", className)} {...p} />
));
Label.displayName = "Label";

"use client";

import { Loader2, CheckCircle, AlertCircle, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface LoadingStateProps {
  state: "idle" | "loading" | "success" | "error";
  message?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function LoadingState({
  state,
  message,
  size = "md",
  className,
}: LoadingStateProps) {
  const sizeClasses = {
    sm: "h-6 w-6 text-sm",
    md: "h-10 w-10 text-base",
    lg: "h-14 w-14 text-lg",
  };

  const iconClasses = {
    idle: "text-slate-400",
    loading: "text-primary animate-spin",
    success: "text-green-500",
    error: "text-red-500",
  };

  const icons = {
    idle: Loader2,
    loading: Loader2,
    success: CheckCircle,
    error: AlertCircle,
  };

  const Icon = icons[state];

  return (
    <div className={cn("flex flex-col items-center justify-center gap-3", className)}>
      <Icon
        className={cn(iconClasses[state], sizeClasses[size])}
        aria-hidden="true"
      />
      {message && (
        <p className={cn("text-center font-medium", {
          "text-slate-600": state === "idle" || state === "loading",
          "text-green-600": state === "success",
          "text-red-600": state === "error",
        })}>
          {message}
        </p>
      )}
    </div>
  );
}

interface InlineLoadingProps {
  label?: string;
  size?: "sm" | "md";
  className?: string;
}

export function InlineLoading({ label, size = "md", className }: InlineLoadingProps) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <Loader2 className={cn("animate-spin text-primary", size === "sm" && "h-4 w-4", size === "md" && "h-5 w-5")} />
      {label && <span className="text-sm text-slate-600">{label}</span>}
    </div>
  );
}

interface ButtonLoadingProps {
  isLoading: boolean;
  children: React.ReactNode;
  loadingText?: string;
  className?: string;
}

export function ButtonLoading({ isLoading, children, loadingText = "Loading...", className }: ButtonLoadingProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed",
        className
      )}
      disabled={isLoading}
    >
      {isLoading ? (
        <>
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          <span>{loadingText}</span>
        </>
      ) : (
        children
      )}
    </button>
  );
}

interface PageLoadingProps {
  message?: string;
  showProgress?: boolean;
}

export function PageLoading({ message = "Loading...", showProgress = false }: PageLoadingProps) {
  return (
    <div className="flex min-h-[400px] items-center justify-center p-8">
      <div className="text-center space-y-4">
        <Loader2 className="mx-auto h-12 w-12 animate-spin text-primary" />
        <div>
          <p className="text-lg font-medium text-slate-900">{message}</p>
          {showProgress && (
            <div className="mt-2 w-64 mx-auto">
              <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary animate-pulse"
                  style={{ width: "60%" }}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function CardLoading({ className }: { className?: string }) {
  return (
    <div className={cn("animate-pulse space-y-4", className)}>
      <div className="h-4 w-3/4 bg-slate-200 rounded" />
      <div className="h-3 w-1/2 bg-slate-200 rounded" />
      <div className="h-8 w-1/3 bg-slate-200 rounded" />
      <div className="h-4 w-1/4 bg-slate-200 rounded mt-2" />
    </div>
  );
}

export function TableLoading({ rows = 5, columns = 5 }: { rows?: number; columns?: number }) {
  const headerCells = Array.from({ length: columns }).map((_, i) => (
    <div key={i} className="h-4 bg-slate-200 rounded flex-1" style={{ maxWidth: "150px" }} />
  ));

  const rowCells = Array.from({ length: rows }).map((_, rowIndex) => (
    <div key={rowIndex} className="flex gap-4 px-4">
      {Array.from({ length: columns }).map((_, i) => (
        <div key={i} className="h-4 bg-slate-200 rounded flex-1" style={{ maxWidth: "150px" }} />
      ))}
    </div>
  ));

  return (
    <div className="space-y-3 animate-pulse">
      <div className="flex gap-4 px-4">
        {headerCells}
      </div>
      {rowCells}
    </div>
  );
}

export function KpiCardLoading() {
  return (
    <div className="animate-pulse space-y-3 p-4 bg-white rounded-lg border">
      <div className="h-4 w-1/2 bg-slate-200 rounded" />
      <div className="h-8 w-1/3 bg-slate-200 rounded" />
      <div className="h-4 w-1/4 bg-slate-200 rounded" />
    </div>
  );
}
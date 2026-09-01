"use client";

import { createContext, useContext, useState, useCallback, ReactNode } from "react";
import { X, CheckCircle, AlertCircle, Info, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

export type ToastType = "success" | "error" | "info" | "loading";

interface Toast {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  duration?: number;
  action?: { label: string; onClick: () => void };
}

interface ToastContextType {
  toasts: Toast[];
  toast: (toast: Omit<Toast, "id">) => string;
  dismiss: (id: string) => void;
  dismissAll: () => void;
}

const ToastContext = createContext<ToastContextType | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback((toast: Omit<Toast, "id">) => {
    const id = Math.random().toString(36).substring(2, 9);
    const newToast = { ...toast, id };
    setToasts((prev) => [...prev, newToast]);
    
    if (toast.duration !== 0 && toast.type !== "loading") {
      setTimeout(() => dismiss(id), toast.duration ?? 5000);
    }
    return id;
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const dismissAll = useCallback(() => {
    setToasts([]);
  }, []);

  return (
    <ToastContext.Provider value={{ toasts, toast, dismiss, dismissAll }}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used within ToastProvider");
  return context;
}

function ToastContainer({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: string) => void }) {
  return (
    <AnimatePresence>
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-80">
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
        ))}
      </div>
    </AnimatePresence>
  );
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: (id: string) => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 100, y: 20 }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      exit={{ opacity: 0, x: 100, y: -20 }}
      transition={{ type: "spring", damping: 25, stiffness: 300 }}
      className={cn(
        "flex items-start gap-3 p-4 rounded-lg border shadow-lg bg-white",
        {
          "bg-green-50 text-green-900 border-green-200": toast.type === "success",
          "bg-red-50 text-red-900 border-red-200": toast.type === "error",
          "bg-blue-50 text-blue-900 border-blue-200": toast.type === "info",
          "bg-slate-50 text-slate-900 border-slate-200": toast.type === "loading",
        }
      )}
    >
      <div className="flex-shrink-0 mt-0.5">
        {(() => {
          switch (toast.type) {
            case "success": return <CheckCircle className="h-5 w-5" />;
            case "error": return <AlertCircle className="h-5 w-5" />;
            case "info": return <Info className="h-5 w-5" />;
            case "loading": return <Loader2 className="h-5 w-5 animate-spin" />;
          }
        })()}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium">{toast.title}</p>
        {toast.message && (
          <p className="mt-1 text-sm opacity-80">{toast.message}</p>
        )}
      </div>
      <button
        onClick={() => onDismiss(toast.id)}
        className="flex-shrink-0 p-1 rounded hover:opacity-50 transition-opacity"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4 opacity-50" />
      </button>
    </motion.div>
  );
}

export function useToastHelpers() {
  const { toast, dismiss } = useToast();
  
  return {
    success: (title: string, message?: string) =>
      toast({ type: "success", title, message }),
    error: (title: string, message?: string) =>
      toast({ type: "error", title, message }),
    info: (title: string, message?: string) =>
      toast({ type: "info", title, message }),
    loading: (title: string, message?: string) =>
      toast({ type: "loading", title, message, duration: 0 }),
    dismiss,
  };
}
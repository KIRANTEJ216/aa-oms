"use client";

import { Card, CardContent, CardHeader, CardTitle } from "./card";

export function CardSkeleton({ className = "" }: { className?: string }) {
  return (
    <Card className={`animate-pulse ${className}`}>
      <CardHeader>
        <div className="h-4 w-3/4 bg-slate-200 rounded" />
        <div className="h-3 w-1/2 bg-slate-200 rounded mt-2" />
      </CardHeader>
      <CardContent>
        <div className="h-8 w-1/3 bg-slate-200 rounded" />
        <div className="h-4 w-1/4 bg-slate-200 rounded mt-2" />
      </CardContent>
    </Card>
  );
}

export function TableRowSkeleton({ columns = 5 }: { columns?: number }) {
  return (
    <tr className="animate-pulse">
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="p-3">
          <div className={`h-4 bg-slate-200 rounded ${i === 0 ? 'w-3/4' : 'w-1/2'}`} />
        </td>
      ))}
    </tr>
  );
}

export function KpiCardSkeleton() {
  return (
    <div className="animate-pulse space-y-3">
      <div className="h-4 w-1/2 bg-slate-200 rounded" />
      <div className="h-8 w-1/3 bg-slate-200 rounded" />
      <div className="h-4 w-1/4 bg-slate-200 rounded" />
    </div>
  );
}

export function TableSkeleton({ rows = 5, columns = 5 }: { rows?: number; columns?: number }) {
  return (
    <div className="space-y-3">
      <div className="animate-pulse flex gap-4">
        {Array.from({ length: columns }).map((_, i) => (
          <div key={i} className="h-4 bg-slate-200 rounded flex-1" style={{ maxWidth: '150px' }} />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <TableRowSkeleton key={rowIndex} columns={columns} />
      ))}
    </div>
  );
}

export function PageSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Header skeleton */}
      <div className="flex items-center justify-between">
        <div className="h-8 w-48 bg-slate-200 rounded" />
        <div className="h-6 w-32 bg-slate-200 rounded" />
      </div>
      
      {/* KPI Cards skeleton */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <KpiCardSkeleton key={i} />
        ))}
      </div>
      
      {/* Secondary metrics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <KpiCardSkeleton key={`secondary-${i}`} />
        ))}
      </div>
      
      {/* Table skeleton */}
      <div className="rounded-lg border bg-white">
        <TableSkeleton rows={5} columns={5} />
      </div>
    </div>
  );
}
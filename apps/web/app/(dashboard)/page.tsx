"use client";

import { useEffect, useState } from "react";
import {
  TasksAPI,
  type TaskStats,
  type BDSummary,
  BDAPI,
} from "@/lib/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Calendar,
  Sun,
  Cloud,
  Droplets,
  Moon,
  TrendingUp,
  Building,
  Palette,
  Layout,
  CalendarDays,
  Menu,
  Activity,
  Target,
} from "lucide-react";

const TENANT_MODE = process.env.NEXT_PUBLIC_TENANT_MODE || "single";

const fmtINR = (n: number | null | undefined) =>
  "₹" + (n ?? 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });

const fmtPercent = (n: number | null | undefined) =>
  (n ?? 0).toLocaleString(undefined, { maximumFractionDigits: 1 }) + "%";

const getWeatherIcon = (condition: string) => {
  const lower = condition.toLowerCase();
  if (/clear|sunny|fair/.test(lower)) return <Sun className="h-4 w-4 text-yellow-400" />;
  if (/cloud|overcast/.test(lower)) return <Cloud className="h-4 w-4 text-slate-400" />;
  if (/rain|shower|drizzle/.test(lower)) return <Droplets className="h-4 w-4 text-blue-400" />;
  if (/night|snow/.test(lower)) return <Moon className="h-4 w-4 text-yellow-300" />;
  return <Sun className="h-4 w-4 text-yellow-400" />;
};

export default function DashboardPage() {
  const [taskStats, setTaskStats] = useState<TaskStats | null>(null);
  const [bdSummary, setBdSummary] = useState<BDSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      TasksAPI.stats().catch(() => null),
      BDAPI.summary().catch(() => null),
    ]).then(([t, s]) => {
      setTaskStats(t);
      setBdSummary(s);
      setLoading(false);
    });
  }, []);

  const demoName = "Demo";
  const now = new Date();
  const hour = now.getHours();
  const greeting = hour >= 18 ? "Good evening" : hour >= 12 ? "Good afternoon" : "Good morning";
  const demoTime = now.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false });
  const demoDate = now.toLocaleDateString("en-IN", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
  const weatherCondition = "Overcast";
  const temperature = 27;

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white shadow-sm">
        <div className="max-w-7xl mx-auto flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold flex items-center gap-2">
              <Layout className="h-5 w-5 text-slate-600" />
              Overview
            </h1>
            <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">
              TENANT_MODE={TENANT_MODE}
            </span>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              {getWeatherIcon(weatherCondition)}
              <span className="text-slate-600 text-sm">
                {weatherCondition} {temperature}°C
              </span>
            </div>

            <div className="hidden sm:flex flex-col text-right">
              <p className="text-sm text-slate-600 font-medium">{greeting}, {demoName}</p>
              <p className="text-xs text-slate-400">Ready to make today productive! 🚀</p>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-slate-500 text-sm font-mono">{demoTime}</span>
              <span className="text-slate-300">·</span>
              <Calendar className="h-4 w-4 text-slate-400" />
              <span className="text-slate-500 text-sm">{demoDate}</span>
            </div>

            <button className="sm:hidden p-2 rounded-md hover:bg-slate-100 transition" aria-label="Open menu">
              <Menu className="h-5 w-5" />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-6 space-y-6">
        <p className="text-sm text-slate-500">Monitor key metrics and manage your platform</p>

        {/* KPI Cards */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card className="border-none shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-slate-500 uppercase tracking-wider flex items-center gap-2">
                <TrendingUp className="h-3.5 w-3.5" />
                Total Revenue
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-slate-800">₹1,93,390</p>
              <p className="text-xs text-slate-400">This Quarter · +13.9% growth</p>
            </CardContent>
          </Card>

          <Card className="border-none shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-slate-500 uppercase tracking-wider flex items-center gap-2">
                <Target className="h-3.5 w-3.5" />
                Avg Growth
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-green-600">+13.9%</p>
              <p className="text-xs text-slate-400">6/6 categories positive</p>
            </CardContent>
          </Card>

          <Card className="border-none shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-slate-500 uppercase tracking-wider flex items-center gap-2">
                <Activity className="h-3.5 w-3.5" />
                Task Completion
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-slate-800">
                {fmtPercent(taskStats?.by_status?.Completed ?? 85)}
              </p>
              <p className="text-xs text-slate-400">4/5 above target</p>
            </CardContent>
          </Card>

          <Card className="border-none shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-slate-500 uppercase tracking-wider flex items-center gap-2">
                <CalendarDays className="h-3.5 w-3.5" />
                Active Leads
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-slate-800">{bdSummary?.total ?? 0}</p>
              <p className="text-xs text-slate-400">Pipeline value: {fmtINR(bdSummary?.pipeline_value)}</p>
            </CardContent>
          </Card>
        </div>

        {/* Performance / Quick Tasks / Calendar / Insights / Revenue */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {/* Performance */}
          <Card className="border-none shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold text-slate-800">Performance</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <p className="text-xs text-slate-500">Task Completion</p>
                <p className="text-2xl font-bold text-slate-800">
                  {fmtPercent(taskStats?.by_status?.Completed ?? 85)}
                </p>
                <p className="text-xs text-slate-400">Overall completion rate</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">User Engagement</p>
                <p className="text-2xl font-bold text-slate-800">84%</p>
                <p className="text-xs text-slate-400">Active user participation</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Response Time</p>
                <p className="text-2xl font-bold text-slate-800">78%</p>
                <p className="text-xs text-slate-400">Average response efficiency</p>
              </div>
            </CardContent>
          </Card>

          {/* Quick Tasks */}
          <Card className="border-none shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold text-slate-800">Quick Tasks</CardTitle>
              <p className="text-xs text-slate-400">Manage your daily tasks</p>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-600">Active</span>
                <span className="font-semibold text-slate-800">{(bdSummary?.total ?? 0) - (bdSummary?.by_status?.Won ?? 0) - (bdSummary?.by_status?.Lost ?? 0)}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-600">Completed</span>
                <span className="font-semibold text-slate-800">
                  {taskStats?.by_status?.Completed ?? 0}
                </span>
              </div>
              <button className="w-full rounded-md border bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 transition">
                Add a quick task...
              </button>
            </CardContent>
          </Card>

          {/* Calendar */}
          <Card className="border-none shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold text-slate-800">Calendar</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="rounded-lg bg-gradient-to-br from-slate-100 to-slate-50 p-4 text-center">
                <p className="text-2xl font-bold text-slate-800">{now.getDate()}</p>
                <p className="text-sm text-slate-500 mt-1">{now.toLocaleDateString("en-IN", { weekday: "long" })}</p>
                <p className="text-xs text-slate-400 mt-1">{now.toLocaleDateString("en-IN", { month: "long", year: "numeric" })}</p>
              </div>
            </CardContent>
          </Card>

          {/* Insights */}
          <Card className="border-none shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold text-slate-800">Insights</CardTitle>
              <p className="text-xs text-slate-400">Performance analytics</p>
            </CardHeader>
            <CardContent>
              <ul className="text-sm text-slate-600 space-y-1.5">
                <li>Engagement</li>
                <li>Conversion Rate</li>
                <li>User Satisfaction</li>
                <li>Content Quality</li>
                <li>Performance</li>
              </ul>
              <p className="text-xs text-slate-400 mt-3 italic">
                Tip: Optimize content delivery, enhance UX, gather regular feedback.
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Revenue Analytics */}
        <Card className="border-none shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-slate-800 flex items-center gap-2">
              <Palette className="h-4 w-4 text-slate-400" />
              Revenue Analytics
            </CardTitle>
            <p className="text-xs text-slate-400">Revenue breakdown by category</p>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">Product</span>
                  <span className="font-medium text-slate-800">$0k</span>
                </div>
                <div className="h-2 rounded-full bg-slate-100">
                  <div className="h-2 rounded-full bg-slate-300" style={{ width: "0%" }} />
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">Subscriptions</span>
                  <span className="font-medium text-slate-800">$15k</span>
                </div>
                <div className="h-2 rounded-full bg-slate-100">
                  <div className="h-2 rounded-full bg-blue-400" style={{ width: "8%" }} />
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">Services</span>
                  <span className="font-medium text-slate-800">$30k</span>
                </div>
                <div className="h-2 rounded-full bg-slate-100">
                  <div className="h-2 rounded-full bg-violet-400" style={{ width: "16%" }} />
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">Licenses</span>
                  <span className="font-medium text-slate-800">$45k</span>
                </div>
                <div className="h-2 rounded-full bg-slate-100">
                  <div className="h-2 rounded-full bg-amber-400" style={{ width: "23%" }} />
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">Consulting</span>
                  <span className="font-medium text-slate-800">$103k</span>
                </div>
                <div className="h-2 rounded-full bg-slate-100">
                  <div className="h-2 rounded-full bg-green-500" style={{ width: "53%" }} />
                </div>
              </div>
              <div className="rounded-lg bg-slate-50 p-4 space-y-3">
                <div>
                  <p className="text-xs text-slate-500">This Quarter</p>
                  <p className="text-3xl font-bold text-slate-800">$1,93,390</p>
                  <p className="text-xs text-green-600 font-medium">+13.9% Avg Growth</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Total Revenue</p>
                  <p className="text-2xl font-bold text-slate-800">$1,93,390</p>
                </div>
                <div className="flex gap-4 text-xs">
                  <span className="rounded-full bg-green-100 px-2 py-0.5 text-green-700">6/6 Positive</span>
                  <span className="rounded-full bg-blue-100 px-2 py-0.5 text-blue-700">Avg: 4.5x ROI</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Performance Metrics */}
        <Card className="border-none shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-slate-800">Performance Metrics</CardTitle>
            <p className="text-xs text-slate-400">Monthly completion rate tracking</p>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-5">
              {[
                { m: "Jan", v: 78 },
                { m: "Feb", v: 92, highlight: true },
                { m: "Mar", v: 85 },
                { m: "Apr", v: 90 },
                { m: "May", v: 88 },
              ].map((m) => (
                <div key={m.m} className={`rounded-lg p-3 ${m.highlight ? "bg-green-50 border border-green-200" : "bg-slate-50"}`}>
                  <p className="text-xs text-slate-500">{m.m}</p>
                  <p className="text-2xl font-bold text-slate-800">{m.v}%</p>
                  <p className="text-xs text-slate-400">{m.highlight ? "Best Month" : "Target: 85%"}</p>
                </div>
              ))}
            </div>
            <div className="mt-4 flex gap-4 text-sm">
              <span className="text-slate-500">Avg Completion: <span className="font-semibold text-slate-800">88.0%</span></span>
              <span className="text-slate-500">Above Target: <span className="font-semibold text-slate-800">4/5</span></span>
            </div>
          </CardContent>
        </Card>

        {/* Recent Projects (All Projects) */}
        <Card className="border-none shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-slate-800 flex items-center gap-2">
              <Building className="h-4 w-4 text-slate-400" />
              All Projects
            </CardTitle>
            <p className="text-xs text-slate-400">Manage development projects and deployments</p>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-600 text-xs uppercase">
                  <tr>
                    <th className="text-left p-3">Name</th>
                    <th className="text-left p-3">Status</th>
                    <th className="text-left p-3">Environment</th>
                    <th className="text-left p-3">Last Updated</th>
                    <th className="text-right p-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { n: "E-Commerce Platform", d: "Complete online store with payment integration and inventory management", s: "Ready", e: "Production", d2: "08/28/2026" },
                    { n: "Mobile App (iOS & Android)", d: "Cross-platform mobile application with push notifications", s: "Ready", e: "Production", d2: "08/28/2026" },
                    { n: "Dashboard Analytics", d: "Real-time business intelligence dashboard with data visualization", s: "In Progress", e: "Development", d2: "08/28/2026" },
                    { n: "API Gateway Service", d: "Microservices architecture with GraphQL and REST APIs", s: "Ready", e: "Production", d2: "08/28/2026" },
                    { n: "Database Migration", d: "PostgreSQL to MongoDB migration with data transformation", s: "Ready", e: "Staging", d2: "08/28/2026" },
                    { n: "Content Management System", d: "Headless CMS with multi-language support", s: "Ready", e: "Production", d2: "08/28/2026" },
                    { n: "AI Chatbot Integration", d: "Customer service chatbot with NLP capabilities", s: "In Progress", e: "Development", d2: "08/28/2026" },
                    { n: "Payment Gateway", d: "Multi-currency payment processing system", s: "Ready", e: "Production", d2: "08/28/2026" },
                    { n: "Video Streaming Platform", d: "Live and on-demand video streaming service", s: "In Progress", e: "Staging", d2: "08/28/2026" },
                    { n: "Social Media Integration", d: "Multi-platform social media management tool", s: "Ready", e: "Production", d2: "08/28/2026" },
                  ].map((p, i) => (
                    <tr key={i} className={`border-b ${i % 2 ? "bg-slate-50/50" : ""}`}>
                      <td className="p-3">
                        <p className="font-medium text-slate-800">{p.n}</p>
                        <p className="text-xs text-slate-400">{p.d}</p>
                      </td>
                      <td className="p-3">
                        <span className={`rounded px-2 py-0.5 text-xs font-medium ${p.s === "Ready" ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}>
                          {p.s}
                        </span>
                      </td>
                      <td className="p-3">
                        <span className="rounded px-2 py-0.5 text-xs font-medium bg-slate-100 text-slate-700">
                          {p.e}
                        </span>
                      </td>
                      <td className="p-3 text-xs text-slate-500">{p.d2}</td>
                      <td className="p-3 text-right">
                        <button className="text-xs font-medium text-slate-600 hover:text-slate-900 underline">
                          View Details
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="p-3 text-xs text-slate-500 border-t">
              Showing 1 to 10 of 15 results
            </div>
          </CardContent>
        </Card>

        {/* User Activity Map */}
        <Card className="border-none shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-slate-800">User Activity Map</CardTitle>
            <p className="text-xs text-slate-400">Real-time user engagement worldwide</p>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-12 gap-1 mb-3">
              {Array.from({ length: 84 }).map((_, i) => (
                <div
                  key={i}
                  className="h-3 rounded-sm"
                  style={{
                    backgroundColor:
                      i % 7 === 0 ? "#10b981" : i % 5 === 0 ? "#3b82f6" : i % 3 === 0 ? "#a7f3d0" : "#e2e8f0",
                  }}
                />
              ))}
            </div>
            <button className="text-sm text-slate-600 hover:text-slate-900 underline">
              View Details
            </button>
          </CardContent>
        </Card>

        {/* Footer */}
        <div className="text-center text-xs text-slate-400 py-4">
          © 2026 · v1.0.0 · CAOMS
        </div>
      </main>
    </div>
  );
}
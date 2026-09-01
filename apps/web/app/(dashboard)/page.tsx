"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
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
  Home,
  Users,
  Briefcase,
  FileText,
  Settings,
  HelpCircle,
  LogOut,
  ChevronRight,
  Bell,
  Search,
  Filter,
  X,
  Clipboard,
  FolderOpen,
} from "lucide-react";
import { MobileDrawer } from "@/components/ui/mobile-drawer";
import { PageSkeleton, KpiCardSkeleton, TableSkeleton } from "@/components/ui/skeleton";
import { PageLoading } from "@/components/ui/loading";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { usePathname } from "next/navigation";

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

const navigationItems = [
  { label: "Dashboard", href: "/", icon: Home },
  { label: "Clients", href: "/clients", icon: Users },
  { label: "Tasks", href: "/tasks", icon: Clipboard },
  { label: "Compliance", href: "/compliance", icon: CalendarDays },
  { label: "Reports", href: "/reports", icon: FileText },
  { label: "Business Dev", href: "/bd", icon: Briefcase },
  { label: "Vault", href: "/credentials", icon: FolderOpen },
  { label: "Documents", href: "/documents", icon: FileText },
  { label: "Audit", href: "/audit", icon: Settings },
  { label: "Billing", href: "/billing", icon: TrendingUp },
];

const breadcrumbItems = [
  { label: "Dashboard", href: "/" },
];

function DashboardContent() {
  const [taskStats, setTaskStats] = useState<TaskStats | null>(null);
  const [bdSummary, setBdSummary] = useState<BDSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const pathname = usePathname();

  useEffect(() => {
    Promise.all([
      TasksAPI.stats().catch(() => null),
      BDAPI.summary().catch(() => null),
    ]).then(([t, s]) => {
      setTaskStats(t);
      setBdSummary(s);
      setLoading(false);
      setLastUpdated(new Date());
    });
  }, []);

  const handleKeyNavigation = (e: React.KeyboardEvent, callback: () => void) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      callback();
    }
  };

  const demoName = "Demo";
  const now = new Date();
  const hour = now.getHours();
  const greeting = hour >= 18 ? "Good evening" : hour >= 12 ? "Good afternoon" : "Good morning";
  const demoTime = now.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false });
  const demoDate = now.toLocaleDateString("en-IN", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
  const weatherCondition = "Overcast";
  const temperature = 27;

  if (loading) {
    return <PageSkeleton />;
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header with improved accessibility */}
      <header 
        className="border-b border-slate-200 bg-white shadow-sm sticky top-0 z-50"
        role="banner"
      >
        <div className="max-w-7xl mx-auto flex items-center justify-between px-4 sm:px-6 py-3">
          <div className="flex items-center gap-3">
            <Link 
              href="/" 
              className="flex items-center gap-2 text-slate-800 hover:text-slate-900 transition-colors focus:outline-none focus:ring-2 focus:ring-slate-500 rounded"
              aria-label="Go to Dashboard"
            >
              <Layout className="h-5 w-5 text-slate-600" aria-hidden="true" />
              <h1 className="text-xl sm:text-2xl font-semibold">Overview</h1>
            </Link>
            <span className="hidden sm:inline-block rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">
              TENANT_MODE={TENANT_MODE}
            </span>
          </div>

          <div className="flex items-center gap-3 sm:gap-4">
            {/* Weather & Calendar - Enhanced with better accessibility */}
            <div className="relative" role="status" aria-live="polite">
              <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-slate-50 hover:bg-slate-100 transition-colors cursor-pointer">
                {getWeatherIcon(weatherCondition)}
                <span className="text-slate-600 text-sm font-medium">
                  {weatherCondition} {temperature}°C
                </span>
              </div>
            </div>

            {/* User info with better hierarchy */}
            <div className="hidden sm:block text-right">
              <p className="text-sm text-slate-600 font-medium">
                {greeting}, {demoName}
              </p>
              <p className="text-xs text-slate-400">Ready to make today productive! 🚀</p>
            </div>

            {/* Time and date display */}
            <div className="hidden md:flex items-center gap-2 text-sm text-slate-500">
              <span className="font-mono">{demoTime}</span>
              <span className="text-slate-300">·</span>
              <CalendarDays className="h-4 w-4 text-slate-400" aria-hidden="true" />
              <span>{demoDate}</span>
            </div>

            {/* Search button */}
            <button
              className="p-2 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-slate-500"
              aria-label="Search"
            >
              <Search className="h-5 w-5" />
            </button>

            {/* Notifications */}
            <button
              className="relative p-2 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-slate-500"
              aria-label="Notifications"
            >
              <Bell className="h-5 w-5" />
              <span className="absolute -top-1 -right-1 h-3 w-3 bg-red-500 rounded-full text-xs text-white flex items-center justify-center">
                3
              </span>
            </button>

            {/* User avatar with dropdown */}
            <div className="relative">
              <button
                className="flex items-center gap-2 p-2 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-slate-500"
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                aria-expanded={isMobileMenuOpen}
                aria-haspopup="true"
                aria-label="User menu"
              >
                <div className="h-8 w-8 rounded-full bg-slate-300 flex items-center justify-center">
                  <span className="text-sm font-medium text-slate-600">
                    {demoName.split(' ')[0][0]}
                  </span>
                </div>
                <ChevronRight className="h-4 w-4" />
              </button>

              {/* Dropdown menu */}
              {isMobileMenuOpen && (
                <div className="absolute right-0 mt-2 w-56 bg-white border border-slate-200 rounded-md shadow-lg z-50">
                  <div className="py-1">
                    <div className="px-4 py-2 text-sm text-slate-700 border-b border-slate-100">
                      Signed in as {demoName}
                    </div>
                    <Link
                      href="/profile"
                      className="flex items-center gap-2 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors"
                      onClick={() => setIsMobileMenuOpen(false)}
                    >
                      <Settings className="h-4 w-4" />
                      Profile
                    </Link>
                    <button
                      className="w-full flex items-center gap-2 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors text-left"
                      onClick={() => setIsMobileMenuOpen(false)}
                    >
                      <LogOut className="h-4 w-4" />
                      Sign out
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Mobile menu button */}
            <button
              className="sm:hidden p-2 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-slate-500"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              aria-expanded={isMobileMenuOpen}
              aria-label="Toggle mobile menu"
            >
              {isMobileMenuOpen ? (
                <X className="h-5 w-5" />
              ) : (
                <Menu className="h-5 w-5" />
              )}
            </button>
          </div>
        </div>

        {/* Mobile navigation using new MobileDrawer component */}
        <MobileDrawer
          isOpen={isMobileMenuOpen}
          onClose={() => setIsMobileMenuOpen(false)}
          items={navigationItems}
          currentPath={pathname}
        />
      </header>

      {/* Main content */}
      <main 
        className="max-w-7xl mx-auto p-4 sm:p-6 space-y-6"
        role="main"
        aria-labelledby="page-title"
      >
        {/* Page title and breadcrumbs */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="mb-6"
        >
          <h1 
            id="page-title" 
            className="text-2xl sm:text-3xl font-bold text-slate-800 mb-2"
          >
            Dashboard Overview
          </h1>
          <nav className="flex text-sm text-slate-500" aria-label="Breadcrumb">
            <ol className="flex items-center space-x-2">
              {breadcrumbItems.map((item, index) => (
                <li key={item.href} className="flex items-center">
                  {index > 0 && <ChevronRight className="h-4 w-4 text-slate-400 mx-1" aria-hidden="true" />}
                  <Link
                    href={item.href}
                    className="hover:text-slate-700 transition-colors"
                    aria-current={index === breadcrumbItems.length - 1 ? "page" : undefined}
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ol>
          </nav>
        </motion.div>

        {/* Last updated indicator */}
        <div className="flex items-center justify-end text-xs text-slate-400 mb-4">
          <span>Updated {lastUpdated.toLocaleTimeString()}</span>
        </div>

        {/* KPI Cards - Enhanced with better accessibility and animations */}
        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Key metrics">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.1 }}
          >
            <Card 
              className="border-none shadow-sm hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => {}}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => handleKeyNavigation(e, () => {})}
              aria-label="View detailed revenue analytics"
            >
              <CardHeader className="pb-2">
                <CardTitle className="text-xs text-slate-500 uppercase tracking-wider flex items-center gap-2">
                  <TrendingUp className="h-3.5 w-3.5" aria-hidden="true" />
                  Total Revenue
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-slate-800">₹1,93,390</p>
                <p className="text-xs text-slate-400">This Quarter · +13.9% growth</p>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.15 }}
          >
            <Card 
              className="border-none shadow-sm hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => {}}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => handleKeyNavigation(e, () => {})}
              aria-label="View growth trends"
            >
              <CardHeader className="pb-2">
                <CardTitle className="text-xs text-slate-500 uppercase tracking-wider flex items-center gap-2">
                  <Target className="h-3.5 w-3.5" aria-hidden="true" />
                  Avg Growth
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-green-600">+13.9%</p>
                <p className="text-xs text-slate-400">6/6 categories positive</p>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.2 }}
          >
            <Card 
              className="border-none shadow-sm hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => {}}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => handleKeyNavigation(e, () => {})}
              aria-label="View task completion statistics"
            >
              <CardHeader className="pb-2">
                <CardTitle className="text-xs text-slate-500 uppercase tracking-wider flex items-center gap-2">
                  <Activity className="h-3.5 w-3.5" aria-hidden="true" />
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
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.25 }}
          >
            <Card 
              className="border-none shadow-sm hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => {}}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => handleKeyNavigation(e, () => {})}
              aria-label="View active business leads"
            >
              <CardHeader className="pb-2">
                <CardTitle className="text-xs text-slate-500 uppercase tracking-wider flex items-center gap-2">
                  <CalendarDays className="h-3.5 w-3.5" aria-hidden="true" />
                  Active Leads
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-slate-800">
                  {(bdSummary?.total ?? 0) - (bdSummary?.by_status?.Won ?? 0) - (bdSummary?.by_status?.Lost ?? 0)}
                </p>
                <p className="text-xs text-slate-400">Pipeline value: {fmtINR(bdSummary?.pipeline_value)}</p>
              </CardContent>
            </Card>
          </motion.div>
        </section>

        {/* Performance / Quick Tasks / Calendar / Insights / Revenue - Enhanced accessibility */}
        <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-4" aria-label="Secondary metrics">
          {/* Performance */}
          <Card className="border-none shadow-sm hover:shadow-md transition-shadow">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold text-slate-800">Performance</CardTitle>
              <p className="text-xs text-slate-400">Task performance metrics</p>
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

          {/* Quick Tasks - Enhanced with keyboard navigation */}
          <Card className="border-none shadow-sm hover:shadow-md transition-shadow">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold text-slate-800">Quick Tasks</CardTitle>
              <p className="text-xs text-slate-400">Manage your daily tasks</p>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-600">Active</span>
                <span className="font-semibold text-slate-800">
                  {(bdSummary?.total ?? 0) - (bdSummary?.by_status?.Won ?? 0) - (bdSummary?.by_status?.Lost ?? 0)}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-600">Completed</span>
                <span className="font-semibold text-slate-800">
                  {taskStats?.by_status?.Completed ?? 0}
                </span>
              </div>
              <button
                className="w-full rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2"
                onClick={() => {}}
                onKeyDown={(e) => handleKeyNavigation(e, () => {})}
              >
                Add a quick task...
              </button>
            </CardContent>
          </Card>

          {/* Calendar - Enhanced with better visual design */}
          <Card className="border-none shadow-sm hover:shadow-md transition-shadow">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold text-slate-800">Calendar</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="rounded-lg bg-gradient-to-br from-blue-50 to-indigo-50 p-4 text-center border border-blue-100">
                <p className="text-2xl font-bold text-blue-700">{now.getDate()}</p>
                <p className="text-sm text-blue-600 mt-1 font-medium">
                  {now.toLocaleDateString("en-IN", { weekday: "short" })}
                </p>
                <p className="text-xs text-blue-500 mt-1">
                  {now.toLocaleDateString("en-IN", { month: "short", year: "numeric" })}
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Insights - Enhanced with better typography */}
          <Card className="border-none shadow-sm hover:shadow-md transition-shadow">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold text-slate-800">Insights</CardTitle>
              <p className="text-xs text-slate-400">Performance analytics</p>
            </CardHeader>
            <CardContent>
              <ul className="text-sm text-slate-600 space-y-2">
                <li className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-blue-400" aria-hidden="true"></span>
                  Engagement
                </li>
                <li className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-green-400" aria-hidden="true"></span>
                  Conversion Rate
                </li>
                <li className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-purple-400" aria-hidden="true"></span>
                  User Satisfaction
                </li>
                <li className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-orange-400" aria-hidden="true"></span>
                  Content Quality
                </li>
                <li className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-red-400" aria-hidden="true"></span>
                  Performance
                </li>
              </ul>
              <p className="text-xs text-slate-400 mt-3 italic bg-slate-50 p-2 rounded">
                Tip: Optimize performance by focusing on user experience improvements.
              </p>
            </CardContent>
          </Card>

          {/* Revenue Analytics - Enhanced with better visual hierarchy */}
          <Card className="border-none shadow-sm hover:shadow-md transition-shadow lg:col-span-2">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold text-slate-800 flex items-center gap-2">
                <Palette className="h-4 w-4 text-slate-400" aria-hidden="true" />
                Revenue Analytics
              </CardTitle>
              <p className="text-xs text-slate-400">Revenue breakdown by category</p>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4 text-xs">
                <div className="flex justify-between items-center py-2 border-b border-slate-100">
                  <span className="text-slate-600">Product</span>
                  <span className="font-medium text-slate-800">$0k</span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-slate-100">
                  <span className="text-slate-600">Subscriptions</span>
                  <span className="font-medium text-slate-800">$15k</span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-slate-100">
                  <span className="text-slate-600">Services</span>
                  <span className="font-medium text-slate-800">$30k</span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-slate-100">
                  <span className="text-slate-600">Licenses</span>
                  <span className="font-medium text-slate-800">$45k</span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-slate-100">
                  <span className="text-slate-600">Consulting</span>
                  <span className="font-medium text-slate-800">$103k</span>
                </div>
              </div>
              <div className="mt-3 pt-3 border-t border-slate-200">
                <div className="flex justify-between text-sm font-medium">
                  <span>Total Revenue</span>
                  <span className="text-slate-800">$1,93,390</span>
                </div>
                <span className="text-xs text-green-600 font-medium">+13.9% Avg Growth</span>
              </div>
            </CardContent>
          </Card>
        </section>

        {/* Recent Projects (All Projects) - Enhanced with better table design */}
        <Card className="border-none shadow-sm hover:shadow-md transition-shadow">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-slate-800 flex items-center gap-2">
              <Building className="h-4 w-4 text-slate-400" aria-hidden="true" />
              All Projects
            </CardTitle>
            <p className="text-xs text-slate-400">Manage development projects and deployments</p>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-600 text-xs uppercase tracking-wider">
                  <tr>
                    <th className="text-left p-3 font-medium">Name</th>
                    <th className="text-left p-3 font-medium">Status</th>
                    <th className="text-left p-3 font-medium">Environment</th>
                    <th className="text-left p-3 font-medium">Last Updated</th>
                    <th className="text-right p-3 font-medium">Actions</th>
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
                    <tr 
                      key={i} 
                      className={`border-b ${i % 2 ? "bg-slate-50/50" : ""} hover:bg-slate-50 transition-colors`}
                    >
                      <td className="p-3">
                        <p className="font-medium text-slate-800">{p.n}</p>
                        <p className="text-xs text-slate-400 mt-1">{p.d}</p>
                      </td>
                      <td className="p-3">
                        <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${p.s === "Ready" ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}>
                          {p.s}
                        </span>
                      </td>
                      <td className="p-3">
                        <span className="inline-flex px-2 py-0.5 text-xs font-medium bg-slate-100 text-slate-700 rounded-full">
                          {p.e}
                        </span>
                      </td>
                      <td className="p-3 text-xs text-slate-500">{p.d2}</td>
                      <td className="p-3 text-right">
                        <button
                          className="text-xs font-medium text-slate-600 hover:text-slate-900 hover:underline focus:outline-none focus:text-slate-900 transition-colors"
                          onClick={() => {}}
                        >
                          View Details
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="p-3 text-xs text-slate-500 border-t bg-slate-50">
              Showing 1 to 10 of 15 results
            </div>
          </CardContent>
        </Card>

        {/* User Activity Map - Enhanced accessibility */}
        <Card className="border-none shadow-sm hover:shadow-md transition-shadow">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-slate-800">User Activity Map</CardTitle>
            <p className="text-xs text-slate-400">Real-time user engagement worldwide</p>
          </CardHeader>
          <CardContent>
            <div 
              className="grid grid-cols-12 gap-1 mb-3"
              role="img"
              aria-label="User activity visualization - 84 activity points across the world"
            >
              {Array.from({ length: 84 }).map((_, i) => (
                <div
                  key={i}
                  className="h-3 rounded-sm transition-all duration-300 hover:h-4 hover:opacity-80"
                  style={{
                    backgroundColor:
                      i % 7 === 0 ? "#10b981" : i % 5 === 0 ? "#3b82f6" : i % 3 === 0 ? "#a7f3d0" : "#e2e8f0",
                    opacity: Math.random() > 0.7 ? 0.4 : 1,
                  }}
                  title={`Activity point ${i + 1}`}
                />
              ))}
            </div>
            <button
              className="text-sm text-slate-600 hover:text-slate-900 hover:underline focus:outline-none focus:text-slate-900 transition-colors"
              onClick={() => {}}
            >
              View Details
            </button>
          </CardContent>
        </Card>

        {/* Footer with better accessibility */}
        <footer className="text-center text-xs text-slate-400 py-6 border-t border-slate-200">
          <div className="flex flex-col sm:flex-row justify-center items-center gap-2 sm:gap-4">
            <span>© 2026</span>
            <span className="hidden sm:inline">·</span>
            <span>v1.0.0</span>
            <span className="hidden sm:inline">·</span>
            <span>by Aniq-ui</span>
            <span className="hidden sm:inline">·</span>
            <Link href="#" className="hover:text-slate-600 transition-colors">Privacy Policy</Link>
            <span className="hidden sm:inline">·</span>
            <Link href="#" className="hover:text-slate-600 transition-colors">Terms of Service</Link>
          </div>
        </footer>
      </main>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ErrorBoundary>
      <DashboardContent />
    </ErrorBoundary>
  );
}
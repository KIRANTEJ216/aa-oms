"use client";

import { useState, useEffect } from "react";
import {
  Plus, Search, Filter, MoreVertical, Edit, Trash2, Eye,
  MessageSquare, AlertTriangle, Clock, CheckCircle, XCircle,
  Loader2, ChevronDown, Download, RefreshCw
} from "lucide-react";
import { SupportAPI, SupportTicket, SupportTicketStats } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { SupportChatbot } from "@/components/support-chatbot";
import { useToastHelpers } from "@/components/ui/toast";

const STATUS_COLORS: Record<string, string> = {
  Open: "bg-blue-100 text-blue-700",
  "In Progress": "bg-amber-100 text-amber-700",
  "Waiting on Customer": "bg-purple-100 text-purple-700",
  Resolved: "bg-green-100 text-green-700",
  Closed: "bg-slate-100 text-slate-700",
};

const PRIORITY_COLORS: Record<string, string> = {
  Low: "bg-slate-100 text-slate-700",
  Medium: "bg-blue-100 text-blue-700",
  High: "bg-amber-100 text-amber-700",
  Urgent: "bg-red-100 text-red-700",
};

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  Technical: <MessageSquare className="h-3.5 w-3.5" />,
  Billing: <AlertTriangle className="h-3.5 w-3.5" />,
  General: <Clock className="h-3.5 w-3.5" />,
  "Feature Request": <CheckCircle className="h-3.5 w-3.5" />,
  "Bug Report": <XCircle className="h-3.5 w-3.5" />,
};

export default function SupportPage() {
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [stats, setStats] = useState<SupportTicketStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [editingTicket, setEditingTicket] = useState<SupportTicket | null>(null);
  const [formData, setFormData] = useState<{
    title: string;
    description: string;
    category: "Technical" | "Billing" | "General" | "Feature Request" | "Bug Report";
    priority: "Low" | "Medium" | "High" | "Urgent";
    client_id: string;
  }>({
    title: "",
    description: "",
    category: "General",
    priority: "Medium",
    client_id: "",
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showChatbot, setShowChatbot] = useState(false);
  const { success, error } = useToastHelpers();

  const fetchTickets = async () => {
    setIsLoading(true);
    try {
      const [ticketsData, statsData] = await Promise.all([
        SupportAPI.list({ status: statusFilter, category: categoryFilter, priority: priorityFilter }),
        SupportAPI.stats(),
      ]);
      setTickets(ticketsData);
      setStats(statsData);
    } catch (err) {
      error("Failed to load support tickets");
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTickets();
  }, [statusFilter, categoryFilter, priorityFilter]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await SupportAPI.create(formData);
      success("Support ticket created successfully");
      setShowCreateDialog(false);
      resetForm();
      fetchTickets();
    } catch (err) {
      error("Failed to create ticket");
      console.error(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingTicket) return;
    setIsSubmitting(true);
    try {
      await SupportAPI.update(editingTicket.id, formData);
      success("Ticket updated successfully");
      setEditingTicket(null);
      resetForm();
      fetchTickets();
    } catch (err) {
      error("Failed to update ticket");
      console.error(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this ticket?")) return;
    try {
      await SupportAPI.remove(id);
      success("Ticket deleted");
      fetchTickets();
    } catch (err) {
      error("Failed to delete ticket");
      console.error(err);
    }
  };

  const handleEdit = (ticket: SupportTicket) => {
    setEditingTicket(ticket);
    setFormData({
      title: ticket.title,
      description: ticket.description,
      category: ticket.category,
      priority: ticket.priority,
      client_id: ticket.client_id || "",
    });
  };

  const resetForm = () => {
    setFormData({ title: "", description: "", category: "General", priority: "Medium", client_id: "" });
    setEditingTicket(null);
  };

  const filteredTickets = tickets.filter(ticket => {
    if (search) {
      const searchLower = search.toLowerCase();
      if (!ticket.title.toLowerCase().includes(searchLower) &&
          !ticket.description.toLowerCase().includes(searchLower) &&
          !ticket.id.toLowerCase().includes(searchLower)) {
        return false;
      }
    }
    return true;
  });

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="space-y-6">
      {/* Header & Stats */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Support Tickets</h1>
          <p className="text-slate-500 text-sm">Manage and track customer support requests</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => { fetchTickets(); }} disabled={isLoading}>
            <RefreshCw className="h-4 w-4 mr-2" /> Refresh
          </Button>
          <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
            <DialogTrigger asChild>
              <Button onClick={() => { resetForm(); setShowCreateDialog(true); }}>
                <Plus className="h-4 w-4 mr-2" /> New Ticket
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>{editingTicket ? "Edit Ticket" : "Create Support Ticket"}</DialogTitle>
              </DialogHeader>
              <form onSubmit={editingTicket ? handleUpdate : handleCreate} className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="sm:col-span-2">
                    <Label htmlFor="title">Title *</Label>
                    <Input
                      id="title"
                      value={formData.title}
                      onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                      placeholder="Brief description of the issue"
                      required
                    />
                  </div>
                  <div>
                    <Label htmlFor="category">Category</Label>
                    <Select value={formData.category} onValueChange={(v) => setFormData({ ...formData, category: v as "Technical" | "Billing" | "General" | "Feature Request" | "Bug Report" })}>
                      <SelectTrigger id="category"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Technical">Technical</SelectItem>
                        <SelectItem value="Billing">Billing</SelectItem>
                        <SelectItem value="General">General</SelectItem>
                        <SelectItem value="Feature Request">Feature Request</SelectItem>
                        <SelectItem value="Bug Report">Bug Report</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="priority">Priority</Label>
                    <Select value={formData.priority} onValueChange={(v) => setFormData({ ...formData, priority: v as "Low" | "Medium" | "High" | "Urgent" })}>
                      <SelectTrigger id="priority"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Low">Low</SelectItem>
                        <SelectItem value="Medium">Medium</SelectItem>
                        <SelectItem value="High">High</SelectItem>
                        <SelectItem value="Urgent">Urgent</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="client_id">Client ID (Optional)</Label>
                    <Input
                      id="client_id"
                      value={formData.client_id}
                      onChange={(e) => setFormData({ ...formData, client_id: e.target.value })}
                      placeholder="Link to client"
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <Label htmlFor="description">Description *</Label>
                    <Textarea
                      id="description"
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      placeholder="Detailed description of the issue..."
                      rows={4}
                      required
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => { setShowCreateDialog(false); resetForm(); }}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={isSubmitting}>
                    {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                    {editingTicket ? "Update" : "Create"}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
          <Button variant="outline" onClick={() => setShowChatbot(true)}>
            <MessageSquare className="h-4 w-4 mr-2" /> Chat Assistant
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-500">Total Tickets</p>
                  <p className="text-2xl font-bold text-slate-800">{stats.total}</p>
                </div>
                <div className="h-12 w-12 rounded-lg bg-blue-100 flex items-center justify-center">
                  <MessageSquare className="h-6 w-6 text-blue-600" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-500">Open</p>
                  <p className="text-2xl font-bold text-blue-600">{stats.by_status.Open || 0}</p>
                </div>
                <div className="h-12 w-12 rounded-lg bg-blue-100 flex items-center justify-center">
                  <Clock className="h-6 w-6 text-blue-600" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-500">In Progress</p>
                  <p className="text-2xl font-bold text-amber-600">{stats.by_status["In Progress"] || 0}</p>
                </div>
                <div className="h-12 w-12 rounded-lg bg-amber-100 flex items-center justify-center">
                  <Loader2 className="h-6 w-6 text-amber-600" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-500">Resolved</p>
                  <p className="text-2xl font-bold text-green-600">{stats.by_status.Resolved || 0}</p>
                </div>
                <div className="h-12 w-12 rounded-lg bg-green-100 flex items-center justify-center">
                  <CheckCircle className="h-6 w-6 text-green-600" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-500">High Priority</p>
                  <p className="text-2xl font-bold text-red-600">{stats.by_priority.Urgent || 0 + stats.by_priority.High || 0}</p>
                </div>
                <div className="h-12 w-12 rounded-lg bg-red-100 flex items-center justify-center">
                  <AlertTriangle className="h-6 w-6 text-red-600" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <Card className="border-slate-200">
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <Input
                placeholder="Search tickets..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[180px]"><SelectValue placeholder="Status" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="">All Statuses</SelectItem>
                <SelectItem value="Open">Open</SelectItem>
                <SelectItem value="In Progress">In Progress</SelectItem>
                <SelectItem value="Waiting on Customer">Waiting on Customer</SelectItem>
                <SelectItem value="Resolved">Resolved</SelectItem>
                <SelectItem value="Closed">Closed</SelectItem>
              </SelectContent>
            </Select>
            <Select value={categoryFilter} onValueChange={setCategoryFilter}>
              <SelectTrigger className="w-[180px]"><SelectValue placeholder="Category" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="">All Categories</SelectItem>
                <SelectItem value="Technical">Technical</SelectItem>
                <SelectItem value="Billing">Billing</SelectItem>
                <SelectItem value="General">General</SelectItem>
                <SelectItem value="Feature Request">Feature Request</SelectItem>
                <SelectItem value="Bug Report">Bug Report</SelectItem>
              </SelectContent>
            </Select>
            <Select value={priorityFilter} onValueChange={setPriorityFilter}>
              <SelectTrigger className="w-[160px]"><SelectValue placeholder="Priority" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="">All Priorities</SelectItem>
                <SelectItem value="Low">Low</SelectItem>
                <SelectItem value="Medium">Medium</SelectItem>
                <SelectItem value="High">High</SelectItem>
                <SelectItem value="Urgent">Urgent</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Tickets Table */}
      <Card className="border-slate-200">
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-8 text-center">
              <Loader2 className="h-8 w-8 animate-spin text-slate-400 mx-auto mb-2" />
              <p className="text-slate-500">Loading tickets...</p>
            </div>
          ) : filteredTickets.length === 0 ? (
            <div className="p-8 text-center">
              <MessageSquare className="h-12 w-12 text-slate-300 mx-auto mb-3" />
              <h3 className="text-slate-600 font-medium">No tickets found</h3>
              <p className="text-slate-400 text-sm mt-1">Create a new support ticket to get started</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Ticket</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Category</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Priority</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Status</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Created</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Source</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {filteredTickets.map((ticket) => (
                    <tr key={ticket.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-4 py-4">
                        <div>
                          <p className="font-medium text-slate-800 truncate max-w-xs">{ticket.title}</p>
                          <p className="text-xs text-slate-500 truncate max-w-xs">{ticket.description.slice(0, 60)}...</p>
                          <p className="text-xs text-slate-400 font-mono">#{ticket.id.slice(0, 8)}</p>
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <span className="inline-flex items-center gap-1.5">
                          {CATEGORY_ICONS[ticket.category] || <Clock className="h-3.5 w-3.5" />}
                          <span className="text-sm text-slate-700">{ticket.category}</span>
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        <Badge className={PRIORITY_COLORS[ticket.priority]}>{ticket.priority}</Badge>
                      </td>
                      <td className="px-4 py-4">
                        <Badge className={STATUS_COLORS[ticket.status]}>{ticket.status}</Badge>
                      </td>
                      <td className="px-4 py-4 text-sm text-slate-600">{formatDate(ticket.created_at)}</td>
                      <td className="px-4 py-4">
                        <Badge variant="outline" className="capitalize">{ticket.source}</Badge>
                      </td>
                      <td className="px-4 py-4 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button variant="ghost" size="sm" onClick={() => handleEdit(ticket)} aria-label="Edit ticket">
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleDelete(ticket.id)} aria-label="Delete ticket">
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Chatbot */}
      <SupportChatbot isOpen={showChatbot} onClose={() => setShowChatbot(false)} />
    </div>
  );
}
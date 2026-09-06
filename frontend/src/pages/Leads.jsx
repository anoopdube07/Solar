import React, { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import api, { apiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/ui-bits";
import { StatusBadge } from "@/components/StatusBadge";
import { RETURN_REASON_LABELS } from "@/lib/constants";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Plus, Search } from "lucide-react";
import { toast } from "sonner";

export default function Leads() {
  const { user } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const params = new URLSearchParams(loc.search);
  const statusFilter = params.get("status") || "";
  const [leads, setLeads] = useState([]);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", phone: "", email: "", address: "", source: "", financing_required: false, project_price: "", remarks: "" });

  const load = () => api.get("/leads").then((r) => setLeads(r.data));
  useEffect(() => { load(); }, []);

  const canCreate = user.role === "LEAD" || user.role === "OWNER";
  const filtered = leads.filter((l) =>
    (!statusFilter || l.status === statusFilter) &&
    (!q || l.name.toLowerCase().includes(q.toLowerCase()) || (l.phone || "").includes(q))
  );

  const create = async () => {
    if (!form.name || !form.phone) { toast.error("Name and phone are required"); return; }
    try {
      await api.post("/leads", { ...form, project_price: parseFloat(form.project_price) || 0 });
      toast.success("Lead created");
      setOpen(false);
      setForm({ name: "", phone: "", email: "", address: "", source: "", financing_required: false, project_price: "", remarks: "" });
      load();
    } catch (e) { toast.error(apiError(e.response?.data?.detail)); }
  };

  return (
    <div>
      <PageHeader title="Leads" subtitle="Lead qualification workspace"
        right={canCreate && (
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button data-testid="new-lead-button" className="bg-sky-600 hover:bg-sky-700"><Plus size={16} className="mr-1" /> New Lead</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>Create Lead</DialogTitle></DialogHeader>
              <div className="space-y-3">
                <div><Label>Name *</Label><Input data-testid="lead-name-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
                <div><Label>Phone *</Label><Input data-testid="lead-phone-input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></div>
                <div className="grid grid-cols-2 gap-3">
                  <div><Label>Email</Label><Input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
                  <div><Label>Source</Label><Input value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} /></div>
                </div>
                <div><Label>Address</Label><Input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} /></div>
                <div><Label>Project Price / Customer Agreed Price (₹)</Label><Input data-testid="lead-project-price-input" type="number" value={form.project_price} onChange={(e) => setForm({ ...form, project_price: e.target.value })} /></div>
                <div className="flex items-center gap-2">
                  <Checkbox id="fin" checked={form.financing_required} onCheckedChange={(v) => setForm({ ...form, financing_required: !!v })} data-testid="lead-financing-checkbox" />
                  <Label htmlFor="fin">Financing Required</Label>
                </div>
                <div><Label>Remarks</Label><Textarea value={form.remarks} onChange={(e) => setForm({ ...form, remarks: e.target.value })} /></div>
              </div>
              <DialogFooter><Button data-testid="lead-create-submit" onClick={create} className="bg-sky-600 hover:bg-sky-700">Create</Button></DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      />
      <div className="p-6 lg:p-8">
        <div className="flex items-center gap-3 mb-4">
          <div className="relative flex-1 max-w-sm">
            <Search size={16} className="absolute left-3 top-2.5 text-slate-400" />
            <Input data-testid="lead-search" className="pl-9" placeholder="Search name or phone…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          {statusFilter && <StatusBadge value={statusFilter} />}
          {statusFilter && <button className="text-xs text-sky-600 underline" onClick={() => nav("/leads")}>clear</button>}
        </div>
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <Table>
            <TableHeader className="bg-slate-50">
              <TableRow>
                <TableHead>Name</TableHead><TableHead>Phone</TableHead><TableHead>Status</TableHead>
                <TableHead>Current Team</TableHead><TableHead>Note</TableHead><TableHead>Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((l) => (
                <TableRow key={l.id} data-testid={`lead-row-${l.id}`} className="hover:bg-slate-50 cursor-pointer" onClick={() => nav(`/leads/${l.id}`)}>
                  <TableCell className="font-semibold text-slate-900">{l.name}</TableCell>
                  <TableCell className="font-mono text-sm">{l.phone}</TableCell>
                  <TableCell><StatusBadge value={l.status} /></TableCell>
                  <TableCell className="text-sm">{l.current_team || "—"}</TableCell>
                  <TableCell className="text-xs text-slate-500">
                    {l.action_required && <span className="text-amber-600 font-semibold">Action Required</span>}
                    {l.return_reason && <span className="ml-1">· {RETURN_REASON_LABELS[l.return_reason]}</span>}
                  </TableCell>
                  <TableCell><Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); nav(`/leads/${l.id}`); }}>Open</Button></TableCell>
                </TableRow>
              ))}
              {filtered.length === 0 && <TableRow><TableCell colSpan={6} className="text-center text-slate-400 py-10">No leads found.</TableCell></TableRow>}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  );
}

import React, { useEffect, useState } from "react";
import api, { apiError } from "@/lib/api";
import { PageHeader } from "@/components/ui-bits";
import { ROLE_LABELS } from "@/lib/constants";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Plus, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

const ROLES = ["OWNER", "MANAGER", "LEAD", "REGISTRATION", "ACCOUNTS", "DISPATCH", "INSTALLATION_MANAGER", "INSTALLATION_MEMBER", "COMPLAINT"];
const TYPE_LABELS = { LEAD: "Lead", ECP: "ECP Project", SITE_VISIT: "Site Visit", COMPLAINT: "Complaint" };

export default function Users() {
  const [users, setUsers] = useState([]);
  const [dlg, setDlg] = useState(false);
  const [edit, setEdit] = useState(null);
  const [f, setF] = useState({});
  // reassignment popup state
  const [reassign, setReassign] = useState(null); // { user, assignments, picks:{key:new_user_id} }
  const [saving, setSaving] = useState(false);

  const load = () => api.get("/users").then((r) => setUsers(r.data));
  useEffect(() => { load(); }, []);

  const openNew = () => { setEdit(null); setF({ username: "", password: "", name: "", role: "LEAD", phone: "" }); setDlg(true); };
  const openEdit = (u) => { setEdit(u); setF({ name: u.name, role: u.role, phone: u.phone || "", password: "" }); setDlg(true); };

  const save = async () => {
    try {
      if (edit) {
        await api.patch(`/users/${edit.id}`, { name: f.name, role: f.role, phone: f.phone, password: f.password || undefined });
      } else {
        if (!f.phone || !f.phone.trim()) { toast.error("Phone number is required"); return; }
        await api.post("/users", f);
      }
      toast.success("Saved"); setDlg(false); load();
    } catch (e) { toast.error(apiError(e.response?.data?.detail)); }
  };

  const toggleActive = async (u) => {
    if (u.active) {
      // Deactivating: check for active/pending work first
      try {
        const { data } = await api.get(`/users/${u.id}/assignments`);
        if (data.count > 0) {
          setReassign({ user: u, assignments: data.assignments, picks: {} });
          return;
        }
        await api.patch(`/users/${u.id}`, { active: false });
        toast.success(`${u.name} deactivated`); load();
      } catch (e) { toast.error(apiError(e.response?.data?.detail)); }
    } else {
      try { await api.patch(`/users/${u.id}`, { active: true }); toast.success(`${u.name} reactivated`); load(); }
      catch (e) { toast.error(apiError(e.response?.data?.detail)); }
    }
  };

  const keyOf = (a) => `${a.type}:${a.id}`;
  const setPick = (a, v) => setReassign((r) => ({ ...r, picks: { ...r.picks, [keyOf(a)]: v } }));
  const allPicked = reassign && reassign.assignments.every((a) => reassign.picks[keyOf(a)]);

  const confirmReassign = async () => {
    if (!allPicked) { toast.error("Select a replacement user for every work item"); return; }
    setSaving(true);
    try {
      const reassignments = reassign.assignments.map((a) => ({ type: a.type, id: a.id, new_user_id: reassign.picks[keyOf(a)] }));
      await api.post(`/users/${reassign.user.id}/deactivate`, { reassignments });
      toast.success(`Work reassigned • ${reassign.user.name} deactivated`);
      setReassign(null); load();
    } catch (e) { toast.error(apiError(e.response?.data?.detail)); }
    finally { setSaving(false); }
  };

  return (
    <div>
      <PageHeader title="Users" subtitle="One user = one role = one team. Owner-managed."
        right={<Button data-testid="new-user-button" onClick={openNew} className="bg-sky-600 hover:bg-sky-700"><Plus size={16} className="mr-1" /> New User</Button>} />
      <div className="p-6 lg:p-8">
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <Table>
            <TableHeader className="bg-slate-50">
              <TableRow><TableHead>Name</TableHead><TableHead>Username</TableHead><TableHead>Phone</TableHead><TableHead>Role / Team</TableHead><TableHead>Active</TableHead><TableHead></TableHead></TableRow>
            </TableHeader>
            <TableBody>
              {users.map((u) => (
                <TableRow key={u.id} data-testid={`user-row-${u.id}`}>
                  <TableCell className="font-semibold">{u.name}</TableCell>
                  <TableCell className="font-mono text-sm">{u.username}</TableCell>
                  <TableCell className="text-sm">{u.phone || "—"}</TableCell>
                  <TableCell>{ROLE_LABELS[u.role]}</TableCell>
                  <TableCell><Switch data-testid={`user-active-${u.id}`} checked={u.active} onCheckedChange={() => toggleActive(u)} /></TableCell>
                  <TableCell><Button size="sm" variant="outline" data-testid={`edit-user-${u.id}`} onClick={() => openEdit(u)}>Edit</Button></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>

      <Dialog open={dlg} onOpenChange={setDlg}>
        <DialogContent>
          <DialogHeader><DialogTitle>{edit ? "Edit User" : "Create User"}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            {!edit && <div><Label>Username *</Label><Input data-testid="user-username-input" value={f.username || ""} onChange={(e) => setF({ ...f, username: e.target.value })} /></div>}
            <div><Label>Name *</Label><Input data-testid="user-name-input" value={f.name || ""} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
            <div><Label>Phone Number *</Label><Input data-testid="user-phone-input" value={f.phone || ""} onChange={(e) => setF({ ...f, phone: e.target.value })} /></div>
            <div><Label>Role / Team *</Label>
              <Select value={f.role} onValueChange={(v) => setF({ ...f, role: v })}>
                <SelectTrigger data-testid="user-role-select"><SelectValue /></SelectTrigger>
                <SelectContent>{(edit?.role === "INSTALLATION" ? ["INSTALLATION", ...ROLES] : ROLES).map((r) => <SelectItem key={r} value={r}>{ROLE_LABELS[r]}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label>Password {edit ? "(leave blank to keep)" : "*"}</Label><Input data-testid="user-password-input" type="password" value={f.password || ""} onChange={(e) => setF({ ...f, password: e.target.value })} /></div>
          </div>
          <DialogFooter><Button data-testid="user-save" onClick={save} className="bg-sky-600 hover:bg-sky-700">Save</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!reassign} onOpenChange={(o) => { if (!o) setReassign(null); }}>
        <DialogContent className="max-w-2xl" data-testid="reassign-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-amber-700"><AlertTriangle size={18} /> User has assigned work</DialogTitle>
          </DialogHeader>
          {reassign && (
            <div className="space-y-4">
              <p className="text-sm text-slate-600">
                <b>{reassign.user.name}</b> currently has <b>{reassign.assignments.length}</b> active assignment{reassign.assignments.length > 1 ? "s" : ""}.
                Please reassign each item to an eligible active user before deactivating this user.
              </p>
              <div className="max-h-[52vh] overflow-y-auto space-y-2 pr-1">
                {reassign.assignments.map((a) => (
                  <div key={keyOf(a)} data-testid={`reassign-row-${a.type}-${a.id}`} className="rounded-lg border border-slate-200 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{TYPE_LABELS[a.type] || a.type}</div>
                        <div className="font-semibold text-slate-800 truncate">{a.label}</div>
                        <div className="text-xs text-slate-500">{a.detail} · Currently: {a.current_user_name}</div>
                      </div>
                      <div className="w-52 shrink-0">
                        <Select value={reassign.picks[keyOf(a)] || ""} onValueChange={(v) => setPick(a, v)}>
                          <SelectTrigger data-testid={`reassign-select-${a.type}-${a.id}`}><SelectValue placeholder="Reassign to…" /></SelectTrigger>
                          <SelectContent>
                            {a.eligible_users.length === 0
                              ? <SelectItem value="__none" disabled>No eligible active user</SelectItem>
                              : a.eligible_users.map((u) => <SelectItem key={u.id} value={u.id}>{u.name} · {ROLE_LABELS[u.role] || u.role}</SelectItem>)}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" data-testid="reassign-cancel" onClick={() => setReassign(null)}>Cancel</Button>
            <Button data-testid="reassign-confirm" className="bg-sky-600 hover:bg-sky-700" disabled={!allPicked || saving} onClick={confirmReassign}>
              {saving ? "Reassigning…" : "Reassign & Deactivate"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

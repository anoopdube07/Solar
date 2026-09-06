import React, { useEffect, useState } from "react";
import api, { apiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/ui-bits";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";

export default function SiteVisits() {
  const { user } = useAuth();
  const [visits, setVisits] = useState([]);
  const [installers, setInstallers] = useState([]);
  const [assignDlg, setAssignDlg] = useState(null);
  const [completeDlg, setCompleteDlg] = useState(null);
  const [af, setAf] = useState({});
  const [survey, setSurvey] = useState("");

  const load = () => api.get("/site-visits").then((r) => setVisits(r.data));
  useEffect(() => {
    load();
    if (user.role === "MANAGER" || user.role === "OWNER") {
      api.get("/users/team/INSTALLATION").then((r) => setInstallers(r.data)).catch(() => {});
    }
  }, []);

  const canAssign = user.role === "MANAGER" || user.role === "OWNER";
  const canComplete = user.role === "INSTALLATION" || user.role === "OWNER";

  const doAssign = async () => {
    try { await api.post(`/site-visits/${assignDlg.id}/assign`, af); toast.success("Assigned"); setAssignDlg(null); setAf({}); load(); }
    catch (e) { toast.error(apiError(e.response?.data?.detail)); }
  };
  const doComplete = async () => {
    try { await api.post(`/site-visits/${completeDlg.id}/complete`, { survey_info: survey }); toast.success("Site visit completed"); setCompleteDlg(null); setSurvey(""); load(); }
    catch (e) { toast.error(apiError(e.response?.data?.detail)); }
  };

  return (
    <div>
      <PageHeader title="Site Visits" subtitle="Lead qualification site visits (not ECP installation)" />
      <div className="p-6 lg:p-8">
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <Table>
            <TableHeader className="bg-slate-50">
              <TableRow><TableHead>Lead</TableHead><TableHead>Status</TableHead><TableHead>Assigned To</TableHead><TableHead>Visit Date</TableHead><TableHead>Survey</TableHead><TableHead>Action</TableHead></TableRow>
            </TableHeader>
            <TableBody>
              {visits.map((v) => (
                <TableRow key={v.id} data-testid={`sv-row-${v.id}`}>
                  <TableCell className="font-semibold">{v.lead_name}</TableCell>
                  <TableCell><span className="text-xs font-semibold px-2 py-0.5 rounded-full border bg-slate-100">{v.status}</span></TableCell>
                  <TableCell className="text-sm">{v.assigned_user_name || "—"}</TableCell>
                  <TableCell className="text-sm">{v.visit_date?.slice(0, 10) || "—"}</TableCell>
                  <TableCell className="text-xs text-slate-500 max-w-[200px] truncate">{v.survey_info || "—"}</TableCell>
                  <TableCell>
                    {canAssign && (v.status === "REQUESTED" || v.status === "ASSIGNED") && <Button size="sm" data-testid={`assign-sv-${v.id}`} onClick={() => { setAssignDlg(v); setAf({ visit_date: "" }); }}>Assign</Button>}
                    {canComplete && v.status === "ASSIGNED" && <Button size="sm" className="ml-2 bg-emerald-600 hover:bg-emerald-700" data-testid={`complete-sv-${v.id}`} onClick={() => { setCompleteDlg(v); setSurvey(""); }}>Complete</Button>}
                  </TableCell>
                </TableRow>
              ))}
              {visits.length === 0 && <TableRow><TableCell colSpan={6} className="text-center text-slate-400 py-10">No site visits.</TableCell></TableRow>}
            </TableBody>
          </Table>
        </div>
      </div>

      <Dialog open={!!assignDlg} onOpenChange={(o) => !o && setAssignDlg(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Assign Site Visit</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>Installation Employee *</Label>
              <Select value={af.assigned_user} onValueChange={(v) => setAf({ ...af, assigned_user: v })}>
                <SelectTrigger data-testid="assign-employee-select"><SelectValue placeholder="Select employee" /></SelectTrigger>
                <SelectContent>{installers.map((u) => <SelectItem key={u.id} value={u.id}>{u.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label>Visit Date *</Label><Input data-testid="assign-date-input" type="date" value={af.visit_date || ""} onChange={(e) => setAf({ ...af, visit_date: e.target.value })} /></div>
          </div>
          <DialogFooter><Button data-testid="assign-submit" onClick={doAssign} className="bg-sky-600 hover:bg-sky-700">Assign</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!completeDlg} onOpenChange={(o) => !o && setCompleteDlg(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Complete Site Visit</DialogTitle></DialogHeader>
          <div><Label>Survey Information *</Label><Textarea data-testid="survey-info-input" value={survey} onChange={(e) => setSurvey(e.target.value)} placeholder="Roof condition, feasibility, notes…" /></div>
          <DialogFooter><Button data-testid="complete-submit" onClick={doComplete} className="bg-emerald-600 hover:bg-emerald-700">Mark Done · Return to Lead Team</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

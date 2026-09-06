import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api, { apiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/ui-bits";
import { StatusBadge } from "@/components/StatusBadge";
import { RETURN_REASON_LABELS } from "@/lib/constants";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CheckCircle2, XCircle, CalendarClock, MapPin, AlertTriangle, RotateCcw } from "lucide-react";
import { toast } from "sonner";

const LOST_REASONS = ["PRICE", "COMPETITOR", "NOT_INTERESTED", "UNREACHABLE", "OTHER"];

export default function LeadDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [dlg, setDlg] = useState(null); // YES|NO|FOLLOW_UP|SITE_VISIT|ESCALATION
  const [f, setF] = useState({});

  const load = () => api.get(`/leads/${id}`).then((r) => setData(r.data));
  useEffect(() => { load(); }, [id]);
  if (!data) return <div className="p-8 text-slate-500">Loading…</div>;

  const { lead, followups, site_visits, escalations, ecp } = data;
  const canAct = user.role === "LEAD" && lead.action_required;
  const canReopen = user.role === "OWNER" && lead.status === "LOST";

  const doAction = async (payload) => {
    try {
      await api.post(`/leads/${id}/action`, payload);
      toast.success("Lead updated");
      setDlg(null); setF({});
      load();
    } catch (e) { toast.error(apiError(e.response?.data?.detail)); }
  };

  const reopen = async () => {
    try { await api.post(`/leads/${id}/reopen`); toast.success("Lead reopened"); load(); }
    catch (e) { toast.error(apiError(e.response?.data?.detail)); }
  };

  const submit = () => {
    if (dlg === "YES") return doAction({ action: "YES" });
    if (dlg === "NO") return doAction({ action: "NO", lost_reason: f.lost_reason, lost_remarks: f.lost_remarks });
    if (dlg === "FOLLOW_UP") return doAction({ action: "FOLLOW_UP", followup_date: f.followup_date, remarks: f.remarks });
    if (dlg === "SITE_VISIT") return doAction({ action: "SITE_VISIT", remarks: f.remarks });
    if (dlg === "ESCALATION") return doAction({ action: "ESCALATION", reason: f.reason, remarks: f.remarks });
  };

  const actions = [
    ["YES", "Qualify (YES)", CheckCircle2, "bg-emerald-600 hover:bg-emerald-700"],
    ["NO", "Mark Lost (NO)", XCircle, "bg-slate-600 hover:bg-slate-700"],
    ["FOLLOW_UP", "Follow-up", CalendarClock, "bg-blue-600 hover:bg-blue-700"],
    ["SITE_VISIT", "Request Site Visit", MapPin, "bg-purple-600 hover:bg-purple-700"],
    ["ESCALATION", "Escalate to Owner", AlertTriangle, "bg-red-600 hover:bg-red-700"],
  ];

  return (
    <div>
      <PageHeader title={lead.name} subtitle={`${lead.phone} · ${lead.email || "no email"}`}
        right={<Button variant="secondary" onClick={() => nav("/leads")}>Back</Button>} />
      <div className="p-6 lg:p-8 grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* highlight box */}
          <Card className="p-5">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <Field label="Status"><StatusBadge value={lead.status} /></Field>
              <Field label="Current Team">{lead.current_team || "—"}</Field>
              <Field label="Action Required">{lead.action_required ? <span className="text-amber-600 font-semibold">YES</span> : "No"}</Field>
              <Field label="Financing">{lead.financing_required ? "Required" : "Not required"}</Field>
            </div>
            {lead.return_reason && (
              <div className="mt-4 text-sm bg-sky-50 border border-sky-200 rounded-md px-3 py-2 text-sky-800" data-testid="lead-return-reason">
                Returned to Lead Team · <b>{RETURN_REASON_LABELS[lead.return_reason]}</b>
              </div>
            )}
            {lead.status === "LOST" && (
              <div className="mt-4 text-sm bg-slate-50 border border-slate-200 rounded-md px-3 py-2 text-slate-700">
                Lost reason: <b>{lead.lost_reason}</b>{lead.lost_remarks ? ` — ${lead.lost_remarks}` : ""}
              </div>
            )}
          </Card>

          {/* actions */}
          {canAct && (
            <Card className="p-5">
              <h3 className="font-head font-semibold mb-3">Lead Team Actions</h3>
              <div className="flex flex-wrap gap-2">
                {actions.map(([key, label, Icon, cls]) => (
                  <Button key={key} data-testid={`lead-action-${key.toLowerCase()}`} className={`${cls} text-white`} onClick={() => { setDlg(key); setF({}); }}>
                    <Icon size={16} className="mr-1.5" /> {label}
                  </Button>
                ))}
              </div>
            </Card>
          )}
          {canReopen && (
            <Card className="p-5">
              <Button data-testid="lead-reopen-button" variant="outline" onClick={reopen}><RotateCcw size={16} className="mr-1.5" /> Reopen Lost Lead</Button>
            </Card>
          )}
          {ecp && (
            <Card className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-xs font-mono uppercase text-slate-500">Linked ECP Project</div>
                  <div className="font-semibold mt-1">{ecp.lead_name} · <StatusBadge value={ecp.current_stage} /></div>
                </div>
                <Button variant="outline" onClick={() => nav(`/ecps/${ecp.id}`)}>Open ECP</Button>
              </div>
            </Card>
          )}
        </div>

        {/* history */}
        <div className="space-y-6">
          <HistoryCard title="Follow-ups" items={followups} render={(x) => `${x.followup_date?.slice(0, 10)} — ${x.remarks}`} empty="No follow-ups" />
          <HistoryCard title="Site Visits" items={site_visits} render={(x) => `${x.status}${x.visit_date ? " · " + x.visit_date.slice(0, 10) : ""}${x.assigned_user_name ? " · " + x.assigned_user_name : ""}${x.survey_info ? " · " + x.survey_info : ""}`} empty="No site visits" />
          <HistoryCard title="Escalations" items={escalations} render={(x) => `${x.status} · ${x.reason}${x.owner_remarks ? " · Owner: " + x.owner_remarks : ""}`} empty="No escalations" />
        </div>
      </div>

      {/* action dialog */}
      <Dialog open={!!dlg} onOpenChange={(o) => !o && setDlg(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>{dlg && actions.find((a) => a[0] === dlg)?.[1]}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            {dlg === "YES" && <p className="text-sm text-slate-600">This will qualify the lead and automatically create one ECP project at Registration 1.</p>}
            {dlg === "NO" && (<>
              <div><Label>Lost Reason *</Label>
                <Select value={f.lost_reason} onValueChange={(v) => setF({ ...f, lost_reason: v })}>
                  <SelectTrigger data-testid="lost-reason-select"><SelectValue placeholder="Select reason" /></SelectTrigger>
                  <SelectContent>{LOST_REASONS.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div><Label>Remarks {f.lost_reason === "OTHER" && "*"}</Label><Textarea data-testid="lost-remarks-input" value={f.lost_remarks || ""} onChange={(e) => setF({ ...f, lost_remarks: e.target.value })} /></div>
            </>)}
            {dlg === "FOLLOW_UP" && (<>
              <div><Label>Follow-up Date *</Label><Input data-testid="followup-date-input" type="date" value={f.followup_date || ""} onChange={(e) => setF({ ...f, followup_date: e.target.value })} /></div>
              <div><Label>Remarks *</Label><Textarea data-testid="followup-remarks-input" value={f.remarks || ""} onChange={(e) => setF({ ...f, remarks: e.target.value })} /></div>
            </>)}
            {dlg === "SITE_VISIT" && (<>
              <p className="text-sm text-slate-600">A site visit request will be created for the Manager to assign an Installation employee.</p>
              <div><Label>Remarks</Label><Textarea data-testid="sitevisit-remarks-input" value={f.remarks || ""} onChange={(e) => setF({ ...f, remarks: e.target.value })} /></div>
            </>)}
            {dlg === "ESCALATION" && (<>
              <div><Label>Reason *</Label><Input data-testid="escalation-reason-input" value={f.reason || ""} onChange={(e) => setF({ ...f, reason: e.target.value })} /></div>
              <div><Label>Remarks *</Label><Textarea data-testid="escalation-remarks-input" value={f.remarks || ""} onChange={(e) => setF({ ...f, remarks: e.target.value })} /></div>
            </>)}
          </div>
          <DialogFooter><Button data-testid="lead-action-submit" onClick={submit} className="bg-sky-600 hover:bg-sky-700">Confirm</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Field({ label, children }) {
  return <div><div className="text-xs font-mono uppercase tracking-wider text-slate-500">{label}</div><div className="mt-1 font-medium text-slate-900">{children}</div></div>;
}
function HistoryCard({ title, items, render, empty }) {
  return (
    <Card className="p-5">
      <h3 className="font-head font-semibold mb-3">{title}</h3>
      <ul className="space-y-2">
        {items.length === 0 && <li className="text-sm text-slate-400">{empty}</li>}
        {items.map((x) => <li key={x.id} className="text-sm text-slate-700 border-l-2 border-slate-200 pl-3">{render(x)}</li>)}
      </ul>
    </Card>
  );
}

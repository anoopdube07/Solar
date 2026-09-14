import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, StatCard } from "@/components/ui-bits";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Download, GitPullRequestArrow, ShieldAlert, Ban, Clock, ChevronRight, FileText, Truck, Wrench, CheckCircle2, IndianRupee } from "lucide-react";

function AttentionTile({ icon: Icon, label, value, onClick, tone = "amber", testid }) {
  const tones = {
    red: "bg-red-50 border-red-200 text-red-700 hover:border-red-400",
    amber: "bg-amber-50 border-amber-200 text-amber-700 hover:border-amber-400",
    indigo: "bg-indigo-50 border-indigo-200 text-indigo-700 hover:border-indigo-400",
  };
  return (
    <button data-testid={testid} onClick={onClick}
      className={`flex items-center gap-4 rounded-xl border p-4 text-left transition-all hover:shadow-md hover:-translate-y-0.5 ${tones[tone]}`}>
      <div className="shrink-0 rounded-lg bg-white/70 p-2.5"><Icon size={22} /></div>
      <div>
        <div className="text-3xl font-black font-head leading-none text-slate-900">{value ?? 0}</div>
        <div className="text-[11px] font-semibold uppercase tracking-wide mt-1.5">{label}</div>
      </div>
    </button>
  );
}

function Section({ title, hint, children }) {
  return (
    <div>
      <div className="flex items-baseline gap-3 mb-3">
        <h2 className="font-head text-lg font-bold text-slate-800">{title}</h2>
        {hint && <span className="text-xs text-slate-400">{hint}</span>}
      </div>
      {children}
    </div>
  );
}

function OwnerCommandCenter({ d, go, onReviewCommercial, pendingCommCount }) {
  const ecp = d.ecp || {};
  const leads = d.leads || {};
  const pay = d.payments || {};

  const kpis = [
    ["Active ECP Projects", ecp.ACTIVE, "sky", go("/ecps")],
    ["Pending Leads", leads.PENDING, "amber", go("/leads?status=PENDING")],
    ["Qualified Leads", leads.QUALIFIED, "emerald", go("/leads?status=QUALIFIED")],
    ["Payment Blocked", ecp.PAYMENT_BLOCKED, "red", go("/ecps?stage=DISPATCH")],
    ["Delayed", ecp.DELAYED, "red", go("/ecps")],
    ["Successfully Completed", ecp.COMPLETED, "emerald", go("/ecps")],
  ];

  const pipeline = [
    ["Pending", leads.PENDING, "amber", go("/leads?status=PENDING")],
    ["Follow-up", leads.FOLLOW_UP, "sky", go("/leads?status=FOLLOW_UP")],
    ["Site Visit", leads.SITE_VISIT, "indigo", go("/leads?status=SITE_VISIT")],
    ["Escalated", leads.ESCALATED, "red", go("/leads?status=ESCALATED")],
    ["Qualified", leads.QUALIFIED, "emerald", go("/leads?status=QUALIFIED")],
  ];

  const ecpGroups = [
    ["Registration", FileText, [
      ["Pending Documents", ecp.PENDING_DOCUMENTS, "amber", go("/ecps?stage=PENDING_DOCUMENTS")],
      ["Registration 1", ecp.REGISTRATION_1, "slate", go("/ecps?stage=REGISTRATION_1")],
      ["Accounts 1", ecp.ACCOUNTS_1, "slate", go("/ecps?stage=ACCOUNTS_1")],
    ]],
    ["Dispatch", Truck, [
      ["Payment Blocked", ecp.PAYMENT_BLOCKED, "red", go("/ecps?stage=DISPATCH")],
      ["Ready for Dispatch", ecp.READY_FOR_DISPATCH, "teal", go("/ecps?stage=DISPATCH")],
      ["Dispatch In Process", ecp.DISPATCH_IN_PROCESS, "indigo", go("/ecps?stage=DISPATCH")],
    ]],
    ["Installation", Wrench, [
      ["Ready to Install", ecp.READY_TO_INSTALL, "teal", go("/ecps?stage=INSTALLATION")],
      ["Installation In Process", ecp.INSTALLATION_IN_PROCESS, "indigo", go("/ecps?stage=INSTALLATION")],
    ]],
    ["Completion", CheckCircle2, [
      ["Net Metering", ecp.NET_METERING, "slate", go("/ecps?stage=NET_METERING")],
      ["Registration 2", ecp.REGISTRATION_2, "slate", go("/ecps?stage=REGISTRATION_2")],
      ["Accounts 2", ecp.ACCOUNTS_2, "slate", go("/ecps?stage=ACCOUNTS_2")],
      ["Successfully Completed", ecp.COMPLETED, "emerald", go("/ecps")],
      ["Closed / Cancelled", ecp.CLOSED, "slate", go("/ecps")],
    ]],
  ];

  const payments = [
    ["First Pending", pay.FIRST_PENDING, "amber", go("/payments")],
    ["First Confirmed", pay.FIRST_CONFIRMED, "emerald", go("/payments")],
    ["Subsequent / Additional", pay.ADDITIONAL, "slate", go("/payments")],
  ];

  return (
    <div className="space-y-8" data-testid="owner-command-center">
      {/* ATTENTION REQUIRED */}
      <Section title="Attention Required" hint="Act on these first">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <AttentionTile testid="attn-commercial" icon={GitPullRequestArrow} tone="indigo" label="Commercial Approvals"
            value={pendingCommCount} onClick={onReviewCommercial} />
          <AttentionTile testid="attn-escalated" icon={ShieldAlert} tone="red" label="Escalated Leads"
            value={leads.ESCALATED} onClick={go("/leads?status=ESCALATED")} />
          <AttentionTile testid="attn-payment-blocked" icon={Ban} tone="red" label="Payment Blocked"
            value={ecp.PAYMENT_BLOCKED} onClick={go("/ecps?stage=DISPATCH")} />
          <AttentionTile testid="attn-delayed" icon={Clock} tone="amber" label="Delayed Projects"
            value={ecp.DELAYED} onClick={go("/ecps")} />
        </div>
      </Section>

      {/* EXECUTIVE KPI ROW */}
      <Section title="Business Overview">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {kpis.map(([label, value, tone, onClick]) => (
            <StatCard key={label} label={label} value={value} tone={tone} onClick={onClick}
              testid={`kpi-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`} />
          ))}
        </div>
      </Section>

      {/* LEAD PIPELINE */}
      <Section title="Lead Pipeline" hint="Pending → Follow-up → Site Visit → Escalated → Qualified">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap items-stretch gap-2">
            {pipeline.map(([label, value, tone, onClick], i) => (
              <React.Fragment key={label}>
                <button data-testid={`pipeline-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`} onClick={onClick}
                  className="flex-1 min-w-[130px] text-left rounded-lg border border-slate-100 hover:border-sky-300 hover:shadow-sm transition-all p-3">
                  <div className={`text-[11px] font-mono uppercase tracking-wider ${tone === "red" ? "text-red-500" : "text-slate-500"}`}>{label}</div>
                  <div className="text-2xl font-black font-head text-slate-900 mt-1">{value ?? 0}</div>
                </button>
                {i < pipeline.length - 1 && (
                  <div className="hidden md:flex items-center text-slate-300"><ChevronRight size={18} /></div>
                )}
              </React.Fragment>
            ))}
            <div className="hidden lg:flex items-center px-1"><div className="h-10 w-px bg-slate-200" /></div>
            <button data-testid="pipeline-lost" onClick={go("/leads?status=LOST")}
              className="min-w-[120px] text-left rounded-lg border border-slate-200 bg-slate-50 hover:border-slate-400 transition-all p-3">
              <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400">Lost</div>
              <div className="text-2xl font-black font-head text-slate-500 mt-1">{leads.LOST ?? 0}</div>
            </button>
          </div>
        </div>
      </Section>

      {/* ECP OPERATIONS */}
      <Section title="ECP Operations" hint="Where every active project stands">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {ecpGroups.map(([group, Icon, cards]) => (
            <div key={group} className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex items-center gap-2 mb-3 text-slate-700">
                <Icon size={16} className="text-sky-600" />
                <h3 className="font-head font-bold text-sm uppercase tracking-wide">{group}</h3>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {cards.map(([label, value, tone, onClick]) => (
                  <StatCard key={label} label={label} value={value} tone={tone} onClick={onClick}
                    testid={`ecp-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* PAYMENTS */}
      <Section title="Payments">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex items-center gap-2 mb-3 text-slate-700">
            <IndianRupee size={16} className="text-emerald-600" />
            <h3 className="font-head font-bold text-sm uppercase tracking-wide">Collection Status</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {payments.map(([label, value, tone, onClick]) => (
              <StatCard key={label} label={label} value={value} tone={tone} onClick={onClick}
                testid={`pay-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`} />
            ))}
          </div>
        </div>
      </Section>
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const nav = useNavigate();
  const [d, setD] = useState(null);
  const [pendingComm, setPendingComm] = useState([]);
  const [exportDlg, setExportDlg] = useState(false);
  const [inclMoney, setInclMoney] = useState(false);

  useEffect(() => { api.get("/dashboard").then((r) => setD(r.data)); }, []);
  useEffect(() => {
    if (user.role === "OWNER") api.get("/commercial-changes/pending").then((r) => setPendingComm(r.data)).catch(() => {});
  }, [user.role]);
  if (!d) return <div className="p-8 text-slate-500">Loading…</div>;

  const go = (path) => () => nav(path);
  const isOwner = user.role === "OWNER";
  const reviewCommercial = () => { if (pendingComm.length) nav(`/leads/${pendingComm[0].id}`); };

  const downloadCsv = async () => {
    try {
      const res = await api.get(`/export/projects?include_money=${inclMoney}`, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url; a.download = "projects.csv"; a.click();
      window.URL.revokeObjectURL(url);
      setExportDlg(false);
    } catch (e) { /* owner-only enforced server-side */ }
  };

  // ---- Non-owner role sections (unchanged) ----
  const sections = [];
  if (user.role === "MANAGER") {
    sections.push(["Operations", [
      ["Site Visits To Assign", d.site_visits_to_assign, "amber", go("/site-visits?status=REQUESTED")],
      ["Today's Site Visits", d.site_visits_today, "sky", go("/site-visits?status=ASSIGNED")],
      ["Upcoming Site Visits", d.site_visits_upcoming, "indigo", go("/site-visits?status=ASSIGNED")],
      ["Awaiting Install Assignment", d.awaiting_install_assignment, "amber", go("/ecps?view=AWAITING_ASSIGNMENT")],
      ["Delayed Projects", d.delayed, "red", go("/ecps")],
      ["Active Leads", d.active_leads, "slate", go("/leads")],
      ["Active ECPs", d.active_ecps, "sky", go("/ecps")],
    ]]);
  } else if (user.role === "LEAD") {
    sections.push(["My Lead Queue", [
      ["Action Required", d.action_required, "amber", go("/leads?status=PENDING")],
      ["Follow-ups Today", d.followups_today, "sky", go("/leads?followup=today")],
      ["Waiting for Site Visit", d.waiting_site_visit, "indigo", go("/leads?status=SITE_VISIT")],
      ["Escalated", d.escalated, "red", go("/leads?status=ESCALATED")],
      ["Qualified", d.qualified, "emerald", go("/leads?status=QUALIFIED")],
      ["Awaiting Documents", d.pending_documents, "amber", go("/leads?status=QUALIFIED")],
      ["Lost", d.lost, "slate", go("/leads?status=LOST")],
    ]]);
  } else if (user.role === "ACCOUNTS") {
    const fmt = (n) => "₹" + Number(n || 0).toLocaleString("en-IN");
    sections.push(["Receivables", [
      ["First Payment Pending", `${d.first_payment_pending_count} Projects`, "amber", go("/payments?view=first_pending")],
      ["Total Receivable", fmt(d.total_receivable), "red", go("/payments?view=receivable")],
    ]]);
  } else if (user.role === "DISPATCH") {
    sections.push(["Dispatch Hub", [
      ["Payment Blocked", d.payment_blocked, "red", go("/ecps?view=PAYMENT_BLOCKED")],
      ["Ready for Dispatch", d.ready_for_dispatch, "teal", go("/ecps?view=READY_FOR_DISPATCH")],
      ["Dispatch In Process", d.dispatch_in_process, "indigo", go("/ecps?view=DISPATCH_IN_PROCESS")],
      ["Delivered / Past Dispatch", d.completed, "emerald", go("/ecps?view=PAST_DISPATCH")],
    ]]);
  } else if (user.role === "INSTALLATION") {
    sections.push(["Lead Site Visits", [
      ["Upcoming", d.sv_upcoming, "indigo", go("/site-visits")],
      ["Today", d.sv_today, "sky", go("/site-visits")],
      ["Assigned to Me", d.sv_assigned, "amber", go("/site-visits")],
      ["Completed", d.sv_completed, "emerald", go("/site-visits")],
    ]]);
    sections.push(["ECP Installation", [
      ["Ready to Install", d.ready_to_install, "teal", go("/ecps?view=READY_TO_INSTALL")],
      ["In Process", d.installation_in_process, "indigo", go("/ecps?view=IN_PROCESS")],
      ["Net Metering", d.net_metering, "slate", go("/ecps?stage=NET_METERING")],
    ]]);
  } else if (user.role === "REGISTRATION") {
    sections.push(["Registration", [
      ["Awaiting Documents", d.pending_documents, "amber", () => {}],
      ["Registration 1", d.registration_1, "sky", go("/ecps?stage=REGISTRATION_1")],
      ["Registration 2", d.registration_2, "sky", go("/ecps?stage=REGISTRATION_2")],
      ["Pending Total", d.pending, "amber", go("/ecps")],
    ]]);
  } else if (user.role === "INSTALLATION_MANAGER") {
    sections.push(["Installation Supervision", [
      ["Awaiting Assignment", d.awaiting_assignment, "amber", go("/ecps?view=READY_TO_INSTALL")],
      ["In Process", d.install_in_process, "indigo", go("/ecps?view=IN_PROCESS")],
      ["Pending Acceptance", d.pending_acceptance, "red", go("/ecps?view=IN_PROCESS")],
      ["Net Metering", d.net_metering, "slate", go("/ecps?stage=NET_METERING")],
    ]]);
    sections.push(["Site Visit Supervision", [
      ["Awaiting Assignment", d.sv_awaiting, "amber", go("/site-visits?status=REQUESTED")],
      ["In Process", d.sv_in_process, "indigo", go("/site-visits?status=ASSIGNED")],
    ]]);
  } else if (user.role === "INSTALLATION_MEMBER") {
    sections.push(["My Installations", [
      ["Ready to Install", d.ready_to_install, "teal", go("/ecps?view=READY_TO_INSTALL")],
      ["In Process", d.install_in_process, "indigo", go("/ecps?view=IN_PROCESS")],
      ["Pending Acceptance", d.pending_acceptance, "amber", go("/ecps?view=IN_PROCESS")],
    ]]);
    sections.push(["My Site Visits", [
      ["Assigned to Me", d.sv_assigned, "amber", go("/site-visits?status=ASSIGNED")],
      ["Due Today", d.sv_today, "sky", go("/site-visits?status=ASSIGNED")],
      ["Completed", d.sv_completed, "emerald", go("/site-visits?status=DONE")],
    ]]);
  } else if (user.role === "COMPLAINT") {
    sections.push(["Complaint Register", [
      ["Registered", d.registered, "amber", go("/complaints?status=REGISTERED")],
      ["Assigned", d.assigned, "sky", go("/complaints?status=ASSIGNED")],
      ["In Progress", d.in_progress, "indigo", go("/complaints?status=IN_PROGRESS")],
      ["Critical (open)", d.critical, "red", go("/complaints?priority=CRITICAL")],
      ["Due Today", d.due_today, "amber", go("/complaints")],
      ["Overdue", d.overdue, "red", go("/complaints")],
    ]]);
  }

  return (
    <div>
      <PageHeader
        title={isOwner ? "Owner Command Center" : `${d.role_label} Dashboard`}
        subtitle={isOwner ? "Business overview • Operations • Attention required" : "Click any counter to drill down into the records."}
        right={isOwner ? (
          <Dialog open={exportDlg} onOpenChange={setExportDlg}>
            <DialogTrigger asChild><Button data-testid="export-csv-button" className="bg-white/10 hover:bg-white/20 text-white"><Download size={16} className="mr-1.5" /> Export CSV</Button></DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>Export Customer & Project Status</DialogTitle></DialogHeader>
              <div className="flex items-center gap-2 py-2">
                <Checkbox id="money" data-testid="export-money-checkbox" checked={inclMoney} onCheckedChange={(v) => setInclMoney(!!v)} />
                <Label htmlFor="money">Also Include Monetary Values</Label>
              </div>
              <DialogFooter><Button data-testid="export-download-button" onClick={downloadCsv} className="bg-sky-600 hover:bg-sky-700">Download CSV</Button></DialogFooter>
            </DialogContent>
          </Dialog>
        ) : user.role === "COMPLAINT" ? (
          <Button data-testid="dashboard-register-complaint" className="bg-white text-slate-900 hover:bg-white/90 font-semibold" onClick={() => nav("/complaints?new=1")}>+ Register Complaint</Button>
        ) : null} />
      <div className="p-6 lg:p-8 space-y-8">
        {isOwner && pendingComm.length > 0 && (
          <div data-testid="pending-commercial-banner" className="rounded-lg border border-amber-300 bg-amber-50 px-5 py-4 flex items-center justify-between">
            <div>
              <div className="font-head font-bold text-amber-800">{pendingComm.length} Commercial Change{pendingComm.length > 1 ? "s" : ""} awaiting your approval</div>
              <div className="text-sm text-amber-700 mt-0.5">{pendingComm.map((l) => l.name).slice(0, 4).join(", ")}{pendingComm.length > 4 ? "…" : ""}</div>
            </div>
            <Button data-testid="pending-commercial-review" className="bg-amber-600 hover:bg-amber-700 text-white" onClick={() => nav(`/leads/${pendingComm[0].id}`)}>Review</Button>
          </div>
        )}
        {isOwner ? (
          <OwnerCommandCenter d={d} go={go} onReviewCommercial={reviewCommercial} pendingCommCount={pendingComm.length} />
        ) : (
          sections.map(([title, cards]) => (
            <div key={title}>
              <h2 className="font-head text-lg font-bold text-slate-800 mb-3">{title}</h2>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
                {cards.map(([label, value, tone, onClick]) => (
                  <StatCard key={label} label={label} value={value} tone={tone} onClick={onClick}
                    testid={`stat-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`} />
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

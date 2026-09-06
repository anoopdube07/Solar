import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, StatCard } from "@/components/ui-bits";

export default function Dashboard() {
  const { user } = useAuth();
  const nav = useNavigate();
  const [d, setD] = useState(null);

  useEffect(() => { api.get("/dashboard").then((r) => setD(r.data)); }, []);
  if (!d) return <div className="p-8 text-slate-500">Loading…</div>;

  const go = (path) => () => nav(path);

  const sections = [];
  if (user.role === "OWNER") {
    sections.push(["Leads", [
      ["Pending", d.leads.PENDING, "amber", go("/leads?status=PENDING")],
      ["Follow-up", d.leads.FOLLOW_UP, "sky", go("/leads?status=FOLLOW_UP")],
      ["Site Visit", d.leads.SITE_VISIT, "indigo", go("/leads?status=SITE_VISIT")],
      ["Escalated", d.leads.ESCALATED, "red", go("/leads?status=ESCALATED")],
      ["Qualified", d.leads.QUALIFIED, "emerald", go("/leads?status=QUALIFIED")],
      ["Lost", d.leads.LOST, "slate", go("/leads?status=LOST")],
    ]]);
    sections.push(["ECP Projects", [
      ["Active", d.ecp.ACTIVE, "sky", go("/ecps")],
      ["Registration 1", d.ecp.REGISTRATION_1, "slate", go("/ecps?stage=REGISTRATION_1")],
      ["Accounts 1", d.ecp.ACCOUNTS_1, "slate", go("/ecps?stage=ACCOUNTS_1")],
      ["Payment Blocked", d.ecp.PAYMENT_BLOCKED, "red", go("/ecps?stage=DISPATCH")],
      ["Ready for Dispatch", d.ecp.READY_FOR_DISPATCH, "teal", go("/ecps?stage=DISPATCH")],
      ["Dispatch In Process", d.ecp.DISPATCH_IN_PROCESS, "indigo", go("/ecps?stage=DISPATCH")],
      ["Ready to Install", d.ecp.READY_TO_INSTALL, "teal", go("/ecps?stage=INSTALLATION")],
      ["Installation In Process", d.ecp.INSTALLATION_IN_PROCESS, "indigo", go("/ecps?stage=INSTALLATION")],
      ["Net Metering", d.ecp.NET_METERING, "slate", go("/ecps?stage=NET_METERING")],
      ["Registration 2", d.ecp.REGISTRATION_2, "slate", go("/ecps?stage=REGISTRATION_2")],
      ["Accounts 2", d.ecp.ACCOUNTS_2, "slate", go("/ecps?stage=ACCOUNTS_2")],
      ["Delayed", d.ecp.DELAYED, "red", go("/ecps")],
      ["Successfully Completed", d.ecp.COMPLETED, "emerald", go("/ecps")],
      ["Closed / Cancelled", d.ecp.CLOSED, "slate", go("/ecps")],
    ]]);
    sections.push(["Payments", [
      ["First Pending", d.payments.FIRST_PENDING, "amber", go("/payments")],
      ["First Confirmed", d.payments.FIRST_CONFIRMED, "emerald", go("/payments")],
      ["Final Pending", d.payments.FINAL_PENDING, "amber", go("/payments")],
      ["Final Confirmed", d.payments.FINAL_CONFIRMED, "emerald", go("/payments")],
      ["Additional", d.payments.ADDITIONAL, "slate", go("/payments")],
    ]]);
  } else if (user.role === "MANAGER") {
    sections.push(["Operations", [
      ["Site Visits To Assign", d.site_visits_to_assign, "amber", go("/site-visits")],
      ["Today's Site Visits", d.site_visits_today, "sky", go("/site-visits")],
      ["Upcoming Site Visits", d.site_visits_upcoming, "indigo", go("/site-visits")],
      ["Awaiting Install Assignment", d.awaiting_install_assignment, "amber", go("/ecps?view=AWAITING_ASSIGNMENT")],
      ["Delayed Projects", d.delayed, "red", go("/ecps")],
      ["Active Leads", d.active_leads, "slate", go("/leads")],
      ["Active ECPs", d.active_ecps, "sky", go("/ecps")],
    ]]);
  } else if (user.role === "LEAD") {
    sections.push(["My Lead Queue", [
      ["Action Required", d.action_required, "amber", go("/leads")],
      ["Follow-ups Today", d.followups_today, "sky", go("/leads?status=FOLLOW_UP")],
      ["Waiting for Site Visit", d.waiting_site_visit, "indigo", go("/leads?status=SITE_VISIT")],
      ["Escalated", d.escalated, "red", go("/leads?status=ESCALATED")],
      ["Qualified", d.qualified, "emerald", go("/leads?status=QUALIFIED")],
      ["Lost", d.lost, "slate", go("/leads?status=LOST")],
    ]]);
  } else if (user.role === "ACCOUNTS") {
    const fmt = (n) => "₹" + Number(n || 0).toLocaleString("en-IN");
    sections.push(["Receivables", [
      ["First Payment Pending", `${d.first_payment_pending_count} Projects`, "amber", go("/payments")],
      ["Subsequent Payment Follow-up", `${d.subsequent_followup_count} Projects`, "sky", go("/payments")],
      ["Subsequent Amount Pending", fmt(d.subsequent_amount_pending), "indigo", go("/payments")],
      ["Total Receivable", fmt(d.total_receivable), "red", go("/payments")],
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
      ["Registration 1", d.registration_1, "sky", go("/ecps?stage=REGISTRATION_1")],
      ["Registration 2", d.registration_2, "sky", go("/ecps?stage=REGISTRATION_2")],
      ["Pending Total", d.pending, "amber", go("/ecps")],
    ]]);
  }

  return (
    <div>
      <PageHeader title={`${d.role_label} Dashboard`} subtitle="Click any counter to drill down into the records." />
      <div className="p-6 lg:p-8 space-y-8">
        {sections.map(([title, cards]) => (
          <div key={title}>
            <h2 className="font-head text-lg font-bold text-slate-800 mb-3">{title}</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
              {cards.map(([label, value, tone, onClick]) => (
                <StatCard key={label} label={label} value={value} tone={tone} onClick={onClick}
                  testid={`stat-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

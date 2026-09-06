import React, { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import api from "@/lib/api";
import { PageHeader } from "@/components/ui-bits";
import { StatusBadge, DelayedBadge } from "@/components/StatusBadge";
import { STAGE_LABELS } from "@/lib/constants";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Search } from "lucide-react";

export default function ECPs() {
  const nav = useNavigate();
  const loc = useLocation();
  const stageParam = new URLSearchParams(loc.search).get("stage") || "";
  const [ecps, setEcps] = useState([]);
  const [q, setQ] = useState("");

  useEffect(() => {
    const url = stageParam ? `/ecps?stage=${stageParam}` : "/ecps";
    api.get(url).then((r) => setEcps(r.data));
  }, [stageParam]);

  const filtered = ecps.filter((e) => !q || e.lead_name.toLowerCase().includes(q.toLowerCase()));

  return (
    <div>
      <PageHeader title="ECP Projects" subtitle="Execution workflow tracking" />
      <div className="p-6 lg:p-8">
        <div className="flex items-center gap-3 mb-4">
          <div className="relative flex-1 max-w-sm">
            <Search size={16} className="absolute left-3 top-2.5 text-slate-400" />
            <Input data-testid="ecp-search" className="pl-9" placeholder="Search customer…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          {stageParam && <StatusBadge value={stageParam} />}
          {stageParam && <button className="text-xs text-sky-600 underline" onClick={() => nav("/ecps")}>clear</button>}
        </div>
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <Table>
            <TableHeader className="bg-slate-50">
              <TableRow>
                <TableHead>Customer</TableHead><TableHead>Stage</TableHead><TableHead>Status</TableHead>
                <TableHead>Current Team</TableHead><TableHead>Days in Stage</TableHead><TableHead>Flags</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((e) => (
                <TableRow key={e.id} data-testid={`ecp-row-${e.id}`} className="hover:bg-slate-50 cursor-pointer" onClick={() => nav(`/ecps/${e.id}`)}>
                  <TableCell className="font-semibold text-slate-900">{e.lead_name}</TableCell>
                  <TableCell><StatusBadge value={e.current_stage} /></TableCell>
                  <TableCell>
                    {e.derived_status ? <StatusBadge value={e.derived_status} /> :
                      <StatusBadge value={e.status} />}
                  </TableCell>
                  <TableCell className="text-sm">{e.current_team || "—"}</TableCell>
                  <TableCell className="text-sm font-mono">{e.days_in_stage ?? "—"}</TableCell>
                  <TableCell className="space-x-1">
                    {e.delayed && <DelayedBadge />}
                    {!e.first_payment_confirmed && e.status === "ACTIVE" && <span className="text-[10px] text-rose-600 font-semibold">FIRST PAY ✗</span>}
                  </TableCell>
                </TableRow>
              ))}
              {filtered.length === 0 && <TableRow><TableCell colSpan={6} className="text-center text-slate-400 py-10">No ECP projects.</TableCell></TableRow>}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  );
}

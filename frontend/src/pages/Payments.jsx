import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { apiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/ui-bits";
import { StatusBadge } from "@/components/StatusBadge";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";

export default function Payments() {
  const { user } = useAuth();
  const nav = useNavigate();
  const [rows, setRows] = useState([]);
  const [dlg, setDlg] = useState(false);
  const [edit, setEdit] = useState(null);
  const [f, setF] = useState({});

  const canEdit = user.role === "ACCOUNTS";
  const load = () => api.get("/payments/monitor").then((r) => setRows(r.data));
  useEffect(() => { load(); }, []);

  const openNew = (ecpId) => { setEdit(null); setF({ ecp_id: ecpId, type: "FIRST", status: "PENDING", amount: "", date: "", remarks: "" }); setDlg(true); };
  const openEdit = (p) => { setEdit(p); setF({ ...p }); setDlg(true); };

  const save = async () => {
    try {
      if (edit) {
        await api.patch(`/payments/${edit.id}`, { amount: parseFloat(f.amount), date: f.date, status: f.status, remarks: f.remarks });
      } else {
        await api.post("/payments", { ...f, amount: parseFloat(f.amount) });
      }
      toast.success("Payment saved"); setDlg(false); load();
    } catch (e) { toast.error(apiError(e.response?.data?.detail)); }
  };

  return (
    <div>
      <PageHeader title="Payment Monitor" subtitle="Payments are independent of ECP stage. Only Accounts can create/update." />
      <div className="p-6 lg:p-8 space-y-4">
        {rows.map((r) => (
          <Card key={r.ecp_id} className="p-5" data-testid={`pay-ecp-${r.ecp_id}`}>
            <div className="flex items-center justify-between mb-3">
              <div>
                <button className="font-semibold text-sky-700 hover:underline" onClick={() => nav(`/ecps/${r.ecp_id}`)}>{r.lead_name}</button>
                <span className="ml-2"><StatusBadge value={r.stage} /></span>
              </div>
              {canEdit && r.status === "ACTIVE" && <Button size="sm" data-testid={`add-payment-${r.ecp_id}`} onClick={() => openNew(r.ecp_id)}>+ Payment</Button>}
            </div>
            <Table>
              <TableHeader className="bg-slate-50">
                <TableRow><TableHead>Type</TableHead><TableHead>Amount</TableHead><TableHead>Date</TableHead><TableHead>Status</TableHead><TableHead>Updated By</TableHead>{canEdit && <TableHead></TableHead>}</TableRow>
              </TableHeader>
              <TableBody>
                {r.payments.length === 0 && <TableRow><TableCell colSpan={6} className="text-slate-400 text-sm py-4">No payments</TableCell></TableRow>}
                {r.payments.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-semibold">{p.type}</TableCell>
                    <TableCell>₹{p.amount}</TableCell>
                    <TableCell>{p.date?.slice(0, 10)}</TableCell>
                    <TableCell><StatusBadge value={p.status} kind={p.status === "CONFIRMED" ? "CONFIRMED" : "PENDING"} label={p.status} /></TableCell>
                    <TableCell className="text-xs text-slate-500">{p.updated_by_name}</TableCell>
                    {canEdit && <TableCell><Button size="sm" variant="outline" data-testid={`edit-payment-${p.id}`} onClick={() => openEdit(p)}>Edit</Button></TableCell>}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        ))}
        {rows.length === 0 && <div className="text-slate-400">No ECP projects yet.</div>}
      </div>

      <Dialog open={dlg} onOpenChange={setDlg}>
        <DialogContent>
          <DialogHeader><DialogTitle>{edit ? "Edit Payment" : "New Payment"}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            {!edit && (
              <div><Label>Type *</Label>
                <Select value={f.type} onValueChange={(v) => setF({ ...f, type: v })}>
                  <SelectTrigger data-testid="payment-type-select"><SelectValue /></SelectTrigger>
                  <SelectContent>{["FIRST", "ADDITIONAL", "FINAL"].map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            )}
            <div><Label>Amount *</Label><Input data-testid="payment-amount-input" type="number" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} /></div>
            <div><Label>Date *</Label><Input data-testid="payment-date-input" type="date" value={(f.date || "").slice(0, 10)} onChange={(e) => setF({ ...f, date: e.target.value })} /></div>
            <div><Label>Status *</Label>
              <Select value={f.status} onValueChange={(v) => setF({ ...f, status: v })}>
                <SelectTrigger data-testid="payment-status-select"><SelectValue /></SelectTrigger>
                <SelectContent>{["PENDING", "CONFIRMED"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label>Remarks</Label><Textarea value={f.remarks || ""} onChange={(e) => setF({ ...f, remarks: e.target.value })} /></div>
          </div>
          <DialogFooter><Button data-testid="payment-save" onClick={save} className="bg-sky-600 hover:bg-sky-700">Save</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

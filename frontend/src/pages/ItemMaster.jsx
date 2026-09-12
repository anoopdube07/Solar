import React, { useEffect, useState } from "react";
import api, { apiError, API } from "@/lib/api";
import { PageHeader } from "@/components/ui-bits";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Plus, Download, Upload } from "lucide-react";
import { toast } from "sonner";

export default function ItemMaster() {
  const [items, setItems] = useState([]);
  const [dlg, setDlg] = useState(false);
  const [f, setF] = useState({ name: "", unit: "" });
  const load = () => api.get("/items").then((r) => setItems(r.data));
  useEffect(() => { load(); }, []);

  const save = async () => {
    try { await api.post("/items", f); toast.success("Item added"); setDlg(false); setF({ name: "", unit: "" }); load(); }
    catch (e) { toast.error(apiError(e.response?.data?.detail)); }
  };
  const toggle = async (it) => { try { await api.patch(`/items/${it.id}`, { active: !it.active }); load(); } catch (e) { toast.error(apiError(e.response?.data?.detail)); } };

  const exportCsv = async () => {
    const res = await api.get("/items/export", { responseType: "blob" });
    const url = window.URL.createObjectURL(new Blob([res.data])); const a = document.createElement("a");
    a.href = url; a.download = "items.csv"; a.click(); window.URL.revokeObjectURL(url);
  };
  const importCsv = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    const text = await file.text();
    const lines = text.split(/\r?\n/).filter((l) => l.trim());
    const rows = lines.slice(1).map((l) => { const [name, unit] = l.split(","); return { name: (name || "").trim(), unit: (unit || "").trim() }; });
    try { const r = await api.post("/items/import", { rows }); toast.success(`Imported ${r.data.created}. ${r.data.errors.length} skipped.`); if (r.data.errors.length) console.log(r.data.errors); load(); }
    catch (er) { toast.error(apiError(er.response?.data?.detail)); }
    e.target.value = "";
  };

  return (
    <div>
      <PageHeader title="Item Master" subtitle="Owner-managed products. Duplicate key = Name + Unit."
        right={<div className="flex gap-2">
          <Button data-testid="item-export-btn" variant="secondary" onClick={exportCsv}><Download size={16} className="mr-1" /> CSV</Button>
          <label className="inline-flex items-center px-3 py-2 rounded-md bg-white/10 text-white text-sm cursor-pointer"><Upload size={16} className="mr-1" /> Import<input type="file" accept=".csv" className="hidden" data-testid="item-import-input" onChange={importCsv} /></label>
          <Button data-testid="new-item-btn" className="bg-sky-600 hover:bg-sky-700" onClick={() => setDlg(true)}><Plus size={16} className="mr-1" /> New Item</Button>
        </div>} />
      <div className="p-4 lg:p-8">
        <div className="bg-white rounded-lg border overflow-x-auto">
          <Table>
            <TableHeader className="bg-slate-50"><TableRow><TableHead>Item Name</TableHead><TableHead>Unit</TableHead><TableHead>Active</TableHead></TableRow></TableHeader>
            <TableBody>
              {items.map((it) => (
                <TableRow key={it.id} data-testid={`item-row-${it.id}`}>
                  <TableCell className="font-semibold">{it.name}</TableCell>
                  <TableCell>{it.unit}</TableCell>
                  <TableCell><Switch data-testid={`item-active-${it.id}`} checked={it.active} onCheckedChange={() => toggle(it)} /></TableCell>
                </TableRow>
              ))}
              {items.length === 0 && <TableRow><TableCell colSpan={3} className="text-center text-slate-400 py-8">No items.</TableCell></TableRow>}
            </TableBody>
          </Table>
        </div>
      </div>
      <Dialog open={dlg} onOpenChange={setDlg}>
        <DialogContent>
          <DialogHeader><DialogTitle>New Item</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>Item Name *</Label><Input data-testid="item-name-input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
            <div><Label>Unit *</Label><Input data-testid="item-unit-input" value={f.unit} onChange={(e) => setF({ ...f, unit: e.target.value })} /></div>
          </div>
          <DialogFooter><Button data-testid="item-save" onClick={save} className="bg-sky-600 hover:bg-sky-700">Save</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

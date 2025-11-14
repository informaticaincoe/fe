import base64
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ReportAccountMoveDaily(models.TransientModel):
    _name = "report.account.move.daily"
    _description = "Facturas agrupadas por día"

    invoice_date = fields.Date("Fecha")
    invoice_date_str = fields.Char("Fecha", compute="_compute_invoice_date_str", store=False)

    cantidad_facturas = fields.Integer("Registros")
    monto_total_operacion = fields.Monetary("Monto total operación")
    monto_total_impuestos = fields.Monetary("IVA operación")
    name = fields.Char("Número de factura")
    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)

    semester_year = fields.Integer(string="Año (Semestre)", readonly=True, index=True)
    semester_label = fields.Char(
        compute="_compute_semester",
        store=True,
        index=True,
    )

    invoice_year = fields.Char(string="Año", compute="_compute_invoice_year", store=False)
    invoice_month = fields.Char(string="Mes", compute="_compute_invoice_month", store=False)

    numero_anexo = fields.Char(
        string="Número del anexo",
        default=lambda self: str(self.env.context.get("numero_anexo", "")),
    )

    # --- Campos para agrupar / filtros ---
    invoice_year_agrupado = fields.Char(string="Año", index=True)
    invoice_semester_agrupado = fields.Selection(
        [('1', '1.º semestre'), ('2', '2.º semestre')],
        string="Semestre",
        index=True,
    )
    invoice_month_agrupado = fields.Char(string="Mes", index=True)

    invoice_year_sel = fields.Selection(
        selection=lambda self: [(str(y), str(y)) for y in range(2018, 2040)],
        string="Año (sel)",
        index=True,
    )
    invoice_month_sel = fields.Selection(
        selection=[(f"{m:02d}", f"{m:02d}") for m in range(1, 13)],
        string="Mes (sel)",
        index=True,
    )

    # ---------- COMPUTES ----------
    @api.depends("invoice_date")
    def _compute_invoice_date_str(self):
        for r in self:
            r.invoice_date_str = r.invoice_date.strftime("%d/%m/%Y") if r.invoice_date else ""

    @api.depends("invoice_date")
    def _compute_invoice_year(self):
        for r in self:
            r.invoice_year = r.invoice_date.strftime("%Y") if r.invoice_date else ""

    @api.depends("invoice_date")
    def _compute_invoice_month(self):
        for r in self:
            r.invoice_month = r.invoice_date.strftime("%m") if r.invoice_date else ""

    @api.depends("invoice_date")
    def _compute_semester(self):
        for r in self:
            if r.invoice_date:
                r.semester_year = r.invoice_date.year
                sem = "S1" if r.invoice_date.month <= 6 else "S2"
                r.semester_label = f"{r.semester_year}-{sem}"
            else:
                r.semester_year = False
                r.semester_label = False

    @api.depends("invoice_date")
    def _compute_periods(self):
        for r in self:
            if r.invoice_date:
                r.invoice_year_agrupado = str(r.invoice_date.year)
                r.invoice_semester_agrupado = "1" if r.invoice_date.month <= 6 else "2"
                r.invoice_month_agrupado = f"{r.invoice_date.month:02d}"
            else:
                r.invoice_year_agrupado = False
                r.invoice_semester_agrupado = False
                r.invoice_month_agrupado = False

    @api.depends("invoice_date")
    def _compute_periods_sel(self):
        for r in self:
            if r.invoice_date:
                r.invoice_year_sel = str(r.invoice_date.year)
                r.invoice_month_sel = f"{r.invoice_date.month:02d}"
            else:
                r.invoice_year_sel = False
                r.invoice_month_sel = False

    # ---------- LÓGICA PRINCIPAL ----------
    @api.model
    def action_open_report(self, *args, **kwargs):
        """Recalcula el reporte y abre la vista."""
        # limpiar registros anteriores
        self.search([]).unlink()

        numero_anexo = str(self.env.context.get("numero_anexo") or "")

        Move = self.env["account.move"]
        # Dominio o filtro de los campos
        domain = [
            ("move_type", "=", "out_invoice"),
            ("amount_untaxed", "<", 25000),
            ("hacienda_estado", "=", "PROCESADO"),
            ("hacienda_selloRecibido", "!=", False),
            ("has_sello_anulacion", "=", False),
        ]
        # Realizar las operaciones de suma y conteo en los siguientes campos
        agg_fields = [
            "amount_untaxed:sum",
            "amount_tax:sum",
            "id:count",
        ]
        # Agrupar por DÍA
        groupby = ["invoice_date:day"]

        _logger.info("mOVE = %s", Move)

        # Obtener de account moves todos los registros que cumplen con el dominio, se realizcen las operaciones indicadas en add_fields y agrupadas por fecha
        rows = Move.read_group(
            domain=domain,
            fields=agg_fields,
            groupby=groupby,
            orderby="invoice_date:day",
        )

        for r in rows:
            # Obtener las fechas del diccionario de datos
            range_info = r.get("__range", {}).get("invoice_date:day")
            if range_info:
                # Convetir la fecha de formato string a Date dd/mm/yyyy
                d = fields.Date.to_date(range_info["from"])
            else:
                continue

            year = d.year
            month = d.month
            semester = "1" if month <= 6 else "2"

            self.create({
                "invoice_date": d,
                "cantidad_facturas": r["__count"] if "__count" in r else r.get("invoice_date_count", 0),
                "monto_total_operacion": r["amount_untaxed"],
                "monto_total_impuestos": r["amount_tax"],
                "invoice_year_agrupado": str(year),
                "invoice_semester_agrupado": semester,
                "invoice_month_agrupado": f"{month:02d}",
                "invoice_year_sel": str(year),
                "invoice_month_sel": f"{month:02d}",
                "numero_anexo": numero_anexo
            })

        return {
            "type": "ir.actions.client",
            "name": "Facturas clientes menores a 25000",
            "res_model": "report.account.move.daily",
            "view_mode": "list",
            "view_id": self.env.ref(
                "l10n_sv_mh_anexos.view_report_account_move_daily_list"
            ).id,
            "search_view_id": self.env.ref(
                "l10n_sv_mh_anexos.view_anexo_menores_search"
            ).id,
            "target": "current",
            "context": dict(self.env.context, numero_anexo=numero_anexo),
            "replace_existing_action": True,
            'tag': 'reload'
        }

    # Exportar datos a csv
    def export_csv_from_action(self):
        _logger.info("Selfssss: %s", self)

        ctx = self.env.context
        numero_anexo = str(ctx.get("numero_anexo") or "")
        params = ctx.get("params") or {}

        # Dominio actual de la vista (filtros aplicados)
        domain = params.get("domain") or ctx.get("active_domain") or []

        _logger.info("ANEXO CSV | domain usado en export: %s", domain)

        # 1) Si hay selección en la lista, se respeta SOLO esa selección
        active_ids = ctx.get("active_ids") or []
        if active_ids:
            recs = self.browse(active_ids)
        else:
            recs = self.search(domain)

        _logger.info("DATOSSS: %s", recs)

        if not recs:
            _logger.warning("Sin registros para exportar en %s.", self._name)
            return

        # (opcional) recuperar view_id
        view_id = None
        xmlid = params.get("action")
        if xmlid:
            try:
                action = self.env["ir.actions.act_window"]._for_xml_id(xmlid)
                view_id = action.get("view_id") and action["view_id"][0] or None
            except Exception as e:
                _logger.warning("No se pudo resolver view_id: %s", e)

        csv_bytes = self.env["anexo.csv.utils"].generate_csv(
            recs,
            numero_anexo=numero_anexo,
            view_id=view_id,
            include_header=False,
        )

        att = self.env["ir.attachment"].create({
            "name": f"anexo_{numero_anexo or 'reporte'}.csv",
            "type": "binary",
            "datas": base64.b64encode(csv_bytes),
            "res_model": self._name,
            "res_id": False,
            "public": True,
        })
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{att.id}?download=true",
            "target": "self",
        }

    # --- Campos para agrupar (store=True) ---
    invoice_year_agrupado = fields.Char(string="Año", index=True)
    invoice_semester_agrupado = fields.Selection(
        [('1', '1.º semestre'), ('2', '2.º semestre')],
        string="Semestre", index=True
    )
    invoice_month_agrupado = fields.Char(string="Mes", index=True)

    # --- Wrappers para SearchPanel (Selection) ---
    invoice_year_sel = fields.Selection(
        selection=lambda self: [(str(y), str(y)) for y in range(2018, 2040)],
        string='Año (sel)', index=True
    )
    invoice_month_sel = fields.Selection(
        selection=[(f'{m:02d}', f'{m:02d}') for m in range(1, 13)],
        string='Mes (sel)', index=True
    )

    @api.depends('invoice_date')
    def _compute_periods(self):
        for r in self:
            if r.invoice_date:
                r.invoice_year_agrupado = str(r.invoice_date.year)
                r.invoice_semester_agrupado = '1' if r.invoice_date.month <= 6 else '2'
                r.invoice_month_agrupado = f'{r.invoice_date.month:02d}'
            else:
                r.invoice_year_agrupado = False
                r.invoice_semester_agrupado = False
                r.invoice_month_agrupado = False

    @api.depends('invoice_date')
    def _compute_periods_sel(self):
        for r in self:
            if r.invoice_date:
                r.invoice_year_sel = str(r.invoice_date.year)
                r.invoice_month_sel = f'{r.invoice_date.month:02d}'
            else:
                r.invoice_year_sel = False
                r.invoice_month_sel = False

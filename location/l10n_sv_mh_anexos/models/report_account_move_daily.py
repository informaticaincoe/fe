import base64
from odoo import fields, models, api
import logging

_logger = logging.getLogger(__name__)

class ReportAccountMoveDaily(models.Model):
    _name = "report.account.move.daily"
    _description = "Facturas agrupadas por día"
    _auto = False

    invoice_date = fields.Date("Fecha")
    cantidad_facturas = fields.Integer("Registros")
    monto_total_operacion = fields.Monetary("Monto total operación")
    monto_total_impuestos = fields.Monetary("IVA operacion")
    name = fields.Char("Número de factura")
    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)

    invoice_year = fields.Char(
        string="Año",
        compute='_compute_invoice_year',
        store=False
    )

    invoice_month = fields.Char(
        string="Mes",
        compute='_compute_invoice_month',
        store=False
    )

    numero_anexo = fields.Char(
        string="Número del anexo",
        compute='_compute_get_numero_anexo',
        readonly=True,
    )

    @api.depends('invoice_date')
    def _compute_invoice_year(self):
        for record in self:
            if record.invoice_date:
                record.invoice_year = record.invoice_date.strftime('%Y')
            else:
                record.invoice_year = ''

    @api.depends('invoice_date')
    def _compute_invoice_month(self):
        for record in self:
            if record.invoice_date:
                record.invoice_month = record.invoice_date.strftime('%m')
            else:
                record.invoice_month = ''

    @api.depends()
    def _compute_get_numero_anexo(self):
        numero_anexo_ctx = str(self.env.context.get("numero_anexo", ""))  # valor del contexto o vacío
        for record in self:
            record.numero_anexo = numero_anexo_ctx

    def init(self):
        self.env.cr.execute("""
                            CREATE
                            OR REPLACE VIEW report_account_move_daily AS (
                SELECT
                    MIN(id) AS id,
                    invoice_date::date AS invoice_date,
                    STRING_AGG(name, ', ') AS name,
                    COUNT(id) AS cantidad_facturas,
                    SUM(total_operacion) AS monto_total_operacion,
                    SUM(amount_tax) AS monto_total_impuestos,
                    (SELECT id FROM res_currency WHERE name='USD' LIMIT 1) as currency_id
                FROM account_move
                WHERE total_operacion < 15000 --state = 'posted' 
                GROUP BY invoice_date::date
            )
                            """)

    def export_csv_from_action(self):
        ctx = self.env.context
        numero_anexo = str(ctx.get("numero_anexo") or "")

        # 1) Si hay selección en la lista
        active_ids = ctx.get("active_ids") or []
        if active_ids:
            recs = self.browse(active_ids)
        else:
            recs = self.search([])

        if not recs:
            _logger.warning("Sin registros para exportar en %s.", self._name)
            return

        # (opcional) recuperar view_id
        view_id = None
        params = ctx.get("params") or {}
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

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

    # semester = fields.Selection(
    #     [('S1', 'Ene–Jun'), ('S2', 'Jul–Dic')],
    #     string="Semestre", readonly=True, index=True
    # )
    semester_year = fields.Integer(string="Año (Semestre)", readonly=True, index=True)

    semester_label = fields.Char(  # útil para mostrar/ordenar: "2025-H1"
        compute='_compute_semester',
        store=True, index=True
    )

    invoice_year = fields.Char(string="Año", compute='_compute_invoice_year', store=True)
    invoice_month = fields.Char(string="Mes", compute='_compute_invoice_month', store=True)

    @api.depends('invoice_date')
    def _compute_invoice_year(self):
        for r in self:
            r.invoice_year = r.invoice_date.strftime('%Y') if r.invoice_date else ''

    @api.depends('invoice_date')
    def _compute_invoice_month(self):
        for r in self:
            r.invoice_month = r.invoice_date.strftime('%m') if r.invoice_date else ''

    @api.depends('invoice_date')
    def _compute_semester(self):
        for m in self:
            if m.invoice_date:
                m.semester_year = m.invoice_date.year
                m.semester = 'S1' if m.invoice_date.month <= 6 else 'S2'
                m.semester_label = f"{m.semester_year}-{m.semester}"
            else:
                m.semester_year = False
                m.semester = False
                m.semester_label = False

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
        # IMPORTANTE: usar el nombre real de la tabla account_move y columnas (total_operacion, amount_tax, name, invoice_date)
        self.env.cr.execute("""
              CREATE OR REPLACE VIEW report_account_move_daily AS
              (
                  SELECT
                      MIN(am.id) AS id,
                      MIN (am.move_type) as move_type,
                      am.invoice_date::date AS invoice_date,
                      STRING_AGG(am.name, ', ') AS name,
                      COUNT(am.id) AS cantidad_facturas,
                      SUM(am.amount_untaxed) AS monto_total_operacion,
                      SUM(am.amount_tax) AS monto_total_impuestos,
                      (SELECT id FROM res_currency WHERE name='USD' LIMIT 1) AS currency_id,

                      /* ====== Nuevas columnas de semestre ====== */
                      EXTRACT(YEAR FROM am.invoice_date)::int AS semester_year,
                      CASE WHEN EXTRACT(MONTH FROM am.invoice_date)::int <= 6 THEN 'S1' ELSE 'S2' END AS semester,
                      (EXTRACT(YEAR FROM am.invoice_date)::int || '-' ||
                         CASE WHEN EXTRACT(MONTH FROM am.invoice_date)::int <= 6 THEN 'S1' ELSE 'S2' END
                      )::text AS semester_label

                  FROM account_move am
                  WHERE am.amount_untaxed < 25000  and am.move_type::text ILIKE 'out_invoice' -- (tu condición)
                  GROUP BY
                      am.invoice_date::date,
                      EXTRACT(YEAR FROM am.invoice_date)::int,
                      CASE WHEN EXTRACT(MONTH FROM am.invoice_date)::int <= 6 THEN 'S1' ELSE 'S2' END
              );
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

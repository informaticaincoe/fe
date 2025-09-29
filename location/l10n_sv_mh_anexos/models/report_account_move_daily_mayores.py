from odoo import fields, models, api


class ReportAccountMoveDailyMayores(models.Model):
    _name = "report.account.move.daily.mayores"
    _description = "Facturas agrupadas por día para clientes con ventas mayores a 25000"
    _auto = False

    invoice_date = fields.Date("Fecha")
    cantidad_facturas = fields.Integer("Registros")
    monto_total_operacion = fields.Monetary("Monto total operación")
    monto_total_impuestos = fields.Monetary("IVA operacion")
    name = fields.Char("Número de factura")  # 👈 aquí el nombre del move
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
                            OR REPLACE VIEW report_account_move_daily_mayores AS (
                SELECT
                    MIN(id) AS id,
                    invoice_date::date AS invoice_date,
                    STRING_AGG(name, ', ') AS name,   -- 👈 ahora sí existe
                    COUNT(id) AS cantidad_facturas,
                    SUM(total_operacion) AS monto_total_operacion,
                    SUM(amount_tax) AS monto_total_impuestos,
                    (SELECT id FROM res_currency WHERE name='USD' LIMIT 1) as currency_id
                FROM account_move
                WHERE total_operacion >= 25000
                GROUP BY invoice_date::date
            )
                            """)

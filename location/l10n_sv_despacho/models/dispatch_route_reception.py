from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DispatchRouteReception(models.Model):
    _name = "dispatch.route.reception"
    _description = "Recepción de Ruta"
    _order = "create_date desc"

    route_id = fields.Many2one("dispatch.route", string="Ruta", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="route_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="route_id.currency_id", store=True, readonly=True)

    received_by_id = fields.Many2one("res.users", string="Recibido por", default=lambda self: self.env.user, required=True)
    received_date = fields.Datetime(string="Fecha recepción", default=fields.Datetime.now, required=True)

    cash_received = fields.Monetary(string="Efectivo recibido", currency_field="currency_id", required=True, default=0.0)
    expected_cash_total = fields.Monetary(string="Esperado contado entregado", currency_field="currency_id", required=True, default=0.0)
    cash_difference = fields.Monetary(string="Diferencia", currency_field="currency_id", compute="_compute_difference", store=True)

    notes = fields.Text(string="Observaciones")

    line_ids = fields.One2many("dispatch.route.reception.line", "reception_id", string="Facturas")

    @api.depends("cash_received", "expected_cash_total")
    def _compute_difference(self):
        for rec in self:
            rec.cash_difference = rec.cash_received - rec.expected_cash_total


class DispatchRouteReceptionLine(models.Model):
    _name = "dispatch.route.reception.line"
    _description = "Línea recepción de ruta"

    reception_id = fields.Many2one("dispatch.route.reception", string="Recepción", required=True, ondelete="cascade")
    route_id = fields.Many2one(related="reception_id.route_id", store=True, readonly=True)

    move_id = fields.Many2one("account.move", string="Factura", required=True, index=True)
    partner_id = fields.Many2one(related="move_id.partner_id", store=True, readonly=True)
    move_total = fields.Monetary(related="move_id.amount_total", store=True, readonly=True, currency_field="currency_id")
    currency_id = fields.Many2one(related="reception_id.currency_id", store=True, readonly=True)

    # Estado de entrega (solo auditoría; devoluciones de producto se registran en el otro formulario)
    status = fields.Selection(
        [
            ("delivered", "Entregada"),
            ("not_delivered", "No entregada"),
            ("partial", "Parcial / Avería"),
        ],
        required=True,
        default="delivered",
    )

    is_credit = fields.Boolean(string="Crédito", default=False)
    not_delivered_reason = fields.Text(string="Motivo no entregada")
    partial_note = fields.Text(string="Detalle parcial/avería")

    @api.constrains("status", "not_delivered_reason")
    def _check_reason(self):
        for ln in self:
            if ln.status == "not_delivered" and not (ln.not_delivered_reason or "").strip():
                raise ValidationError(_("Debes ingresar el motivo cuando una factura es 'No entregada'."))

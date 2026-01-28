from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class DispatchRouteReception(models.Model):
    _name = "dispatch.route.reception"
    _description = "Recepción de Ruta (CxC)"
    _order = "create_date desc"

    route_id = fields.Many2one("dispatch.route", string="Ruta", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="route_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="route_id.currency_id", store=True, readonly=True)

    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("confirmed", "Confirmado"),
            ("cancel", "Cancelado"),
        ],
        default="draft",
        tracking=True,
        copy=False,
    )

    received_by_id = fields.Many2one("res.users", string="Recibido por", default=lambda self: self.env.user, required=True)
    received_date = fields.Datetime(string="Fecha recepción", default=fields.Datetime.now, required=True)

    cash_received = fields.Monetary(string="Efectivo recibido", currency_field="currency_id", required=True, default=0.0)
    expected_cash_total = fields.Monetary(string="Esperado contado entregado", currency_field="currency_id", compute="_compute_expected_cash_total", store=True)
    cash_difference = fields.Monetary(string="Diferencia", currency_field="currency_id", compute="_compute_difference", store=True)

    notes = fields.Text(string="Observaciones")

    line_ids = fields.One2many("dispatch.route.reception.line", "reception_id", string="Facturas")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        route_id = res.get("route_id") or self.env.context.get("default_route_id")
        if route_id:
            route = self.env["dispatch.route"].browse(route_id)
            lines = []
            for mv in route.account_move_ids:
                # Heurística simple: si tiene término de pago => crédito
                is_credit = bool(mv.invoice_payment_term_id and mv.invoice_payment_term_id.line_ids)
                lines.append((0, 0, {
                    "move_id": mv.id,
                    "status": "delivered",
                    "is_credit": is_credit,
                }))
            res["line_ids"] = lines
        return res

    @api.depends("line_ids.status", "line_ids.move_total", "line_ids.is_credit")
    def _compute_expected_cash_total(self):
        for rec in self:
            total = 0.0
            for ln in rec.line_ids:
                if ln.status == "delivered" and not ln.is_credit:
                    total += ln.move_total
            rec.expected_cash_total = total

    @api.depends("cash_received", "expected_cash_total")
    def _compute_difference(self):
        for rec in self:
            rec.cash_difference = rec.cash_received - rec.expected_cash_total

    def action_confirm(self):
        for rec in self:
            if rec.state != "draft":
                continue

            if not rec.route_id:
                raise UserError(_("Debe seleccionar una ruta."))

            if rec.route_id.state != "in_transit":
                raise UserError(_("La ruta debe estar 'En tránsito' para poder recibirla."))

            # Validaciones
            for ln in rec.line_ids:
                if ln.status == "not_delivered" and not (ln.not_delivered_reason or "").strip():
                    raise ValidationError(_("Debe ingresar el motivo cuando una factura es 'No entregada'."))
                if ln.status == "partial" and not (ln.partial_note or "").strip():
                    raise ValidationError(_("Agregue un detalle para 'Parcial / Avería'."))

            # Actualiza ruta a recibido + resumen
            rec.route_id.write({
                "state": "received",
                "received_by_id": rec.received_by_id.id,
                "received_date": rec.received_date,
                "cash_received": rec.cash_received,
                "expected_cash_total": rec.expected_cash_total,
                "cash_difference": rec.cash_difference,
                "last_reception_id": rec.id,
            })

            rec.state = "confirmed"

    def action_cancel(self):
        self.write({"state": "cancel"})


class DispatchRouteReceptionLine(models.Model):
    _name = "dispatch.route.reception.line"
    _description = "Línea Recepción de Ruta (CxC)"

    reception_id = fields.Many2one("dispatch.route.reception", string="Recepción", required=True, ondelete="cascade")
    route_id = fields.Many2one(related="reception_id.route_id", store=True, readonly=True)

    move_id = fields.Many2one("account.move", string="Factura", required=True, index=True)
    partner_id = fields.Many2one(related="move_id.partner_id", store=True, readonly=True)
    move_total = fields.Monetary(related="move_id.amount_total", store=True, readonly=True, currency_field="currency_id")
    currency_id = fields.Many2one(related="reception_id.currency_id", store=True, readonly=True)

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
                raise ValidationError(_("Debe ingresar el motivo cuando una factura es 'No entregada'."))

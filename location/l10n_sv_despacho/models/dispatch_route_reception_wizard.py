from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class DispatchRouteReceptionWizard(models.TransientModel):
    _name = "dispatch.route.reception.wizard"
    _description = "Wizard Recepción de Ruta (CxC)"

    route_id = fields.Many2one("dispatch.route", string="Ruta", required=True)
    currency_id = fields.Many2one(related="route_id.currency_id", readonly=True)

    cash_received = fields.Monetary(string="Efectivo recibido", currency_field="currency_id", default=0.0, required=True)
    notes = fields.Text(string="Observaciones")

    line_ids = fields.One2many("dispatch.route.reception.line.wizard", "wizard_id", string="Facturas")

    expected_cash_total = fields.Monetary(
        string="Esperado (contado entregado)",
        currency_field="currency_id",
        compute="_compute_expected_cash_total",
        store=False,
    )
    difference = fields.Monetary(
        string="Diferencia",
        currency_field="currency_id",
        compute="_compute_difference",
        store=False,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        route_id = res.get("route_id") or self.env.context.get("default_route_id")
        if route_id:
            route = self.env["dispatch.route"].browse(route_id)
            lines = []
            # Facturas asignadas a la ruta (podés filtrar por posted/out_invoice si querés más estricto)
            for mv in route.account_move_ids:
                # sugerencia de crédito: si tiene término de pago y no es pago inmediato
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
        for wiz in self:
            total = 0.0
            for ln in wiz.line_ids:
                if ln.status == "delivered" and not ln.is_credit:
                    total += ln.move_total
            wiz.expected_cash_total = total

    @api.depends("cash_received", "expected_cash_total")
    def _compute_difference(self):
        for wiz in self:
            wiz.difference = wiz.cash_received - wiz.expected_cash_total

    def action_confirm_reception(self):
        self.ensure_one()

        route = self.route_id
        if route.state != "in_transit":
            raise UserError(_("Solo se puede recibir una ruta cuando está En tránsito."))

        # Validaciones de motivos
        for ln in self.line_ids:
            if ln.status == "not_delivered" and not (ln.not_delivered_reason or "").strip():
                raise ValidationError(_("Debes ingresar el motivo para las facturas No entregadas."))
            if ln.status == "partial" and not (ln.partial_note or "").strip():
                # no obligatorio si no querés, pero recomendable
                raise ValidationError(_("Agrega un detalle para 'Parcial / Avería'."))

        # Crear recepción (auditoría)
        reception = self.env["dispatch.route.reception"].create({
            "route_id": route.id,
            "cash_received": self.cash_received,
            "expected_cash_total": self.expected_cash_total,
            "notes": self.notes,
            "line_ids": [(0, 0, {
                "move_id": ln.move_id.id,
                "status": ln.status,
                "is_credit": ln.is_credit,
                "not_delivered_reason": ln.not_delivered_reason,
                "partial_note": ln.partial_note,
            }) for ln in self.line_ids],
        })

        # Actualizar ruta: recibido + resumen
        route.write({
            "state": "received",
            "received_by_id": self.env.user.id,
            "received_date": fields.Datetime.now(),
            "cash_received": self.cash_received,
            "expected_cash_total": self.expected_cash_total,
            "cash_difference": self.difference,
            "last_reception_id": reception.id,
        })

        return {"type": "ir.actions.act_window_close"}


class DispatchRouteReceptionLineWizard(models.TransientModel):
    _name = "dispatch.route.reception.line.wizard"
    _description = "Línea Wizard Recepción de Ruta"

    wizard_id = fields.Many2one("dispatch.route.reception.wizard", required=True, ondelete="cascade")

    move_id = fields.Many2one("account.move", string="Factura", required=True)
    partner_id = fields.Many2one(related="move_id.partner_id", readonly=True)
    move_total = fields.Monetary(related="move_id.amount_total", readonly=True, currency_field="currency_id")
    currency_id = fields.Many2one(related="wizard_id.currency_id", readonly=True)

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

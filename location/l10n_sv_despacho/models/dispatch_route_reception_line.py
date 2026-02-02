from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DispatchRouteReceptionLine(models.Model):
    _name = "dispatch.route.reception.line"
    _description = "Factura en recepción de ruta"

    reception_id = fields.Many2one(
        "dispatch.route.reception",
        required=True,
        ondelete="cascade"
    )

    move_id = fields.Many2one(
        "account.move",
        string="Factura",
        required=True
    )

    partner_id = fields.Many2one(
        related="move_id.partner_id",
        store=True,
        readonly=True
    )

    move_total = fields.Monetary(
        related="move_id.amount_total",
        store=True,
        readonly=True
    )

    currency_id = fields.Many2one(
        related="reception_id.currency_id",
        store=True,
        readonly=True
    )

    status = fields.Selection([
        ("delivered", "Entregado"),
        ("partial", "Parcial"),
        ("not_delivered", "No entregado"),
        ("returned", "Devuelto"),
    ], default="delivered", required=True)

    is_credit = fields.Boolean(
        string="Crédito",
        default=False
    )

    not_delivered_reason = fields.Text()
    partial_note = fields.Text()

    has_return = fields.Boolean(
        string="Tiene devolución",
        default=False
    )

    # -------------------------
    # VALIDACIONES
    # -------------------------
    @api.constrains("status", "not_delivered_reason", "partial_note")
    def _check_status_details(self):
        for line in self:
            if line.status == "not_delivered" and not (line.not_delivered_reason or "").strip():
                raise ValidationError(
                    _("Debe indicar el motivo cuando la factura es 'No entregada'.")
                )

            if line.status == "partial" and not (line.partial_note or "").strip():
                raise ValidationError(
                    _("Debe indicar el detalle cuando la factura es 'Parcial / Avería'.")
                )

    # ==========================
    # ACCIÓN DEVOLUCIÓN FACTURA
    # ==========================

    def action_open_return_form(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Devolución de factura",
            "res_model": "dispatch.route.invoice.return",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_reception_id": self.reception_id.id,
                "default_reception_line_id": self.id,
                "default_move_id": self.move_id.id,
            }
        }




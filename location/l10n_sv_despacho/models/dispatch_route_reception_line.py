from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

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

    def _release_move_from_route(self):
        """Libera la factura para que pueda asignarse a otra ruta"""
        for line in self:
            move = line.move_id
            if not move:
                continue
            _logger.info("[ReceptionLine] Liberando factura %s de la ruta %s",
                         move.name, move.dispatch_route_id.display_name if move.dispatch_route_id else None)

            move.write({
                "dispatch_route_id": False,
                "dispatch_state": "free",
                "dispatch_reception_line_id": False,
            })

    def _assign_move_to_route(self):
        """Asocia la factura nuevamente a la ruta"""
        for line in self:
            move = line.move_id
            if not move or not line.reception_id:
                continue
            _logger.info("[ReceptionLine] Asociando factura %s a la ruta %s",
                         move.name, line.reception_id.route_id.display_name)

            move.write({
                "dispatch_route_id": line.reception_id.route_id.id,
                "dispatch_state": "assigned",
                "dispatch_reception_line_id": line.id,
            })

    # -------------------------
    # WRITE (cambio de estado)
    # -------------------------
    def write(self, vals):
        res = super().write(vals)

        if "status" in vals:
            for line in self:
                if line.status == "delivered":
                    raise ValidationError(_("Un documento entregado no puede liberarse de la ruta."))
                if line.status == "not_delivered":
                    line._release_move_from_route()
                else:
                    line._assign_move_to_route()
        return res

    # -------------------------
    # UNLINK (eliminar línea)
    # -------------------------
    def unlink(self):
        for line in self:
            if line.move_id:
                _logger.info("[ReceptionLine] unlink → liberando factura %s", line.move_id.name)
                line._release_move_from_route()
        return super().unlink()
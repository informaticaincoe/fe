from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class DispatchRouteReturn(models.Model):
    _name = "dispatch.route.return"
    _description = "Devolución por Ruta"
    _order = "create_date desc"

    reception_id = fields.Many2one("dispatch.route.reception", required=True, ondelete="cascade")
    route_id = fields.Many2one(related="reception_id.route_id", store=True, readonly=True)

    move_id = fields.Many2one("account.move", string="Factura", required=True, index=True)
    partner_id = fields.Many2one(related="move_id.partner_id", store=True, readonly=True)

    state = fields.Selection([("draft", "Borrador"), ("confirmed", "Confirmada")], default="draft", tracking=True)
    notes = fields.Text(string="Observaciones")

    line_ids = fields.One2many("dispatch.route.return.line", "return_id", string="Productos devueltos")

    def action_confirm(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError("Debe registrar al menos un producto devuelto")
            rec.state = "confirmed"
















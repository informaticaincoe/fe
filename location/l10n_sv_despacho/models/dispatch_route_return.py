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

class DispatchRouteReturnLine(models.Model):
    _name = "dispatch.route.return.line"
    _description = "Línea Devolución por Ruta"

    return_id = fields.Many2one("dispatch.route.return", required=True, ondelete="cascade")

    product_id = fields.Many2one("product.product", string="Producto", required=True)
    uom_id = fields.Many2one("uom.uom", string="UdM", required=True)
    qty_invoiced = fields.Float(string="Cant. facturada", readonly=True)
    qty_return = fields.Float(string="Cant. devuelta", required=True, default=0.0)

    reason = fields.Selection(
        [
            ("damaged", "Avería"),
            ("wrong", "Producto equivocado"),
            ("expired", "Vencido"),
            ("customer_reject", "Rechazado por cliente"),
            ("other", "Otro"),
        ],
        string="Motivo",
        required=True,
        default="Rechazado por cliente",
    )
    note = fields.Char(string="Detalle")

    @api.constrains("qty_return", "qty_invoiced")
    def _check_qty(self):
        for ln in self:
            if ln.qty_return <0:
                raise ValidationError("la cantidad devuelta no puede ser negativo")
            if ln.qty_return > ln.qty_invoiced:
                raise ValidationError(_("La cantidad devuelta no puede exceder la cantidad facturada."))














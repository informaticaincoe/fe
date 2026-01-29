from odoo import api, fields, models

class DispatchRouteReturnLine(models.Model):
    _name = "dispatch.route.return.line"
    _description = "Línea devolución por Ruta"

    return_id = fields.Many2one(
        "dispatch.route.return",
        required=True,
        ondelete="cascade",
    )

    product_id = fields.Many2one("product.product", required=True)
    uom_id = fields.Many2one("uom.uom", required=True)
    qty_return = fields.Float(string="Cantidad devuelta", default=0.0)
    reason = fields.Selection([
        ("damaged", "Avería"),
        ("wrong", "Producto equivocado"),
        ("expired", "Vencido"),
        ("customer_reject", "Rechazado por cliente"),
        ("other", "Otro"),
    ], default="other", required=True)
    note = fields.Char("Detalle")

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for ln in self:
            if ln.product_id and not ln.uom_id:
                ln.uom_id = ln.product_id.uom_id

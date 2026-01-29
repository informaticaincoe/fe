from odoo import api, fields, models, _

class AccountMove(models.Model):
    _inherit = 'account.move'

    ##FRANCISCO FLORES

    dispatch_state = fields.Selection([
        ("free", "Libre"),
        ("assigned", "Asignada a ruta"),
        ("delivered", "Entregada"),
        ("returned", "Devuelta"),
    ], default="free", copy=False)

    dispatch_reception_line_id = fields.Many2one("dispatch.route.reception.line", copy=False)
    dispatch_return_id = fields.Many2one("dispatch.route.invoice.return", copy=False)

    ############

    dispatch_route_id = fields.Many2one(
        'dispatch.route',
        string='Ruta de despacho',
        ondelete='set null',
        index=True,
        copy=False
    )

    partner_phone = fields.Char(
        related='partner_id.phone',
        string='Teléfono',
        store=False
    )

    partner_address = fields.Char(
        string='Dirección',
        compute='_compute_partner_address',
        store=False
    )

    def _compute_partner_address(self):
        for move in self:
            partner = move.partner_id
            parts = []
            if partner.street:
                parts.append(partner.street)
            if partner.street2:
                parts.append(partner.street2)
            move.partner_address = ' '.join(parts)

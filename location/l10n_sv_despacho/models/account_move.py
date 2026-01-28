from odoo import api, fields, models, _

class AccountMove(models.Model):
    _inherit = 'account.move'

    dispatch_route_id = fields.Many2one(
        'dispatch.route',
        string='Ruta de despacho',
        ondelete='set null',
        index=True
    )

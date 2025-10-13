from odoo import models, fields

class AccountMove(models.Model):
    _inherit = 'account.move'

    def write(self, vals):
        res = super().write(vals)
        if 'payment_state' in vals:
            quedans = self.env['account.quedan'].search([('factura_ids', 'in', self.ids)])
            quedans._sync_payments()
        return res

from odoo import models, fields

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    quedan_id = fields.Many2one(
        'account.quedan',
        string="Quedán asociado",
        ondelete='set null',
        index=True
    )

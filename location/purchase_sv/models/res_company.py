from odoo import fields, models, api, _

import logging
_logger = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = "res.company"

    percepcion_purchase_id = fields.Many2one(
        'account.account',
        string='Cuenta contable de Percepción 1%'
    )

    retencion_iva_purchase_id = fields.Many2one(
        'account.account',
        string='Cuenta contable de Retención IVA'
    )

    renta_purchase_id = fields.Many2one(
        'account.account',
        string='Cuenta contable de Renta'
    )

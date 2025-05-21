# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    document_number = fields.Char("Número de documento de proveedor")

    journal_id = fields.Many2one(
        'account.journal',
        string='Diario contable',
        domain="[('type', '=', 'purchase')]",
        help="Seleccione el diario contable para la factura de proveedor.",
    )

    def _prepare_invoice(self):
        res = super()._prepare_invoice()
        if self.journal_id:
            res['journal_id'] = self.journal_id.id
        return res
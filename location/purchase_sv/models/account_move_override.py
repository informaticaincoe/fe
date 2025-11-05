# -*- coding: utf-8 -*-
from odoo import fields, models

import logging
_logger = logging.getLogger(__name__)
try:
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo constants [purchase-account_move_override]")
except ImportError as e:
    _logger.error(f"Error al importar 'constants': {e}")
    constants = None

class SvMoveTaxAccountOverride(models.Model):
    _name = 'sv.move.tax.account.override'
    _description = 'Override de cuenta de impuesto por factura'
    _order = 'id'

    move_id = fields.Many2one('account.move', required=True, ondelete='cascade')
    tax_id = fields.Many2one('account.tax', required=True, ondelete='restrict', string='Impuesto')
    account_id = fields.Many2one('account.account', required=True, string='Cuenta alternativa')

    _sql_constraints = [
        ('move_tax_unique', 'unique(move_id, tax_id)',
         'Solo puede haber un reemplazo por impuesto en la factura.'),
    ]


class AccountMove(models.Model):
    _inherit = 'account.move'

    sv_override_ids = fields.One2many(
        'sv.move.tax.account.override', 'move_id', string='Reemplazos de cuentas de impuestos'
    )

    def _sv_requires_tax_override(self):
        """Vence > Contable y es compra."""
        self.ensure_one()
        return (
            self.move_type in (constants.IN_INVOICE, constants.IN_REFUND)
            and self.invoice_date and self.invoice_date_due
            and self.invoice_date_due > self.invoice_date
        )

    def _sv_get_move_taxes(self):
        self.ensure_one()
        return self.invoice_line_ids.mapped('tax_ids')

# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

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
        self.ensure_one()
        return (
            self.move_type in ('in_invoice', 'in_refund')
            and self.invoice_date and self.invoice_date_due
            and self.invoice_date_due > self.invoice_date
        )

    def _sv_get_move_taxes(self):
        self.ensure_one()
        return self.invoice_line_ids.mapped('tax_ids')

    # Integra este bloque dentro de TU action_post (antes de generar asientos y antes del super)
    def action_post(self):
        for move in self:
            if move._sv_requires_tax_override():
                taxes = move._sv_get_move_taxes()
                missing = taxes.filtered(lambda t: not move.sv_override_ids.filtered(lambda r: r.tax_id == t))
                if missing:
                    raise ValidationError(_(
                        "Esta factura tiene Vencimiento > Fecha contable.\n"
                        "Debes asignar una CUENTA ALTERNATIVA para cada impuesto:\n%s\n\n"
                        "Usa el botón “Cambiar cuentas de impuestos”."
                    ) % ', '.join(missing.mapped('name')))
        return super().action_post()

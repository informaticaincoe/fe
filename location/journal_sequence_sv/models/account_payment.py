# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

import logging
_logger = logging.getLogger(__name__)

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    name = fields.Char(readonly=False, copy=False, default='/')

    # No usar @only_fe en onchanges
    @api.onchange('posted_before', 'state', 'journal_id', 'date')
    def _onchange_journal_date(self):
        """Deja este onchange funcionar siempre.
        Si necesitas lógica especial SOLO cuando FE está activa, pon la condición adentro."""
        if not self.env.company.sit_facturacion:
            return  # no hagas nada especial
        # aquí tu lógica extra solo si FE=ON (si aplica)
        return

    # No usar @only_fe en action_post
    def action_post(self):
        """Permite postear pagos siempre.
        Si FE está apagada, deja el comportamiento estándar (super()).
        Si FE está encendida y necesitas numerar/cambiar algo, hazlo adentro."""
        if not self.env.company.sit_facturacion:
            # FE OFF → comportamiento estándar
            return super(AccountPayment, self).action_post()

        # FE ON → si realmente necesitas personalización, hazla aquí
        for rec in self:
            # if rec.state != 'draft':
            #     raise UserError(_("Only a draft payment can be posted."))
            if any(inv.state != 'posted' for inv in rec.reconciled_invoice_ids):
                raise ValidationError(_("The payment cannot be processed because the invoice is not open!"))

            if rec.name == '/':
                if rec.payment_type == 'transfer':
                    sequence_code = 'account.payment.transfer'
                else:
                    if rec.partner_type == 'customer':
                        sequence_code = 'account.payment.customer.invoice' if rec.payment_type == 'inbound' else 'account.payment.customer.refund'
                    else:
                        sequence_code = 'account.payment.supplier.refund' if rec.payment_type == 'inbound' else 'account.payment.supplier.invoice'
                rec.name = self.env['ir.sequence'].next_by_code(sequence_code, sequence_date=rec.date)

        # return super(AccountPayment, self).action_post()
        # Llamar al super con contexto para saltar validaciones FE en invoice
        return super(AccountPayment, self.with_context(skip_dte_validations=True)).action_post()
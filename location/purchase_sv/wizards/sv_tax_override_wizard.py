# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class SvTaxOverrideWizard(models.TransientModel):
    _name = 'sv.tax.override.wizard'
    _description = 'Cambiar cuentas de impuestos (solo esta factura)'

    move_id = fields.Many2one('account.move', required=True)
    line_ids = fields.One2many('sv.tax.override.wizard.line', 'wizard_id', string='Impuestos')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        move = self.env['account.move'].browse(self._context.get('active_id'))
        res['move_id'] = move.id

        lines = []
        taxes = (move.invoice_line_ids.mapped('tax_ids')).sorted(key=lambda t: t.name)
        for tax in taxes:
            # Cuenta “actual” por defecto (repartition line de factura, tipo 'tax')
            rep = tax.invoice_repartition_line_ids.filtered(lambda r: r.repartition_type == 'tax')[:1]
            current_account_id = rep.account_id.id if rep and rep.account_id else False

            # Si ya hay override guardado, precargarlo
            override = move.sv_override_ids.filtered(lambda r: r.tax_id == tax)[:1]
            lines.append((0, 0, {
                'tax_id': tax.id,
                'current_account_id': current_account_id,
                'new_account_id': override.account_id.id if override else False,
            }))
        res['line_ids'] = lines
        return res

    def action_apply(self):
        self.ensure_one()
        move = self.move_id

        # Borrar overrides previos para los impuestos de este asistente
        move.sv_override_ids.filtered(
            lambda r: r.tax_id.id in self.line_ids.mapped('tax_id').ids
        ).unlink()

        vals = []
        for l in self.line_ids:
            if not l.new_account_id:
                raise UserError(_("Debes elegir la cuenta para el impuesto %s.") % l.tax_id.display_name)
            vals.append({'move_id': move.id, 'tax_id': l.tax_id.id, 'account_id': l.new_account_id.id})

        self.env['sv.move.tax.account.override'].create(vals)
        return {'type': 'ir.actions.act_window_close'}


class SvTaxOverrideWizardLine(models.TransientModel):
    _name = 'sv.tax.override.wizard.line'
    _description = 'Línea de cambio de cuentas de impuestos'

    wizard_id = fields.Many2one('sv.tax.override.wizard', required=True, ondelete='cascade')
    tax_id = fields.Many2one('account.tax', required=True, string='Impuesto')
    current_account_id = fields.Many2one('account.account', string='Cuenta actual', readonly=True)
    new_account_id = fields.Many2one('account.account', string='Nueva cuenta', required=True,
                                     domain="[('company_id','=',wizard_id.move_id.company_id.id)]")

    @api.onchange('tax_id')
    def _onchange_tax_id(self):
        if self.tax_id and self.tax_id.sv_secondary_account_ids:
            accounts = self.tax_id.sv_secondary_account_ids.mapped('account_id').ids
            return {'domain': {'new_account_id': [('id', 'in', accounts)]}}
        return {'domain': {'new_account_id': [('company_id', '=', self.wizard_id.move_id.company_id.id)]}}

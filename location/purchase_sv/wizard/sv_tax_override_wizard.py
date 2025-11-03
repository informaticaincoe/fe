# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)

class SvTaxOverrideWizard(models.TransientModel):
    _name = 'sv.tax.override.wizard'
    _description = 'Cambiar cuentas de impuestos (solo esta factura)'

    move_id = fields.Many2one('account.move', required=True)
    line_ids = fields.One2many(
        'sv.tax.override.wizard.line',
        'wizard_id',
        string='Impuestos'
    )

    @api.model_create_multi
    def create(self, vals_list):
        _logger.info("SIT | create vals_list inicial: %s", vals_list)

        # Ignora silenciosamente intentos de crear líneas sin impuesto (evita el crash)
        # vals_list = [v for v in vals_list if v.get('tax_id')]
        # _logger.info("SIT | create vals_list filtrado (solo con tax_id): %s", vals_list)

        # if not vals_list:
        #     _logger.info("SIT | No hay líneas válidas para crear, retornando browse vacío")
        #     return self.browse()

        res = super().create(vals_list)
        _logger.info("SIT | Líneas creadas: %s", res.ids)
        return res

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        move = self.env['account.move'].browse(
            self._context.get('active_id') or self._context.get('default_move_id')
        )
        _logger.info("SIT | default_get wizard move_id: %s", move.id if move else "False")
        if not move:
            raise UserError(_("No se encontró la factura activa."))
        res['move_id'] = move.id

        lines = []
        taxes = move.invoice_line_ids.mapped('tax_ids').sorted(key=lambda t: t.name or str(t.id))
        for tax in taxes:
            rep = tax.invoice_repartition_line_ids.filtered(lambda r: r.repartition_type == 'tax')[:1]
            current_account_id = rep.account_id.id if rep and rep.account_id else False
            override = move.sv_override_ids.filtered(lambda r: r.tax_id == tax)[:1]
            lines.append((0, 0, {
                'tax_id': tax.id,
                'current_account_id': current_account_id,
                'new_account_id': override.account_id.id if override else False,
            }))
        res['line_ids'] = lines
        return res

    def action_apply(self):
        _logger.info("SIT | action_apply inicio.")
        self.ensure_one()
        move = self.move_id
        _logger.info("SIT | action_apply inicio para factura ID=%s", move.id)

        # líneas incompletas
        incompletas = self.line_ids.filtered(lambda l: not l.tax_id or not l.new_account_id)
        _logger.info("SIT | Líneas totales del wizard: %s", len(self.line_ids))
        _logger.info("SIT | Líneas incompletas detectadas: %s", incompletas.mapped('tax_id.name'))
        if incompletas:
            raise UserError(_("Hay líneas incompletas en el asistente. Revisa 'Nueva cuenta'."))

        # limpiar y crear overrides
        to_unlink = move.sv_override_ids.filtered(
            lambda r: r.tax_id.id in self.line_ids.mapped('tax_id').ids
        )
        _logger.info("SIT | Overrides a eliminar: %s", to_unlink.mapped('tax_id.name'))
        to_unlink.unlink()

        vals = []
        for l in self.line_ids:
            _logger.info("SIT | Procesando línea: Tax=%s, Nueva cuenta=%s", l.tax_id.name if l.tax_id else "False",
                         l.new_account_id.name if l.new_account_id else "False")
            if not l.tax_id or not l.new_account_id:
                raise UserError(_("Hay líneas incompletas en el asistente. Tax: %s, Nueva cuenta: %s") % (
                    l.tax_id.name if l.tax_id else "False",
                    l.new_account_id.name if l.new_account_id else "False"
                ))

            vals.append({
                'move_id': move.id,
                'tax_id': l.tax_id.id,
                'account_id': l.new_account_id.id
            })

        # vals = [{'move_id': move.id, 'tax_id': l.tax_id.id, 'account_id': l.new_account_id.id}
        #         for l in self.line_ids]
        # self.env['sv.move.tax.account.override'].create(vals)

            # Actualizar la línea contable del impuesto en el move
            tax_lines = move.line_ids.filtered(lambda ml: ml.tax_line_id == l.tax_id)
            _logger.info("SIT | Tax lines encontradas para %s: %s", l.tax_id.name, tax_lines.ids)
            if tax_lines:
                tax_lines.write({'account_id': l.new_account_id.id})
                _logger.info("SIT | Actualizada cuenta del impuesto %s a %s", l.tax_id.name, l.new_account_id.code)

        # Crear overrides (registro de respaldo)
        if vals:
            _logger.info("SIT | Creando overrides: %s", vals)
            self.env['sv.move.tax.account.override'].create(vals)

        _logger.info("SIT | action_apply finalizado para factura ID=%s", move.id)
        return {'type': 'ir.actions.act_window_close'}


class SvTaxOverrideWizardLine(models.TransientModel):
    _name = 'sv.tax.override.wizard.line'
    _description = 'Línea de cambio de cuentas de impuestos'

    wizard_id = fields.Many2one('sv.tax.override.wizard', required=True, ondelete='cascade')
    tax_id = fields.Many2one('account.tax', required=True, string='Impuesto')
    current_account_id = fields.Many2one('account.account', string='Cuenta actual', readonly=True)
    new_account_id = fields.Many2one(
        'account.account',
        string='Nueva cuenta',
        required=True
    )

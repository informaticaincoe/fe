from odoo import fields, models, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    from odoo.addons.common_utils.utils import config_utils
    _logger.info("SIT Modulo config_utils [Reverse] Nota de credito")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None
    constants = None

class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    l10n_latam_document_type_id = fields.Many2one(
        'l10n_latam.document.type',
        string='Tipo de Documento',
        domain=[('code', '=', '05')],
    )

    inv_refund_id = fields.Many2one('account.move', string='Factura a Reversar')
    inv_debit_id = fields.Many2one('account.move', string='Factura a Debitar')

    def refund_moves(self):
        self.ensure_one()
        _logger.info("SIT refund_moves_custom iniciado con move_ids=%s", self.move_ids)

        # --- GUARD: saltar flujo personalizado si se indica ---
        if self.env.context.get('skip_custom_refund_flow', False):
            _logger.info("SIT: skip_custom_refund_flow → usando flujo estándar de Odoo")
            return super(AccountMoveReversal, self).refund_moves()

        # --- Empresas sin FE → usamos flujo estándar ---
        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info("Empresa %s no usa FE → flujo estándar", self.company_id.name)
            return super(AccountMoveReversal, self).refund_moves()

        # --- Flujo de ventas con FE ---
        if self.move_type in (constants.OUT_INVOICE, constants.OUT_REFUND):
            _logger.info("Movimiento de VENTA (%s) → lógica personalizada FE", self.move_type)

            if not self.journal_id:
                raise UserError(_("Debe seleccionar un diario antes de continuar."))

            if self.journal_id.type == 'sale' and not self.l10n_latam_document_type_id:
                doc_type = self.env['l10n_latam.document.type'].search(
                    [('code', '=', constants.COD_DTE_NC)], limit=1
                )
                if not doc_type:
                    raise UserError(_("No se encontró tipo de documento Nota de Crédito (05)"))
                self.l10n_latam_document_type_id = doc_type

            created_moves = self.env['account.move']  # recordset vacío

            # --- Contexto seguro para evitar cálculos automáticos ---
            ctx_safe = dict(self.env.context, skip_compute_percepcion=True)

            for move in self.move_ids:
                # --- 1. Crear nota de crédito sin líneas (name asignado automáticamente) ---
                base_vals = self._prepare_default_reversal(move)
                base_vals.update({
                    'journal_id': self.journal_id.id,
                    'move_type': constants.OUT_REFUND,
                    'partner_id': move.partner_id.id,
                    'l10n_latam_document_type_id': self.l10n_latam_document_type_id.id,
                    'inv_refund_id': move.id,
                    'reversed_entry_id': move.id,
                    'company_id': move.company_id.id,
                })

                # --- Manejar diarios sin secuencia (force_name) ---
                # ctx_move = dict(ctx_safe)
                # if not self.journal_id.sequence_id:
                #     ctx_move['force_name'] = '/'

                reversal_move = self.env['account.move'].with_context(ctx_move).create(base_vals)

                # --- 2. Copiar líneas de productos ---
                lines_vals = []
                for line in move.invoice_line_ids:
                    line_vals = line.copy_data()[0]
                    for fld in ['move_id', 'payment_id', 'reconcile_id', 'matched_debit_ids', 'matched_credit_ids']:
                        line_vals.pop(fld, None)
                    lines_vals.append((0, 0, line_vals))

                if lines_vals:
                    reversal_move.write({'invoice_line_ids': lines_vals})

                created_moves |= reversal_move

            _logger.info("Reversiones creadas: %s", created_moves.ids)

            if created_moves:
                return {
                    'name': _('Nota de Crédito'),
                    'view_mode': 'form',
                    'res_model': 'account.move',
                    'type': 'ir.actions.act_window',
                    'res_id': created_moves[0].id,
                    'context': self.env.context,
                }

            return created_moves  # fallback

        # --- Flujo de compras ---
        else:
            _logger.info("Movimiento de COMPRA (%s) → usando flujo estándar Odoo", self.move_type)
            ctx = dict(self.env.context, skip_custom_refund_flow=True)

            if self.move_type != constants.IN_INVOICE:
                self.move_type = constants.IN_REFUND

            return super(AccountMoveReversal, self.with_context(ctx)).refund_moves()

    # def refund_moves(self):
    #     self.ensure_one()
    #     _logger.info("SIT refund_moves_custom iniciado con move_ids=%s", self.move_ids)
    #     _logger.info("SIT: Secuencia de diario %s, generado name=%s", self.journal_id.name, self.env['ir.sequence'].next_by_code(self.journal_id.sequence_id.code))
    #
    #     # --- GUARD: saltar flujo personalizado si se indica ---
    #     if self.env.context.get('skip_custom_refund_flow', False):
    #         _logger.info("SIT: skip_custom_refund_flow → usando flujo estándar de Odoo")
    #         return super(AccountMoveReversal, self).refund_moves()
    #
    #     # --- Empresas sin FE → usamos flujo estándar, dejando que Odoo genere name automáticamente ---
    #     if not (self.company_id and self.company_id.sit_facturacion):
    #         _logger.info("Empresa %s no usa FE → flujo estándar", self.company_id.name)
    #         return super(AccountMoveReversal, self).refund_moves()
    #
    #     # --- Flujo de ventas con FE ---
    #     if self.move_type in ('out_invoice', 'out_refund'):
    #         _logger.info("Movimiento de VENTA (%s) → lógica personalizada FE", self.move_type)
    #
    #         if not self.journal_id:
    #             raise UserError(_("Debe seleccionar un diario antes de continuar."))
    #
    #         if self.journal_id.type == 'sale' and not self.l10n_latam_document_type_id:
    #             doc_type = self.env['l10n_latam.document.type'].search(
    #                 [('code', '=', '05')], limit=1
    #             )
    #             if not doc_type:
    #                 raise UserError(_("No se encontró tipo de documento Nota de Crédito (05)"))
    #             self.l10n_latam_document_type_id = doc_type
    #
    #         # Generamos las reversiones usando _prepare_default_reversal
    #         default_vals_list = []
    #         for move in self.move_ids:
    #             default_vals = self._prepare_default_reversal(move)
    #             default_vals.update({
    #                 'journal_id': self.journal_id.id,
    #                 'move_type': 'out_refund',
    #                 'partner_id': move.partner_id.id,
    #                 'l10n_latam_document_type_id': self.l10n_latam_document_type_id.id,
    #                 'inv_refund_id': move.id,
    #                 'reversed_entry_id': move.id,
    #                 'company_id': move.company_id.id,
    #             })
    #             default_vals_list.append(default_vals)
    #
    #         # Crear los movimientos de reversión sin tocar default_name
    #         created_moves = self.env['account.move'].create(default_vals_list)
    #         _logger.info("Reversiones creadas: %s", created_moves.ids)
    #         # --- Retornar acción para abrir la nota de crédito ---
    #         if created_moves:
    #             return {
    #                 'name': _('Nota de Crédito'),
    #                 'view_mode': 'form',
    #                 'res_model': 'account.move',
    #                 'type': 'ir.actions.act_window',
    #                 'res_id': created_moves[0].id,  # abrir el primer move creado
    #                 'context': self.env.context,
    #             }
    #         return created_moves  # fallback
    #
    #     # --- Flujo de compras ---
    #     else:
    #         _logger.info("Movimiento de COMPRA (%s) → usando flujo estándar Odoo", self.move_type)
    #         ctx = dict(self.env.context, skip_custom_refund_flow=True)
    #
    #         # Ajustamos move_type a 'in_refund' para compras
    #         if self.move_type != 'in_invoice':
    #             self.move_type = 'in_refund'
    #
    #         # No pasamos default_name; dejamos que Odoo use la secuencia
    #         return super(AccountMoveReversal, self.with_context(ctx)).refund_moves()






    # def refund_moves(self):
    #     self.ensure_one()
    #     _logger.info("SIT refund_moves_custom iniciado con move_ids=%s", self.move_ids)
    #     _logger.info("SIT: Secuencia de diario %s, generado name=%s", self.journal_id.name, self.env['ir.sequence'].next_by_code(self.journal_id.sequence_id.code))
    #
    #     # --- GUARD: saltar flujo personalizado si se indica ---
    #     if self.env.context.get('skip_custom_refund_flow', False):
    #         _logger.info("SIT: skip_custom_refund_flow → usando flujo estándar de Odoo")
    #         return super(AccountMoveReversal, self).refund_moves()
    #
    #     # --- Empresas sin FE → usamos flujo estándar, dejando que Odoo genere name automáticamente ---
    #     if not (self.company_id and self.company_id.sit_facturacion):
    #         _logger.info("Empresa %s no usa FE → flujo estándar", self.company_id.name)
    #         return super(AccountMoveReversal, self).refund_moves()
    #
    #     # --- Flujo de ventas con FE ---
    #     if self.move_type in ('out_invoice', 'out_refund'):
    #         _logger.info("Movimiento de VENTA (%s) → lógica personalizada FE", self.move_type)
    #
    #         if not self.journal_id:
    #             raise UserError(_("Debe seleccionar un diario antes de continuar."))
    #
    #         if self.journal_id.type == 'sale' and not self.l10n_latam_document_type_id:
    #             doc_type = self.env['l10n_latam.document.type'].search(
    #                 [('code', '=', '05')], limit=1
    #             )
    #             if not doc_type:
    #                 raise UserError(_("No se encontró tipo de documento Nota de Crédito (05)"))
    #             self.l10n_latam_document_type_id = doc_type
    #
    #         # Generamos las reversiones usando _prepare_default_reversal
    #         default_vals_list = []
    #         created_moves = self.env['account.move']  # empty recordset
    #         for move in self.move_ids:
    #             default_vals = self._prepare_default_reversal(move)
    #             default_vals.update({
    #                 'journal_id': self.journal_id.id,
    #                 'move_type': 'out_refund',
    #                 'partner_id': move.partner_id.id,
    #                 'l10n_latam_document_type_id': self.l10n_latam_document_type_id.id,
    #                 'inv_refund_id': move.id,
    #                 'reversed_entry_id': move.id,
    #                 'company_id': move.company_id.id,
    #             })
    #
    #             # --- COPIAR LÍNEAS DE FACTURA ---
    #             lines_vals = []
    #             for line in move.invoice_line_ids:
    #                 line_vals = line.copy_data()[0]
    #                 # Quitamos campos que generan recursión
    #                 for fld in ['move_id', 'payment_id', 'reconcile_id', 'matched_debit_ids', 'matched_credit_ids']:
    #                     line_vals.pop(fld, None)
    #                 lines_vals.append((0, 0, line_vals))
    #             default_vals ['invoice_line_ids'] = lines_vals
    #             default_vals_list.append(default_vals)
    #
    #             # reversal_move = self.env['account.move'].create(reversal_vals)
    #             # --- Crear el movimiento con contexto que evita triggers de percepciones ---
    #             ctx_safe = dict(self.env.context, skip_compute_percepcion=True)
    #             reversal_move = self.env['account.move'].with_context(ctx_safe).create(default_vals_list)
    #             created_moves |= reversal_move
    #
    #         # created_moves = self.env['account.move'].create(default_vals_list)
    #         _logger.info("Reversiones creadas: %s", created_moves.ids)
    #         # --- Retornar acción para abrir la nota de crédito ---
    #         if created_moves:
    #             return {
    #                 'name': _('Nota de Crédito'),
    #                 'view_mode': 'form',
    #                 'res_model': 'account.move',
    #                 'type': 'ir.actions.act_window',
    #                 'res_id': created_moves[0].id,  # abrir el primer move creado
    #                 'context': self.env.context,
    #             }
    #         return created_moves  # fallback
    #
    #     # --- Flujo de compras ---
    #     else:
    #         _logger.info("Movimiento de COMPRA (%s) → usando flujo estándar Odoo", self.move_type)
    #         ctx = dict(self.env.context, skip_custom_refund_flow=True)
    #
    #         # Ajustamos move_type a 'in_refund' para compras
    #         if self.move_type != 'in_invoice':
    #             self.move_type = 'in_refund'
    #
    #         # No pasamos default_name; dejamos que Odoo use la secuencia
    #         return super(AccountMoveReversal, self.with_context(ctx)).refund_moves()

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
        _logger.info("SIT: Secuencia de diario %s, generado name=%s", self.journal_id.name, self.env['ir.sequence'].next_by_code(self.journal_id.sequence_id.code))

        # --- GUARD: saltar flujo personalizado si se indica ---
        if self.env.context.get('skip_custom_refund_flow', False):
            _logger.info("SIT: skip_custom_refund_flow → usando flujo estándar de Odoo")
            return super(AccountMoveReversal, self).refund_moves()

        # --- Empresas sin FE → usamos flujo estándar, dejando que Odoo genere name automáticamente ---
        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info("Empresa %s no usa FE → flujo estándar", self.company_id.name)
            return super(AccountMoveReversal, self).refund_moves()

        # --- Flujo de ventas con FE ---
        if self.move_type in ('out_invoice', 'out_refund'):
            _logger.info("Movimiento de VENTA (%s) → lógica personalizada FE", self.move_type)

            if not self.journal_id:
                raise UserError(_("Debe seleccionar un diario antes de continuar."))

            if self.journal_id.type == 'sale' and not self.l10n_latam_document_type_id:
                doc_type = self.env['l10n_latam.document.type'].search(
                    [('code', '=', '05')], limit=1
                )
                if not doc_type:
                    raise UserError(_("No se encontró tipo de documento Nota de Crédito (05)"))
                self.l10n_latam_document_type_id = doc_type

            # Generamos las reversiones usando _prepare_default_reversal
            default_vals_list = []
            for move in self.move_ids:
                default_vals = self._prepare_default_reversal(move)
                default_vals.update({
                    'journal_id': self.journal_id.id,
                    'move_type': 'out_refund',
                    'partner_id': move.partner_id.id,
                    'l10n_latam_document_type_id': self.l10n_latam_document_type_id.id,
                    'inv_refund_id': move.id,
                    'reversed_entry_id': move.id,
                })
                default_vals_list.append(default_vals)

            # Crear los movimientos de reversión sin tocar default_name
            created_moves = self.env['account.move'].create(default_vals_list)
            _logger.info("Reversiones creadas: %s", created_moves.ids)
            return created_moves

        # --- Flujo de compras ---
        else:
            _logger.info("Movimiento de COMPRA (%s) → usando flujo estándar Odoo", self.move_type)
            ctx = dict(self.env.context, skip_custom_refund_flow=True)

            # Ajustamos move_type a 'in_refund' para compras
            if self.move_type != 'in_invoice':
                self.move_type = 'in_refund'

            # No pasamos default_name; dejamos que Odoo use la secuencia
            return super(AccountMoveReversal, self.with_context(ctx)).refund_moves()

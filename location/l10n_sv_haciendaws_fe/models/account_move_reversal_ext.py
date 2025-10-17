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

        # Evitar recursión infinita
        if self.env.context.get('skip_refund_recursion'):
            _logger.info("SIT: Contexto skip_refund_recursion detectado. Usando flujo estándar de Odoo.")
            return super(AccountMoveReversal, self).refund_moves()

        # A. Verificar si aplica la FE
        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info("La empresa %s no usa facturación electrónica, se usará la lógica estándar de Odoo.", self.company_id.name)
            # Simplemente devolvemos None para que el botón siga el flujo estándar
            return self.with_context(skip_custom_refund_flow=True).refund_moves()

        # --- FLUJO DE VENTAS ---
        if self.move_type in (constants.OUT_INVOICE, constants.OUT_REFUND):
            if self.env.context.get('skip_custom_refund_flow', False):
                _logger.info("SIT: Ya estamos en el flujo estándar de ventas. Evitando recursión.")
                return super(AccountMoveReversal, self).refund_moves()

            _logger.info("SIT: Movimiento de VENTA (%s) detectado. Ejecutando lógica personalizada (FE).", self.move_type)

            # B. Validación de diario y movimientos
            if not self.journal_id:
                raise UserError(_("Debe seleccionar un diario antes de continuar."))

            if self.journal_id.type == 'sale' and not self.l10n_latam_document_type_id:
                raise UserError(_("Debe seleccionar un Tipo de Documento para la Nota de Crédito."))

            if self.journal_id.type == 'sale' and not self.l10n_latam_document_type_id:
                doc_type = self.env['l10n_latam.document.type'].search([('code', '=', constants.COD_DTE_NC)], limit=1)
                if not doc_type:
                    raise UserError(_("No se encontró el tipo de documento (05) Nota de crédito."))
                self.l10n_latam_document_type_id = doc_type

            ctx = dict(self.env.context or {})
            ctx.update({
                'default_journal_id': self.journal_id.id,
                'default_l10n_latam_document_type_id': self.l10n_latam_document_type_id.id,
                'dte_name_preassigned': True,
            })
            _logger.info("SIT refund_moves_custom usando contexto: %s", ctx)

            moves = self.move_ids
            if not moves:
                raise UserError(_("No se encontraron movimientos para revertir."))

            default_values_list = []
            default_vals = []
            for move in moves:
                move_type = None
                tipo_documento_compra = None

                if move.move_type == 'out_invoice':
                    move_type = 'out_refund'
                elif move.move_type == 'in_invoice':
                    move_type = 'in_refund'
                    tipo_documento_compra = self.env['account.journal.tipo_documento.field'].search([
                        ('codigo', '=', constants.COD_DTE_NC)
                    ], limit=1)
                    _logger.info("SIT tipo_documento_compra asignado para in_refund: %s", tipo_documento_compra.valores if tipo_documento_compra else "No encontrado")

                default_vals = self._prepare_default_reversal(move)
                default_vals['journal_id'] = self.journal_id.id
                default_vals['move_type'] = move_type  # 'out_refund'
                default_vals['partner_id'] = move.partner_id.id
                default_vals['l10n_latam_document_type_id'] = self.l10n_latam_document_type_id.id
                default_vals['sit_tipo_documento_id'] = tipo_documento_compra.id if tipo_documento_compra else False
                default_vals['clase_documento_id'] = move.clase_documento_id.id
                default_vals['tipo_ingreso_id'] = move.tipo_ingreso_id.id
                default_vals['tipo_costo_gasto_id'] = move.tipo_costo_gasto_id.id
                default_vals['tipo_operacion'] = move.tipo_operacion.id
                default_vals['clasificacion_facturacion'] = move.clasificacion_facturacion.id
                default_vals['sector'] = move.sector.id

                default_vals['inv_refund_id'] = move.id
                default_vals['reversed_entry_id'] = move.id

                _logger.info("SIT descuentos globales desc gravado=%s, desc exento=%s, desc no sujeto=%s, desc global=%s",
                    move.descuento_gravado_pct, move.descuento_exento_pct, move.descuento_no_sujeto_pct, move.descuento_global_monto)
                # Copiar descuentos globales, si existen
                if hasattr(move, 'descuento_gravado_pct'):  # Si account.move tiene un campo descuento_gravado_pct
                    default_vals['descuento_gravado_pct'] = move.descuento_gravado_pct

                if hasattr(move, 'descuento_exento_pct'):
                    default_vals['descuento_exento_pct'] = move.descuento_exento_pct

                if hasattr(move, 'descuento_no_sujeto_pct'):
                    default_vals['descuento_no_sujeto_pct'] = move.descuento_no_sujeto_pct

                if hasattr(move, 'descuento_global_monto'):
                    default_vals['descuento_global_monto'] = move.descuento_global_monto

                _logger.info("SIT Preparing reversal for move_id=%s → reversed_entry_id=%s | inv_refund_id=%s", move.id, default_vals['reversed_entry_id'], default_vals['inv_refund_id'])

                invoice_lines_vals = []
                _logger.info("SIT Invoice Lines: %s", move.invoice_line_ids)

                for line in move.invoice_line_ids:
                    _logger.info("SIT display type: %s", line.display_type)
                    nombre_generado = None
                    if line.display_type not in [False, 'product'] or line.custom_discount_line:
                        continue
        # --- FLUJO DE COMPRAS ---
        else:
            _logger.info("SIT: Movimiento de COMPRA (%s) detectado. Usando flujo estándar de Odoo.", self.move_type)

            # Agregamos la bandera para evitar recursión
            ctx = dict(self.env.context, skip_refund_recursion=True)

            # Forzamos el tipo correcto antes de pasar al flujo estándar
            if self.move_type != constants.IN_INVOICE:
                _logger.info("SIT: Ajustando move_type a 'in_refund' para la nota de crédito de compra.")
                self.move_type = constants.IN_REFUND

            return super(AccountMoveReversal, self.with_context(ctx)).refund_moves()


from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo constants [purchase-account_move_reverse]")
except ImportError as e:
    _logger.error(f"Error al importar 'constants': {e}")
    constants = None

class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    # Campo temporal para controlar tipo de diario
    journal_type = fields.Selection(
        [('sale', 'Venta'), ('purchase', 'Compra')],
        string='Tipo de Diario',
        required=False,
    )

    # Diario final
    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        domain="[('type','=',journal_type)]",
        required=True,
        help="Diario donde se registrará la Nota de Crédito o Nota de Débito."
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        move_ids = self._context.get('active_ids', [])
        if not move_ids:
            _logger.info("SIT: No se encontraron facturas activas en context.")
            return res

        move = self.env['account.move'].browse(move_ids[0])
        _logger.info("SIT: Move type reverse: %s.", move.move_type)

        # Asignar tipo de diario según factura
        if move.move_type in ['out_invoice', 'out_refund']:
            res['journal_type'] = 'sale'
            _logger.info("SIT: Tipo de diario por defecto = venta")
        elif move.move_type in ['in_invoice', 'in_refund']:
            res['journal_type'] = 'purchase'
            res['journal_id'] = False  # Evitar asignación automática
            _logger.info("SIT: Tipo de diario por defecto = compra")
        else:
            _logger.warning("SIT: Tipo de factura desconocido, no se asigna tipo de diario")

        # Si la empresa NO aplica facturación electrónica → usar comportamiento estándar
        if not move.company_id or not move.company_id.sit_facturacion:
            _logger.info("SIT: Empresa no aplica facturación electrónica, se usa flujo estándar de Odoo.")
            return res

        # Si es factura de compra → usar comportamiento estándar
        if move.move_type in (constants.IN_INVOICE, constants.IN_REFUND):
            _logger.info("SIT: Es factura de compra, se usa flujo estándar de Odoo.")
            return res

        # --- Solo aplicar lógica personalizada para facturas de venta ---
        _logger.info("SIT-Purchase: Wizard abierto para reversión de factura ID=%s, tipo=%s, tipo documento=%s", move.id, move.move_type, move.sit_tipo_documento_id)

        # Asignar diario por defecto si existe
        # if not res.get('journal_id'):
        #     journal_default = self.env['account.journal'].search([('type', '=', res.get('journal_type'))], limit=1)
        #     if journal_default:
        #         res['journal_id'] = journal_default.id
        #         _logger.info("SIT: Diario asignado por defecto ID=%s, Nombre=%s", journal_default.id, journal_default.name)

        # Leer tipo de documento de la factura original (sin asignarlo al wizard)
        doc = False
        if move.move_type == 'in_refund':  # Nota de crédito
            doc = self.env['account.journal.tipo_documento.field'].search([('codigo', '=', '05')], limit=1)
            _logger.info(
                "SIT: Tipo de documento original de la factura = %s (Nota de crédito)",
                doc.valores if doc else "None"
            )
        elif move.move_type == 'in_debit':  # Nota de débito
            doc = self.env['account.journal.tipo_documento.field'].search([('codigo', '=', '06')], limit=1)
            _logger.info(
                "SIT: Tipo de documento original de la factura = %s (Nota de débito)",
                doc.valores if doc else "None"
            )
        else:  # Factura normal u otros
            doc = self.env['account.journal.tipo_documento.field'].search([('codigo', 'in', ['01', '03', '11'])], limit=1)
            _logger.info(
                "SIT: Tipo de documento original de la factura = %s (Factura normal u otros)",
                doc.valores if doc else "None"
            )
        # Guardar doc_id en context si luego necesitas usarlo para crear la reversión
        if doc:
            self = self.with_context(default_doc_id=doc.id)

        return res

    @api.onchange('journal_type')
    def _onchange_journal_type(self):
        if self.journal_type:
            domain = [('type', '=', self.journal_type)]
            _logger.info("SIT: Aplicando domain de diarios: %s", domain)
            return {'domain': {'journal_id': domain}}
        return {'domain': {'journal_id': []}}

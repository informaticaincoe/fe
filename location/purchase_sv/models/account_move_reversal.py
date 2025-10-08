from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)

class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    # Campo temporal para controlar tipo de diario
    journal_type = fields.Selection(
        [('sale', 'Venta'), ('purchase', 'Compra')],
        string='Tipo de Diario',
        required=True,
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
        _logger.info("SIT: Wizard abierto para reversión de factura ID=%s, tipo=%s", move.id, move.move_type)

        # Asignar tipo de diario según factura
        if move.move_type in ['out_invoice', 'out_refund']:
            res['journal_type'] = 'sale'
            _logger.info("SIT: Tipo de diario por defecto = venta")
        elif move.move_type in ['in_invoice', 'in_refund']:
            res['journal_type'] = 'purchase'
            _logger.info("SIT: Tipo de diario por defecto = compra")
        else:
            _logger.warning("SIT: Tipo de factura desconocido, no se asigna tipo de diario")

        # Asignar diario por defecto si existe
        journal_default = self.env['account.journal'].search([('type', '=', res.get('journal_type'))], limit=1)
        if journal_default:
            res['journal_id'] = journal_default.id
            _logger.info("SIT: Diario asignado por defecto ID=%s, Nombre=%s", journal_default.id, journal_default.name)

        return res

    @api.onchange('journal_type')
    def _onchange_journal_type(self):
        if self.journal_type:
            domain = [('type', '=', self.journal_type)]
            _logger.info("SIT: Aplicando domain de diarios: %s", domain)
            return {'domain': {'journal_id': domain}}
        return {'domain': {'journal_id': []}}

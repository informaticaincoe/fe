##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, api, fields, _
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Coloco las funciones de WS aqui para limpiar el codigo
# de funciones que no ayudan a su lectura
try:
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo constants [hacienda_payment_terms-account_move]")
except ImportError as e:
    _logger.error(f"Error al importar 'constants': {e}")
    constants = None

class AccountMove(models.Model):
    _inherit = "account.move"

    @api.onchange('invoice_payment_term_id')
    def _onchange_(self):
        for record in self:
            # Validar si es compra normal sin sujeto excluido
            if record.move_type in (constants.IN_INVOICE, constants.IN_REFUND):
                tipo_doc = record.journal_id.sit_tipo_documento
                if not tipo_doc or tipo_doc.codigo != constants.COD_DTE_FSE:
                    _logger.info("SIT Es una compra normal (sin sujeto excluido). Se omite _onchange_ de condiciones de pago.")
                    return

            # Validar si aplica facturación electrónica
            if not (record.company_id and record.company_id.sit_facturacion):
                _logger.info("SIT No aplica facturación electrónica. Se omite _onchange_ de condiciones de pago.")
                return

            con_pag = record.invoice_payment_term_id.condiciones_pago
            if con_pag:
                if con_pag == "1":
                    record.condiciones_pago = con_pag
                    record.sit_plazo = False
                    record.sit_periodo = False
                if con_pag == "2":
                    record.condiciones_pago = con_pag
                    record.sit_plazo = record.invoice_payment_term_id.sit_plazo or False
                    record.sit_periodo = record.invoice_payment_term_id.sit_periodo or False

class AccountMoveReversal(models.TransientModel):
    """
    Account move reversal wizard, it cancel an account move by reversing it.
    """
    _inherit = 'account.move.reversal'

    @api.depends('move_ids')
    def _compute_journal_id(self):
        for record in self:
            _logger.info("SIT _compute_journal_id | Iniciando cálculo para record ID=%s", record.id)

            # Buscar el diario con código 'NDC' y que pertenezca a la misma empresa que el record
            # j_id = self.env['account.journal'].search([('code', '=', 'NDC')], limit=1)
            j_id = self.env['account.journal'].search([
                ('sit_tipo_documento', '!=', False),
                ('sit_tipo_documento.codigo', '=', constants.COD_DTE_NC),
                ('company_id', '=', record.company_id.id)
            ], limit=1)

            if j_id:
                _logger.info("SIT _compute_journal_id | Diario 'NDC' encontrado: ID=%s, Nombre=%s", j_id.id, j_id.name)
            else:
                _logger.warning("SIT _compute_journal_id | No se encontró diario con código 'NDC' para la empresa ID=%s.", record.company_id.id)

            # Si ya hay un diario asignado manualmente
            if record.journal_id:
                record.journal_id = record.journal_id
                _logger.info("SIT _compute_journal_id | Diario ya asignado en el record: ID=%s, Nombre=%s", record.journal_id.id, record.journal_id.name)
            else:
                # Si no hay diario asignado, se intenta tomar el de los movimientos asociados
                journals = record.move_ids.journal_id.filtered(lambda x: x.active)
                if journals:
                    record.journal_id = journals[0]
                    _logger.info("SIT _compute_journal_id | Diario tomado de move_ids: ID=%s, Nombre=%s", record.journal_id.id, record.journal_id.name)
                else:
                    _logger.warning("SIT _compute_journal_id | No se encontró ningún diario activo en move_ids para la empresa ID=%s.", record.company_id.id)

            # Finalmente, si existe el diario NDC, se fuerza como diario de reversión
            if j_id:
                record.journal_id = j_id
                _logger.info("SIT _compute_journal_id | Diario forzado a 'NDC': ID=%s, Nombre=%s", record.journal_id.id, record.journal_id.name)

            _logger.info("SIT _compute_journal_id | Finalizado para record ID=%s con journal_id=%s", record.id, record.journal_id.id if record.journal_id else None)

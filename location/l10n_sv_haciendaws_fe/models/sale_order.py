import logging
from odoo import models, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils [hacienda ws-sale_order]")
except ImportError as e:
    _logger.error(f"Error al importar 'constants': {e}")
    constants = None

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.constrains('journal_id', 'partner_id')
    def _check_journal_and_partner_identification(self):
        for order in self:
            _logger.info("=== Validando cotización ID %s ===", order.id)

            if not (order.company_id and order.company_id.sit_facturacion):
                _logger.info("SIT: La empresa %s no aplica a facturación electrónica, saltando validación de journal/partner.", order.company_id.name)
                continue

            _logger.info("Journal: %s", order.journal_id)
            _logger.info("sit_tipo_documento: %s", order.journal_id.sit_tipo_documento)
            _logger.info("sit_tipo_documento.codigo: %s", getattr(order.journal_id.sit_tipo_documento, 'codigo', None))
            _logger.info("Partner: %s", order.partner_id)
            _logger.info("l10n_latam_identification_type_id: %s", order.partner_id.l10n_latam_identification_type_id)
            _logger.info("l10n_latam_identification_type_id.codigo: %s",
                         getattr(order.partner_id.l10n_latam_identification_type_id, 'codigo', None))

            if not order.journal_id:
                raise ValidationError(_("Debe seleccionar un diario para la cotización."))

            tipo_doc_journal = order.journal_id.sit_tipo_documento
            tipo_doc_partner = order.partner_id.l10n_latam_identification_type_id

            if tipo_doc_journal and tipo_doc_journal.codigo in (constants.COD_DTE_CCF, constants.COD_DTE_FEX):
                if tipo_doc_partner and tipo_doc_partner.codigo == constants.COD_TIPO_DOCU_DUI:
                    raise ValidationError(_(
                        "El cliente tiene el tipo de documento '%s' que no es válido para el tipo de documento del diario."
                    ) % (tipo_doc_partner.name or tipo_doc_partner.codigo))

            # Validar recinto fiscal
            if tipo_doc_journal and tipo_doc_journal.codigo in (constants.COD_DTE_FEX):
                if not order.recintoFiscal:
                    raise ValidationError("Debe seleccionar un recinto fiscal.")

    @api.onchange("partner_id")
    def _onchange_partner_id_set_journal(self):
        """Al seleccionar el cliente, sugerir el diario definido en el cliente."""
        if self.partner_id and self.partner_id.journal_id:
            # Solo asigna si no hay diario aún
            if not self.journal_id:
                self.journal_id = self.partner_id.journal_id

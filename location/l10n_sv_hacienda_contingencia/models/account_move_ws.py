##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import datetime
import base64
import pyqrcode
import logging
import datetime
import pytz

# Definir la zona horaria de El Salvador
tz_el_salvador = pytz.timezone('America/El_Salvador')

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo constants hacienda contingencia")
except ImportError as e:
    _logger.error(f"Error al importar 'constants': {e}")
    constants = None

class AccountMove(models.Model):
    _inherit = "account.move"

######################################################################################################### FCE-CONTINGENCIA
    def sit_obtener_payload_dte_info(self, ambiente, doc_firmado):
        _logger.info("Contingencia-ws Generando payload dte info desde contingencia: %s", self.hacienda_codigoGeneracion_identificacion)
        invoice_info = {}
        invoice_info["ambiente"] = ambiente
        invoice_info["idEnvio"] = "00001"
        invoice_info["tipoDte"] = self.journal_id.sit_tipo_documento.codigo

        invoice_info["version"] = self.journal_id.sit_tipo_documento.version
        if doc_firmado:
            invoice_info["documento"] = doc_firmado
        else:
            invoice_info["documento"] = None
        invoice_info["codigoGeneracion"] = self.sit_generar_uuid()

        return invoice_info

    def sit_generar_uuid(self):
        import uuid
        # Genera un UUID versión 4 (basado en números aleatorios)
        uuid_aleatorio = uuid.uuid4()
        uuid_cadena = str(uuid_aleatorio)
        return uuid_cadena.upper()

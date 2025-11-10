##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.tools import float_repr
from odoo.addons.l10n_sv_haciendaws_fe.afip_utils import get_invoice_number_from_response
import base64
import pyqrcode
import qrcode
import os
from PIL import Image
import io

base64.encodestring = base64.encodebytes
import json
import requests

import logging
import sys
import traceback
from datetime import datetime

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import config_utils
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils [hacienda-fse account_move]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None
    constants = None

class AccountMove(models.Model):
    _inherit = "account.move"

#---------------------------------------------------------------------------------------------
# SUJETO EXCLUIDO
#---------------------------------------------------------------------------------------------

    def sit_debug_mostrar_json_fse(self):
        """Solo muestra el JSON generado de la factura FSE (código 14) sin enviarlo."""
        # 1 Validar que solo haya una factura seleccionada
        if len(self) != 1:
            raise UserError("Selecciona una sola factura para depurar el JSON.")

        # 2 Verificar que sea COMPRA (in_invoice) y tipo de documento FSE (código 14)
        tipo_doc = self.journal_id.sit_tipo_documento
        if self.move_type != constants.IN_INVOICE or (tipo_doc and tipo_doc.codigo != constants.COD_DTE_FSE):
            _logger.info("SIT: omitiendo generación de JSON — aplica solo para compras FSE (in_invoice, código 14). Tipo actual: %s, Código: %s",
                self.move_type, tipo_doc.codigo if tipo_doc else None
            )
            return True

        # 3 Si la facturación electrónica está desactivada, no hacemos nada
        if not self.env.company.sit_facturacion:
            _logger.info("FE OFF: omitiendo sit_debug_mostrar_json_fse")
            return True  # no bloquea la UI

        # 4 Generar y mostrar el JSON FSE
        invoice_json = self.sit__fse_base_map_invoice_info_dtejson()

        pretty_json = json.dumps(invoice_json, indent=4, ensure_ascii=False)
        _logger.info("📄 JSON DTE FSE generado:\n%s", pretty_json)
        print("📄 JSON DTE FSE generado:\n", pretty_json)
        return True

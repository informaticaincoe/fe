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
# Exportacion
#---------------------------------------------------------------------------------------------

    def sit_debug_mostrar_json_fse(self):
        """Solo muestra el JSON generado de la factura FSE sin enviarlo."""
        if not self.env.company.sit_facturacion:
            _logger.info("FE OFF: omitiendo sit_debug_mostrar_json_fse")
            return True  # no bloquea la UI

        if len(self) != 1:
            raise UserError("Selecciona una sola factura para depurar el JSON.")

        invoice_json = self.sit__fse_base_map_invoice_info_dtejson()

        import json
        pretty_json = json.dumps(invoice_json, indent=4, ensure_ascii=False)
        _logger.info("📄 JSON DTE FSE generado:\n%s", pretty_json)
        print("📄 JSON DTE FSE generado:\n", pretty_json)

        return True

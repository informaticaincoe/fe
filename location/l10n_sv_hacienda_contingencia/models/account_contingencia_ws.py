##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import datetime
import base64
import pyqrcode

import pytz
import logging

_logger = logging.getLogger(__name__)

tz_el_salvador = pytz.timezone('America/El_Salvador')

try:
    from odoo.addons.common_utils.utils import config_utils
    from odoo.addons.common_utils.utils import constants

    _logger.info("SIT Modulo config_utils [contingencia ws]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None
    constants = None


class sit_AccountContingencia(models.Model):
    _inherit = "account.contingencia1"

######################################################################################################### FCE-CONTINGENCIA
    def sit__contingencia_base_map_invoice_info(self):
        _logger.info("SIT CONTINGENCIA sit__contingencia_base_map_invoice_info self = %s", self)

        invoice_info = {}
        nit = self.company_id.vat
        nit = nit.replace("-", "")
        invoice_info["nit"] = nit
        invoice_info["activo"] = True
        invoice_info["passwordPri"] = self.company_id.sit_passwordPri
        _logger.info("SIT sit__contingencia_base_map_invoice_info = %s", invoice_info)

        invoice_info["dteJson"] = self.sit__contingencia_base_map_invoice_info_dtejson()
        return invoice_info

    def sit__contingencia_base_map_invoice_info_dtejson(self):
        _logger.info("SIT Contingencia sit__contingencia_base_map_invoice_info_dtejson self = %s", self)
        invoice_info = {}

        invoice_info["identificacion"] = self.sit__contingencia__base_map_invoice_info_identificacion()
        invoice_info["emisor"] = self.sit__contingencia__base_map_invoice_info_emisor()

        detalleDTE = self.sit_contingencia_base_map_invoice_info_detalle_DTE()
        _logger.info("SIT Cuerpo documento =%s", detalleDTE)
        invoice_info["detalleDTE"] = detalleDTE
        # if str(invoice_info["cuerpoDocumento"]) == 'None':
        # raise UserError(_('La Factura no tiene linea de Productos Valida.'))
        invoice_info["motivo"] = self.sit_contingencia__base_map_invoice_info_motivo()
        return invoice_info

    def sit__contingencia__base_map_invoice_info_identificacion(self):
        _logger.info("SIT Contingencia sit_base_map_invoice_info_identificacion self contingencia_ws= %s", self)
        invoice_info = {}
        invoice_info["version"] = int(
            config_utils.get_config_value(self.env, 'version_contingencia', self.company_id.id) or 3)  # 3

        ambiente = None
        if config_utils:
            ambiente = config_utils.compute_validation_type_2(self.env)
        invoice_info["ambiente"] = ambiente

        invoice_info["codigoGeneracion"] = self.hacienda_codigoGeneracion_identificacion  # company_id.sit_uuid.upper()

        if self.fechaHoraTransmision:
            FechaEmi = self.fechaHoraTransmision
            FechaEmi = FechaEmi.replace(tzinfo=pytz.UTC).astimezone(tz_el_salvador)
        else:
            FechaEmi = datetime.datetime.now()
            FechaEmi = FechaEmi.astimezone(tz_el_salvador)

        _logger.info("SIT FechaEmi = %s (%s)", FechaEmi, type(FechaEmi))
        invoice_info["fTransmision"] = FechaEmi.strftime('%Y-%m-%d')
        invoice_info["hTransmision"] = FechaEmi.strftime('%H:%M:%S')
        _logger.info("SIT  sit__contingencia__base_map_invoice_info_identificacion = %s", invoice_info)
        return invoice_info

    def sit__contingencia__base_map_invoice_info_emisor(self):
        _logger.info("SIT Contingencia sit__contingencia__base_map_invoice_info_emisor self = %s", self)

        invoice_info = {}

        nit = self.company_id.vat
        if nit:
            nit = nit.replace("-", "")
        invoice_info["nit"] = nit

        nrc = self.company_id.company_registry
        invoice_info["nombre"] = self.company_id.name
        invoice_info["nombreResponsable"] = self.invoice_user_id.partner_id.user_id.partner_id.name
        tipo_doc = None
        numeroDocumento = None

        if self.invoice_user_id.partner_id.user_id.partner_id.vat:
            numeroDocumento = self.invoice_user_id.partner_id.user_id.partner_id.vat
            tipo_doc = constants.COD_TIPO_DOCU_NIT
        elif self.invoice_user_id.partner_id.user_id.partner_id.dui:
            numeroDocumento = self.invoice_user_id.partner_id.user_id.partner_id.dui
            tipo_doc = constants.COD_TIPO_DOCU_DUI

        invoice_info["numeroDocResponsable"] = numeroDocumento
        invoice_info["tipoDocResponsable"] = tipo_doc
        invoice_info["tipoEstablecimiento"] = self.company_id.tipoEstablecimiento.codigo
        invoice_info["codEstableMH"] = None
        invoice_info["codPuntoVenta"] = None

        if self.company_id.phone:
            invoice_info["telefono"] = self.company_id.phone
        else:
            invoice_info["telefono"] = None

        invoice_info["correo"] = self.company_id.email

        return invoice_info

    def sit_contingencia_base_map_invoice_info_detalle_DTE(self):
        _logger.info(
            "SIT Contingencia sit_contingencia_base_map_invoice_info_detalle_DTE self ------------------------- = (%s)  %s",
            self, self.sit_facturas_relacionadas)
        lines = []
        item_numItem = 0

        for line in self.sit_facturas_relacionadas:
            item_numItem += 1
            line_temp = {}
            lines_tributes = []
            line_temp["noItem"] = item_numItem
            codigoGeneracion = line.hacienda_codigoGeneracion_identificacion
            if not codigoGeneracion:
                MENSAJE = "La Factura " + line.name + " no tiene código de Generacion"
                raise UserError(_(MENSAJE))
            line_temp["codigoGeneracion"] = line.hacienda_codigoGeneracion_identificacion
            tipoDoc = str(line.journal_id.sit_tipo_documento.codigo)
            line_temp["tipoDoc"] = tipoDoc
            lines.append(line_temp)

        return lines

    def sit_contingencia__base_map_invoice_info_motivo(self):
        _logger.info("SIT Contingencia sit_contingencia__base_map_invoice_info_motivo self = %s", self)

        invoice_info = {}

        FechaEmi = self.sit_fInicio_hInicio
        FechaEmi = FechaEmi.astimezone(tz_el_salvador)

        FechaFin = self.sit_fFin_hFin
        FechaFin = FechaFin.astimezone(tz_el_salvador)
        _logger.info("SIT FechaEmi = %s (%s)", FechaEmi, type(FechaEmi))

        invoice_info["fInicio"] = FechaEmi.strftime('%Y-%m-%d')
        invoice_info["fFin"] = FechaFin.strftime('%Y-%m-%d')
        invoice_info["hInicio"] = FechaEmi.strftime('%H:%M:%S')
        invoice_info["hFin"] = FechaFin.strftime('%H:%M:%S')

        invoice_info["tipoContingencia"] = int(self.sit_tipo_contingencia.codigo)
        if self.sit_tipo_contingencia_otro:
            motivoContingencia = self.sit_tipo_contingencia_otro
        else:
            motivoContingencia = None
        invoice_info["motivoContingencia"] = motivoContingencia

        return invoice_info

    def sit_obtener_payload_contingencia_dte_info(self, documento):
        _logger.info("SIT Contingencia sit_obtener_payload_contingencia_dte_info Contingencia = %s", self.id)
        invoice_info = {}
        nit = self.company_id.vat
        nit = nit.replace("-", "")
        invoice_info["nit"] = nit
        invoice_info["documento"] = documento
        return invoice_info

    def sit_generar_uuid(self):
        import uuid
        # Genera un UUID versión 4 (basado en números aleatorios)
        uuid_aleatorio = uuid.uuid4()
        uuid_cadena = str(uuid_aleatorio)
        return uuid_cadena.upper()
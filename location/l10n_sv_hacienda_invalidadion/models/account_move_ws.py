##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import datetime, date, timedelta
import base64
import pyqrcode
import pytz
import logging
import uuid

_logger = logging.getLogger(__name__)

# Zona horaria El Salvador
tz_el_salvador = pytz.timezone('America/El_Salvador')
COD_FE = "01"
COD_FSE = "14"
from ..constantes_utils import get_constantes_anulacion
from pytz import timezone, UTC

ZONA_HORARIA = timezone('America/El_Salvador')

try:
    from odoo.addons.common_utils.utils import config_utils
    _logger.info("SIT Modulo config_utils invalidacion ws")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None

class AccountMove(models.Model):
    _inherit = "account.move"

    ######################################### F-ANULACION

    def _get_version_invalidacion(self):
        """Helper para obtener la version_invalidacion de la configuración de empresa."""
        if config_utils:
            version = config_utils.get_config_value(self.env, 'version_invalidacion', self.company_id.id)
            if version is None:
                _logger.warning("No se encontró 'version_invalidacion' en configuración.")
                return 2
            # Si viene como lista, toma el primer elemento
            if isinstance(version, list):
                version = version[0]

            try:
                return int(version)
            except (ValueError, TypeError):
                _logger.warning("Valor inválido para 'version_invalidacion': %s. Usando valor por defecto.", version)
                return 2
        else:
            _logger.warning("common_utils no está instalado. Usando valor por defecto para version_invalidacion.")
            return 2

    def sit_anulacion_base_map_invoice_info(self):
        _logger.info("SIT [INICIO] sit_anulacion_base_map_invoice_info: self.id=%s, sel.factura_reemplazar=%s", self.id, self.sit_factura_a_reemplazar.company_id)

        invoice_info = {}
        vat = self.sit_factura_a_reemplazar.company_id.vat
        if isinstance(vat, str):
            nit = vat.replace("-", "")
        else:
            nit = None

        invoice_info["nit"] = nit
        invoice_info["activo"] = True
        invoice_info["passwordPri"] = self.company_id.sit_passwordPri

        _logger.info("SIT company_id.vat = %s, passwordPri = %s", nit, self.company_id.sit_passwordPri)

        invoice_info["dteJson"] = self.sit_anulacion_base_map_invoice_info_dtejson()
        _logger.info("SIT sit_anulacion_base_map_invoice_info generado: %s", invoice_info)
        return invoice_info

    def sit_anulacion_base_map_invoice_info_dtejson(self):
        _logger.info("SIT [INICIO] sit_anulacion_base_map_invoice_info_dtejson self=%s", self)
        invoice_info = {}
        invoice_info["identificacion"] = self.sit_invalidacion_base_map_invoice_info_identificacion()
        invoice_info["emisor"] = self.sit_invalidacion_base_map_invoice_info_emisor()
        invoice_info["documento"] = self.sit_invalidacion_base_map_invoice_info_documento()
        invoice_info["motivo"] = self.sit_invalidacion_base_map_invoice_info_motivo()

        _logger.info("SIT [RESULT] DTE JSON anulacion generado: %s", invoice_info)
        return invoice_info

    def sit_invalidacion_base_map_invoice_info_identificacion(self):
        _logger.info("SIT [INICIO] Identificación para anulación: self.id=%s", self.id)

        invoice_info = {}
        FechaHoraAnulacion = None
        invoice_info["version"] = self._get_version_invalidacion()
        ambiente = str(get_constantes_anulacion()['AMBIENTE']) #"00" if self._compute_validation_type_2() == 'homologation' else "01"
        invoice_info["ambiente"] = ambiente

        if self.sit_codigoGeneracion_invalidacion:
            invoice_info["codigoGeneracion"] = self.sit_codigoGeneracion_invalidacion
        else:
            invoice_info["codigoGeneracion"] = self.sit_generar_uuid()  # company_id.sit_uuid.upper()

        import datetime, pytz, os
        os.environ["TZ"] = "America/El_Salvador"
        fecha_actual = datetime.datetime.now(pytz.timezone("America/El_Salvador"))
        _logger.info("Fecha en sesion 1: %s", fecha_actual)

        if self.sit_evento_invalidacion.sit_fec_hor_Anula:
            utc_dt = self.sit_evento_invalidacion.sit_fec_hor_Anula.replace(tzinfo=UTC)
            FechaHoraAnulacion = utc_dt.astimezone(ZONA_HORARIA)
            _logger.info("SIT campo fecha anulacion: =%s", FechaHoraAnulacion)
        else:
            FechaHoraAnulacion = fecha_actual#datetime.now() - timedelta(hours=6)
            _logger.info("SIT fecha anulacion: =%s", FechaHoraAnulacion)

        invoice_info["fecAnula"] = FechaHoraAnulacion.strftime('%Y-%m-%d')
        invoice_info["horAnula"] = FechaHoraAnulacion.strftime('%H:%M:%S')

        _logger.info("SIT Identificación: ambiente=%s, codigoGeneracion=%s, fec=%s, hor=%s",
                     ambiente, invoice_info["codigoGeneracion"],
                     invoice_info["fecAnula"], invoice_info["horAnula"])
        _logger.info("SIT Identificación json: %s", invoice_info)
        return invoice_info


    def sit_invalidacion_base_map_invoice_info_emisor(self):
        _logger.info("SIT [INICIO] Emisor: self.id=%s", self.id)

        invoice_info = {}
        nit = self.company_id.vat.replace("-", "")
        invoice_info.update({
            "nit": nit,
            "nombre": self.company_id.name,
            "tipoEstablecimiento": self.company_id.tipoEstablecimiento.codigo,
            "nomEstablecimiento": self.company_id.tipoEstablecimiento.valores,
            "codEstableMH": self.journal_id.sit_codestable,
            "codEstable": self.journal_id.sit_codestable,
            "codPuntoVentaMH": self.journal_id.sit_codpuntoventa,
            "codPuntoVenta": self.journal_id.sit_codpuntoventa,
            "telefono": self.company_id.phone or None,
            "correo": self.company_id.email
        })

        _logger.info("SIT Emisor: %s", invoice_info)
        return invoice_info

    tz_el_salvador = pytz.timezone('America/El_Salvador')

    def sit_invalidacion_base_map_invoice_info_documento(self):
        _logger.info("SIT [INICIO] Documento: self.id=%s", self.id)

        invoice_info = {
            "tipoDte": self.journal_id.sit_tipo_documento.codigo,
            "codigoGeneracion": self.hacienda_codigoGeneracion_identificacion,
            "selloRecibido": self.hacienda_selloRecibido,
            "numeroControl": self.name,
            "montoIva": round(self.amount_total, 2),
        }

        # fecha_facturacion = (datetime.strptime(self.fecha_facturacion_hacienda, '%Y-%m-%d')
        #                      if isinstance(self.fecha_facturacion_hacienda, str)
        #                      else self.fecha_facturacion_hacienda)

        # --- Procesamiento robusto de fecha ---
        fecha_facturacion = None
        raw_date = self.invoice_date #self.fecha_facturacion_hacienda
        _logger.info("Fecha facturacion: %s", raw_date)
        try:
            if not raw_date:
                _logger.info("No hay valor en 'fecha_facturacion_hacienda'.")
                raise UserError("No se encontró la fecha de facturación enviada a Hacienda")

            elif isinstance(raw_date, str):
                try:
                    fecha_facturacion = datetime.fromisoformat(raw_date)
                except ValueError:
                    try:
                        fecha_facturacion = datetime.strptime(raw_date, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        fecha_facturacion = datetime.strptime(raw_date, '%Y-%m-%d')
                if fecha_facturacion.tzinfo is None:
                    fecha_facturacion = tz_el_salvador.localize(fecha_facturacion)
                # Ajuste de zona horaria
                fecha_facturacion -= timedelta(hours=6)

            elif isinstance(raw_date, datetime):
                fecha_facturacion = raw_date
                if fecha_facturacion.tzinfo is None:
                    fecha_facturacion = tz_el_salvador.localize(fecha_facturacion)
                fecha_facturacion -= timedelta(hours=6)

            elif isinstance(raw_date, date):
                fecha_facturacion = datetime.combine(raw_date, datetime.min.time())
                fecha_facturacion = tz_el_salvador.localize(fecha_facturacion)
                _logger.info("Fecha tipo Date: %s", fecha_facturacion)

            else:
                raise ValueError(f"'fecha_facturacion_hacienda' no es un valor válido: {type(raw_date)}")

            invoice_info["fecEmi"] = fecha_facturacion.strftime('%Y-%m-%d')

        except Exception as e:
            _logger.error("fecha_facturacion no es datetime, es: %s, %s", type(fecha_facturacion), fecha_facturacion)
            raise ValueError("fecha_facturacion no es un datetime válido")

        if self.sit_tipoAnulacion == '2':
            self.sit_codigoGeneracionR = None

        invoice_info["codigoGeneracionR"] = self.sit_codigoGeneracionR or None

        dui = None
        nit = None
        if self.journal_id.sit_tipo_documento.codigo in [COD_FE, COD_FSE]:
            #nit = self.partner_id.dui.replace("-", "") if isinstance(self.partner_id.dui,str) and self.partner_id.dui.strip() else None
            if isinstance(self.partner_id.dui,str) and self.partner_id.dui.strip():
                dui = self.partner_id.dui.replace("-", "")
            elif isinstance(self.partner_id.vat,str) and self.partner_id.vat.strip():
                nit = self.partner_id.vat.replace("-", "")
        else:
            #nit = self.partner_id.vat.replace("-", "") if isinstance(self.partner_id.vat,str) and self.partner_id.vat.strip() else None
            if isinstance(self.partner_id.vat,str) and self.partner_id.vat.strip():
                nit = self.partner_id.vat.replace("-", "")
            elif isinstance(self.partner_id.dui,str) and self.partner_id.dui.strip():
                dui = self.partner_id.dui.replace("-", "")
        _logger.info("SIT Numero de documento: %s, %s", dui, nit)
        #invoice_info["codigoGeneracionR"] = None  # ó self.sit_codigoGeneracionR

        # Datos del receptor
        #dui = self.partner_id.dui or ''
        #nit = dui.replace("-", "") if isinstance(dui, str) else None

        if dui:
            nit = dui
        # else:
        #     nit_partner = self.partner_id.fax or ''
        #     nit = nit_partner.replace("-", "") if isinstance(nit_partner, str) else ''

        invoice_info["numDocumento"] = nit
        invoice_info["tipoDocumento"] = (
            self.partner_id.l10n_latam_identification_type_id.codigo
            if nit and self.partner_id.l10n_latam_identification_type_id
            else None
        )
        invoice_info["nombre"] = self.partner_id.name or None
        invoice_info["telefono"] = self.partner_id.phone or None
        invoice_info["correo"] = self.partner_id.email or None

        _logger.info("SIT Documento: %s", invoice_info)
        return invoice_info

    def sit_invalidacion_base_map_invoice_info_motivo(self):
        _logger.info("SIT [INICIO] Motivo anulación: self.id=%s", self.id)

        _logger.info("SIT Empresa-Receptor: self.id=%s", self.partner_id)
        #if self.journal_id.sit_tipo_documento.codigo == COD_FE:
        dui = None
        if self.partner_id:
            if self.partner_id.dui:
                dui = self.partner_id.dui
            else:
                dui = self.partner_id.vat

        if not dui:
            raise UserError(
                _("No se encontró el DUI del responsable en la empresa. Por favor verifique el campo DUI en el partner de la compañía."))

        numDocumento = None
        if self.company_id:
            if self.company_id.sit_uuid:
                numDocumento = self.company_id.sit_uuid

        #nit = self.company_id.partner_id.dui.replace("-", "")
        nit = dui.replace("-", "")
        if numDocumento:
            numDocumento = numDocumento.replace("-", "")

        #Cat-022 Tipo de documento

        invoice_info = {
            "tipoAnulacion": int(self.sit_tipoAnulacion),
            "motivoAnulacion": self.sit_motivoAnulacion,#self.sit_motivoAnulacion if self.sit_tipoAnulacion == 3 else None,
            "nombreResponsable": self.partner_id.name,
            "tipDocResponsable": "36",
            "numDocResponsable": numDocumento,
            "nombreSolicita": self.partner_id.name,
            "tipDocSolicita": "36" if self.partner_id and self.partner_id.vat else "13",
            "numDocSolicita": nit
        }

        if not invoice_info["motivoAnulacion"]:
            invoice_info["motivoAnulacion"] = None

        _logger.info("SIT Motivo anulación: %s", invoice_info)
        return invoice_info

    def _compute_total_iva(self):
        IVA = 0.0
        for linea in self.invoice_line_ids:
            vat_taxes = linea.tax_ids.compute_all(
                linea.price_unit, self.currency_id,
                linea.quantity, product=linea.product_id, partner=self.partner_id,
            )
            if vat_taxes['taxes']:
                tax = vat_taxes['taxes'][0]
                _logger.info("SIT IVA linea: unit=%s, subtotal=%s, total=%s, discount=%s, amount=%s",
                             linea.price_unit, linea.price_subtotal, linea.price_total, linea.discount, tax['amount'])
                IVA += tax['amount']

        IVA = round(IVA, 6)
        _logger.info("SIT _compute_total_iva TOTAL=%s", IVA)
        return IVA

    def sit_obtener_payload_anulacion_dte_info(self, ambiente, doc_firmado):
        _logger.info("SIT [INICIO] Payload envío DTE anulado: self.id=%s", self.id)

        nit = self.company_id.vat.replace("-", "")
        invoice_info = {
            "ambiente": get_constantes_anulacion()['AMBIENTE'],
            "idEnvio": int(self.sit_evento_invalidacion.id),
            "version": self._get_version_invalidacion(),
            "documento": doc_firmado
        }

        _logger.info("SIT Payload generado para envío: %s", invoice_info)
        return invoice_info

    def sit_generar_uuid(self):
        uuid_str = str(uuid.uuid4()).upper()
        _logger.info("SIT UUID generado: %s", uuid_str)
        return uuid_str

    ######################################### F-ANULACION

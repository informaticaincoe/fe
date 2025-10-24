# -*- coding: utf-8 -*-
from odoo import fields, models, api
import logging
import re
import io
import base64
from datetime import date
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import config_utils
    from odoo.addons.common_utils.utils import constants

    _logger.info("SIT Modulo config_utils [hacienda ws-account_move]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None


class account_move(models.Model):
    _inherit = 'account.move'


    @staticmethod
    def _only_digits(val):
        """Devuelve solo los dígitos del valor (sin guiones/plecas/espacios)."""
        import re
        return re.sub(r'\D', '', val or '')

    hacienda_estado = fields.Char(string="Hacienda estado", readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)

    sit_evento_invalidacion = fields.Many2one(
        'account.move.invalidation',  # <--- Definición 1 (Many2one)
        string='Evento de invalidación',
        ondelete='set null',
        index=True,
    )

    has_sello_anulacion = fields.Boolean(
        string="Tiene Sello Anulación",
        compute="_compute_has_sello_anulacion",
        store=False,
        index=True,
    )

    @api.depends('sit_evento_invalidacion.hacienda_selloRecibido_anulacion')
    def _compute_has_sello_anulacion(self):
        for move in self:
            move.has_sello_anulacion = any(
                bool(x.hacienda_selloRecibido_anulacion) for x in move.sit_evento_invalidacion)

    # consumidor final
    tipo_ingreso_id = fields.Many2one(
        comodel_name="account.tipo.ingreso",
        string="Tipo de Ingreso"
    )

    tipo_ingreso_codigo = fields.Char(
        string="Tipo ingreso codigo",
        compute='_compute_get_tipo_ingreso_codigo',
        readonly=True,
        store=False,
    )

    @api.depends('tipo_ingreso_id', 'invoice_date')
    def _compute_get_tipo_ingreso_codigo(self):
        limite = date(2025, 1, 1)
        for rec in self:
            val = "0"
            if rec.invoice_date and rec.invoice_date >= limite and rec.tipo_ingreso_id and rec.tipo_ingreso_id.codigo is not None:
                val = str(rec.tipo_ingreso_id.codigo)
            rec.tipo_ingreso_codigo = val

    tipo_costo_gasto_id = fields.Many2one(
        comodel_name="account.tipo.costo.gasto",
        string="Tipo de Costo/Gasto"
    )

    tipo_costo_gasto_codigo = fields.Char(
        string="Tipo costo gasto",
        compute='_compute_get_tipo_costo_gasto_codigo',
        readonly=True,
        store=False,
    )

    @api.depends('tipo_costo_gasto_id')
    def _compute_get_tipo_costo_gasto_codigo(self):
        for rec in self:
            rec.tipo_costo_gasto_codigo = (f"{rec.tipo_costo_gasto_id.codigo}")

    tipo_operacion = fields.Many2one(
        comodel_name="account.tipo.operacion",
        string="Tipo Operacion"
    )

    tipo_operacion_codigo = fields.Char(
        string="Tipo operacion codigo",
        compute='_compute_get_tipo_operacion_codigo',
        readonly=True,
        store=False,
    )

    clasificacion_facturacion = fields.Many2one(
        comodel_name="account.clasificacion.facturacion",
        string="Clasificacion"
    )

    clasificacion_facturacion_codigo = fields.Char(
        string="Clasificacion facturacion codigo",
        compute='_compute_get_clasificacion_facturacion_codigo',
        readonly=True,
        store=False,
    )

    @api.depends('clasificacion_facturacion')
    def _compute_get_clasificacion_facturacion_codigo(self):
        for rec in self:
            rec.clasificacion_facturacion_codigo = (f"{rec.clasificacion_facturacion.codigo}")

    sector = fields.Many2one(
        comodel_name="account.sector",
        string="Sector"
    )

    sector_codigo = fields.Char(
        string="Sector codigo",
        compute='_compute_get_sector_codigo',
        readonly=True,
        store=False,
    )

    @api.depends('sector')
    def _compute_get_sector_codigo(self):
        for rec in self:
            rec.sector_codigo = (f"{rec.sector.codigo}")

    clase_documento_id = fields.Many2one(
        # comodel_name="account.clasificacion.facturacion",
        # string="Clasificacion"
        string="Clase de documento",
        comodel_name="account.clase.documento"
    )

    clase_documento = fields.Char(
        string="Clase de documento",
        compute='_compute_get_clase_documento',
        readonly=True,
        store=False,
    )

    clase_documento_display = fields.Char(
        string="Clase de documento",
        compute='_compute_get_clase_documento_display',
        readonly=True,
        store=False,
    )

    codigo_tipo_documento = fields.Char(
        string="Código tipo documento",
        readonly=True
    )

    codigo_tipo_documento_display = fields.Char(
        string="Tipo de documento",
        compute='_compute_codigo_tipo_documento_display',
        store=False
    )

    invoice_date = fields.Date(
        string="Fecha",
        readonly=True,
    )

    invoice_month = fields.Char(
        string="Mes",
        compute='_compute_invoice_month',
        store=False
    )

    invoice_year = fields.Char(
        string="Año",
        compute='_compute_invoice_year',
        store=False
    )

    hacienda_selloRecibido = fields.Char(
        string="Sello Recibido",
        readonly=True,
    )

    hacienda_codigoGeneracion_identificacion = fields.Char(
        string="codigo generacion",
        readonly=True,
    )

    numero_control_interno_del = fields.Char(
        string="Numero de control interno DEL",
        readonly=True,
        store=False,
        compute='_compute_get_numero_control_documento_interno_del',
    )

    numero_control_interno_al = fields.Char(
        string="Numero de control interno AL",
        readonly=True,
        store=False,
        compute='_compute_get_numero_control_documento_interno_al',
    )

    numero_documento_del = fields.Char(
        compute='_compute_get_hacienda_codigo_generacion_sin_guion',
    )

    numero_documento_al = fields.Char(
        compute='_compute_get_hacienda_codigo_generacion_sin_guion',
    )

    numero_maquina_registradora = fields.Char(
        string="Numero de maquina registradora",
        compute='_compute_get_numero_maquina_registradora',
        readonly=True,
        store=False,
    )

    total_exento = fields.Monetary(
        string="Ventas extentas",
        readonly=True,
    )

    total_no_sujeto = fields.Monetary(
        string="Ventas no sujetas",
        readonly=True,
    )

    total_gravado_local = fields.Monetary(
        string="Ventas gravadas locales",
        compute='_compute_get_total_gravado',
        readonly=True,
        store=False,
    )

    ventas_exentas_no_sujetas = fields.Monetary(
        string="Ventas internas exentas no sujetas a proporcionalidad",
        compute='_compute_get_ventas_exentas_no_sujetas',
        readonly=True,
        store=False,
    )

    exportaciones_dentro_centroamerica = fields.Monetary(
        string="Exportaciones dentro del area de centroamerica",
        compute='_compute_get_exportaciones_dentro_centroamerica',
        readonly=True,
        store=False,
    )

    exportaciones_fuera_centroamerica = fields.Monetary(
        string="Exportaciones fuera del area de centroamerica",
        compute='_compute_get_exportaciones_fuera_centroamerica',
        readonly=True,
        store=False,
    )

    exportaciones_de_servicio = fields.Char(
        string="Exportaciones de servicio",
        compute='_compute_get_exportaciones_de_servicio',
        readonly=True,
        store=False,
    )

    ventas_tasa_cero = fields.Char(
        string="Ventas a zonas francas y DPA (tasa cero)",
        compute='_compute_get_ventas_tasa_cero',
        readonly=True,
        store=False,
    )

    ventas_cuenta_terceros = fields.Char(
        string="ventas a cuenta de terceros no domiciliados",
        compute='_compute_get_ventas_cuenta_terceros',
        readonly=True,
        store=False,
    )

    total_operacion = fields.Monetary(
        string="Total de ventas",
        readonly=True,
    )

    tipo_ingreso_renta = fields.Monetary(
        string="Tipo de ingreso (renta)",
        compute='_compute_get_tipo_ingreso_renta',
        readonly=True,
        store=False,
    )

    numero_anexo = fields.Char(
        string="Número del anexo",
        compute='_compute_get_numero_anexo',
        readonly=True,
    )

    retencion_iva_amount = fields.Monetary(
        string="Retencion IVA 13%",
        readonly=True,
    )

    retencion_iva_amount_1 = fields.Monetary(
        string="Percepción IVA 1%",
        compute="_compute_retencion_iva_amount",
        readonly=True,
        store=False
    )

    amount_tax = fields.Monetary(
        string="Percepción IVA 1%",
        readonly=True,
    )

    # === Campos display (codigo + nombre) === #
    tipo_ingreso_display = fields.Char(
        string="Tipo de Ingreso",
        compute="_compute_tipo_ingreso_display",
        store=False
    )

    tipo_costo_gasto_display = fields.Char(
        string="Tipo de Costo/Gasto",
        compute="_compute_tipo_costo_gasto_display",
        store=False
    )

    tipo_operacion_display = fields.Char(
        string="Tipo de Operación",
        compute="_compute_tipo_operacion_display",
        store=False
    )

    clasificacion_facturacion_display = fields.Char(
        string="Clasificación Facturación",
        compute="_compute_clasificacion_facturacion_display",
        store=False
    )

    sector_display = fields.Char(
        string="Sector",
        compute="_compute_sector_display",
        store=False
    )

    numero_resolucion_anexos_anulados = fields.Char(
        string="Numero resolucion",
        compute="_compute_resolucion_anexos_anulados",
        store=False
    )

    desde_tiquete_preimpreso = fields.Char(
        string="Numero resolucion",
        compute="_compute_desde_tiquete_preimpreso",
        store=False
    )

    hasta_tiquete_preimpreso = fields.Char(
        string="Numero resolucion",
        compute="_compute_hasta_tiquete_preimpreso",
        store=False
    )

    tipo_de_detalle = fields.Char(
        string="Tipo de detalle",
        compute="_compute_tipo_detalle",
        store=False
    )

    desde = fields.Char( # Desde para documentos extraviados y anulados
        string="Desde",
        compute="_compute_desde",
        store=False
    )

    hasta = fields.Char(  # Desde para documentos extraviados y anulados
        string="hasta",
        compute="_compute_hasta",
        store=False
    )

    # === Métodos compute === #

    @api.depends('tipo_operacion', 'invoice_date')
    def _compute_get_tipo_operacion_codigo(self):
        limite = date(2025, 1, 1)
        for rec in self:
            val = "0"
            if rec.invoice_date and rec.invoice_date >= limite and rec.tipo_operacion and rec.tipo_operacion.codigo is not None:
                val = str(rec.tipo_operacion.codigo)
            rec.tipo_operacion_codigo = val

    @api.depends('tipo_ingreso_id')
    def _compute_tipo_ingreso_display(self):
        limite = date(2025, 1, 1)
        for rec in self:
            if rec.invoice_date >= limite:
                rec.tipo_ingreso_display = (
                    f"{rec.tipo_ingreso_id.codigo}. {rec.tipo_ingreso_id.valor}"
                    if rec.tipo_ingreso_id else ""
                )
            else:
                rec.tipo_ingreso_display = ("0")


    @api.depends('tipo_costo_gasto_id')
    def _compute_tipo_costo_gasto_display(self):
        for rec in self:
            rec.tipo_costo_gasto_display = (
                f"{rec.tipo_costo_gasto_id.codigo}. {rec.tipo_costo_gasto_id.valor}"
                if rec.tipo_costo_gasto_id else ""
            )


    @api.depends('tipo_operacion')
    def _compute_tipo_operacion_display(self):
        limite = date(2025, 1, 1)
        for rec in self:
            if rec.invoice_date >= limite:
                rec.tipo_operacion_display = (
                    f"{rec.tipo_operacion.codigo}. {rec.tipo_operacion.valor}"
                    if rec.tipo_operacion else ""
                )
            else:
                rec.tipo_operacion_display = ("0")


    @api.depends('clasificacion_facturacion')
    def _compute_clasificacion_facturacion_display(self):
        for rec in self:
            rec.clasificacion_facturacion_display = (
                f"{rec.clasificacion_facturacion.codigo}. {rec.clasificacion_facturacion.valor}"
                if rec.clasificacion_facturacion else ""
            )


    @api.depends('sector')
    def _compute_sector_display(self):
        for rec in self:
            rec.sector_display = (
                f"{rec.sector.codigo}. {rec.sector.valor}"
                if rec.sector else ""
            )

    @api.depends('invoice_date')
    def _compute_invoice_month(self):
        for record in self:
            if record.invoice_date:
                # Solo número del mes con dos dígitos
                record.invoice_month = record.invoice_date.strftime('%m')
            else:
                record.invoice_month = ''

    @api.depends('invoice_date')
    def _compute_invoice_year(self):
        for record in self:
            if record.invoice_date:
                # Solo número del mes con dos dígitos
                record.invoice_year = record.invoice_date.strftime('%Y')
            else:
                record.invoice_year = ''

    # si es preimpreso
    sit_facturacion = fields.Boolean(
        related='company_id.sit_facturacion',
        readonly=True,
        store=True,
    )

    razon_social = fields.Char(
        string="Cliente/Proveedor",
        related='partner_id.name',
        readonly=True,
        store=False,
    )

    tipo_documento_identificacion = fields.Char(
        string="Tipo documento identificacion",
        compute='_compute_get_tipo_documento',
        readonly=True,
        store=False,
    )

    numero_documento = fields.Char(
        string="Número de documento de identificacion",
        compute='_compute_get_numero_documento',
        readonly=True,
        store=False,
    )

    nit_cliente = fields.Char(
        string="NIT cliente",
        compute='_compute_get_nit',
        readonly=True,
        store=False,
    )

    nrc_cliente = fields.Char(
        string="NRC cliente",
        compute='_compute_get_nrc',
        readonly=True,
        store=False,
    )

    nit_o_nrc_anexo_contribuyentes = fields.Char(
        string="NRC o NIT contribuyente",
        compute='_compute_nit_nrc_anexo_contribuyentes',
        readonly=True,
        store=False,
    )

    nit_company = fields.Char(
        string="NIT o NRC cliente",
        compute='_compute_get_nit_company',
        readonly=True,
        store=False,
    )

    debito_fiscal_contribuyentes = fields.Char(
        string="Debito fiscal",
        compute='_compute_get_debito_fiscal',
        readonly=True,
        store=False,
    )

    debito_fiscal_cuenta_terceros = fields.Char(
        string="Debito fiscal a cuenta de terceros",
        compute='_compute_get_debito_fiscal_terceros',
        readonly=True,
        store=False,
    )

    dui_cliente = fields.Char(
        string="DUI cliente",
        compute='_compute_get_dui_cliente',
        readonly=True,
        store=False,
    )

    codigo_tipo_documento_cliente = fields.Char(
        string="codigo tipo documento cliente",
        compute='_compute_get_codigo_tipo_documento_cliente',
        readonly=True,
        store=False,
    )

    codigo_tipo_documento_cliente_display = fields.Char(
        string="codigo tipo documento cliente",
        compute='_compute_get_codigo_tipo_documento_cliente_display',
        readonly=True,
        store=False,
    )

    documento_sujeto_excluido = fields.Char(
        string="Documento sujeto excluido",
        compute="_compute_documento_sujeto_excluido",
        store=False,
        readonly=True,
    )


    @api.depends('name')
    def _compute_get_clase_documento(self):
        for record in self:
            if record.name.startswith("DTE"):
                _logger.info('name %s ',record.name)
                _logger.info('clase_documento_id %s ',record.clase_documento_id)
                record.clase_documento = '4'
            else:
                record.clase_documento = '1'


    @api.depends('journal_id')
    def _compute_get_clase_documento_display(self):
        for record in self:
            if record.clase_documento == '4':
                record.clase_documento_display = '4. Documento tributario electronico DTE'
            else:
                record.clase_documento_display = '1. Impreso por imprenta o tiquetes'

    @api.depends('journal_id', 'codigo_tipo_documento')
    def _compute_codigo_tipo_documento_display(self):
        for record in self:
            codigo = record.codigo_tipo_documento or ""  # asegura string
            nombre = record.journal_id.name or ""  # asegura string
            if codigo or nombre:
                record.codigo_tipo_documento_display = f"{codigo} {nombre}".strip()
            else:
                record.codigo_tipo_documento_display = ""

    @api.depends('partner_id')
    def _compute_get_tipo_documento(self):
        for record in self:
            if record.partner_id:
                record.tipo_documento_identificacion = record.partner_id.dui
            elif record.partner_vat:
                record.tipo_documento_identificacion = record.partner_id.vat
            else:
                record.tipo_documento_identificacion = ''


    @api.depends('partner_id')
    def _compute_get_numero_documento(self):
        for record in self:
            if record.partner_id and record.partner_id.dui:
                record.numero_documento = "01"
            elif record.partner_id and record.partner_id.vat:
                record.numero_documento = "03"
            else:
                record.numero_documento = ''


    @api.depends('journal_id')
    def _compute_numero_control_interno_del(self):
        for record in self:
            numero = False  # valor por defecto
            if record.journal_id and record.journal_id.name:
                    numero = "DTE-" + record.journal_id.name

            record.numero_control_interno_del = numero


    @api.depends('journal_id')
    def _compute_get_numero_control_documento_interno_del(self):
        for record in self:
            record.numero_control_interno_del = record.hacienda_codigoGeneracion_identificacion

    @api.depends('journal_id')
    def _compute_get_numero_control_documento_interno_al(self):
        for record in self:
            if record.clase_documento == "4":
                record.numero_control_interno_al = 0
            else:
                record.numero_control_interno_al = 0


    @api.depends('journal_id')
    def _compute_get_hacienda_codigo_generacion_sin_guion(self):
        for record in self:
            record.numero_documento_del_al = record.hacienda_codigoGeneracion_identificacion


    @api.depends('journal_id')
    def _compute_get_numero_maquina_registradora(self):
        for record in self:
            record.numero_maquina_registradora = ''

    @api.depends('journal_id')
    def _compute_get_total_gravado(self):
        for record in self:
            if record.partner_id.country_id.code in ['SV']:
                record.total_gravado_local = record.total_gravado
            else:
                record.total_gravado_local = 0.00


    @api.depends('journal_id')
    def _compute_get_ventas_exentas_no_sujetas(self):
        for record in self:
            record.ventas_exentas_no_sujetas = 0.00


    @api.depends('journal_id')
    def _compute_get_exportaciones_dentro_centroamerica(self):
        for record in self:
            if record.codigo_tipo_documento == '11':
                if record.partner_id.country_id.code in ['SV', 'GT', 'HN', 'CR', 'PA']:
                    record.exportaciones_dentro_centroamerica = record.total_gravado
                else:
                    record.exportaciones_dentro_centroamerica = 0.00
            else:
                record.exportaciones_dentro_centroamerica = 0.00


    @api.depends('journal_id', 'partner_id.country_id', 'codigo_tipo_documento', 'total_gravado')
    def _compute_get_exportaciones_fuera_centroamerica(self):
        for record in self:
            if record.codigo_tipo_documento == '11':
                # Exportaciones fuera de Centroamérica
                if record.partner_id.country_id.code not in ['SV', 'GT', 'HN', 'CR', 'PA']:
                    record.exportaciones_fuera_centroamerica = record.total_gravado
                else:
                    record.exportaciones_fuera_centroamerica = 0.00
            else:
                record.exportaciones_fuera_centroamerica = 0.00


    @api.depends('invoice_line_ids', 'invoice_line_ids.product_id', 'invoice_line_ids.price_subtotal',
                 'codigo_tipo_documento')
    def _compute_get_exportaciones_de_servicio(self):
        for record in self:
            total_servicios = 0.00

            # if record.codigo_tipo_documento == '11':
            for line in record.invoice_line_ids:
                # _logger.info("linea %s", line)
                if record.codigo_tipo_documento == '11' and line.product_id and line.product_id.product_tmpl_id.type == "service":
                    _logger.info("linea 0roduct id %s ", line.product_id.product_tmpl_id.type == "service")
                    total_servicios += line.price_subtotal

            record.exportaciones_de_servicio = total_servicios


    @api.depends('journal_id')
    def _compute_get_ventas_tasa_cero(self):
        for record in self:
            record.ventas_tasa_cero = 0.00


    @api.depends('journal_id')
    def _compute_get_ventas_cuenta_terceros(self):
        for record in self:
            record.ventas_cuenta_terceros = 0.00


    @api.depends('journal_id')
    def _compute_get_tipo_operacion_renta(self):
        for record in self:
            record.tipo_operacion_renta = record.tipo_operacion_renta


    @api.depends('journal_id')
    def _compute_get_tipo_ingreso_renta(self):
        for record in self:
            record.tipo_ingreso_renta = 0.00


    @api.depends('journal_id')
    def _compute_get_numero_anexo(self):
        for record in self:
            ctx = self.env.context
            if ctx.get('numero_anexo'):
                record.numero_anexo = str(ctx['numero_anexo'])

    @api.depends('partner_id.vat', 'partner_id.nrc', 'partner_id.dui', 'invoice_date', 'partner_id.is_company',
                 'partner_id.company_type')
    def _compute_get_dui_cliente(self):
        """
        Q. DUI del Cliente (campo Q del anexo):
        - Solo para Personas Naturales y periodos >= 2022-01-01.
        - Es OPCIONAL; si se llena, H (NIT/NRC) debe quedar VACÍO.
        - Para periodos < 2022-01-01 el DUI debe ir VACÍO.
        - Formato: 9 caracteres sin guiones.
        """
        limite = date(2022, 1, 1)
        for rec in self:
            valor = ""
            is_person = (rec.partner_id and (rec.partner_id.company_type or (
                "company" if rec.partner_id.is_company else "person")) == "person")
            period = rec.invoice_date or limite

            dui = self._only_digits(getattr(rec.partner_id, "dui", ""))

            if is_person and period >= limite and dui:
                # Solo aceptamos exactamente 9 dígitos (la guía exige 9, sin guiones/pleca)
                if len(dui) == 9:
                    valor = dui
                else:
                    # Guardamos vacío para exportación, pero dejamos rastro en logs
                    _logger.warning("DUI inválido (no 9 dígitos) en %s: '%s'", rec.name, dui)
                    valor = ""
            else:
                valor = ""  # Todos los demás casos

            rec.dui_cliente = valor

    @api.depends('partner_id.vat', 'partner_id.nrc', 'partner_id.dui', 'invoice_date', 'partner_id.is_company',
                 'partner_id.company_type')
    def _compute_nit_nrc_anexo_contribuyentes(self):
        """
        H. NIT o NRC del Cliente (campo H del anexo):
        - Personas Naturales:
            * Periodo >= 2022-01-01:
                - Si completa DUI (Q), este campo debe ir VACÍO.
                - Si NO completa DUI, entonces DEBE completar NIT o NRC (preferencia NIT).
            * Periodo < 2022-01-01: este campo es OBLIGATORIO (DUI debe ir vacío).
        - Personas Jurídicas: NUNCA DUI; usar NIT o, si no, NRC.
        Además: limpiar guiones/plecas y no formatear aquí (solo exportar limpio).
        """
        limite = date(2022, 1, 1)
        for rec in self:
            valor = ""
            is_person = (rec.partner_id and (rec.partner_id.company_type or (
                "company" if rec.partner_id.is_company else "person")) == "person")
            period = rec.invoice_date or limite  # si no hay fecha, tratamos como >=2022 para no falsear DUI pre-2022

            nit = self._only_digits(getattr(rec.partner_id, "vat", ""))
            nrc = self._only_digits(getattr(rec.partner_id, "nrc", ""))
            dui = self._only_digits(getattr(rec.partner_id, "dui", ""))

            if is_person:
                if period >= limite:
                    # Si DUI está presente -> H vacío
                    if dui:
                        valor = ""
                    else:
                        # Debe llenar NIT o NRC (preferir NIT)
                        valor = nit or nrc or ""
                else:
                    # Antes de 2022: H obligatorio (preferir NIT, luego NRC); DUI vacío
                    valor = nit or nrc or ""
            else:
                # Jurídicas: usar NIT o NRC; DUI no aplica
                valor = nit or nrc or ""

            rec.nit_o_nrc_anexo_contribuyentes = valor

    @api.depends('partner_id')
    def _compute_get_nrc(self):
        for record in self:
            if record.partner_id.nrc:
                record.nrc_cliente = record.partner_id.nrc
            else:
                record.nrc_cliente = ''
            _logger.info("record.nrc_cliente %s ", record.nrc_cliente)

    @api.depends('partner_id')
    def _compute_get_nit(self):
        for record in self:
            if record.partner_id.vat:
                record.nit_cliente = record.partner_id.vat
            else:
                record.nit_cliente = ''
            _logger.info("record.nit_cliente %s ", record.nit_cliente)

    @api.depends('partner_id.vat', 'partner_id.nrc', 'partner_id.dui', 'invoice_date')
    def _compute_nit_nrc_anexo_contribuyentes(self):
        limite = date(2022, 1, 1)
        for record in self:
            valor = ""
            if record.invoice_date:
                if record.invoice_date >= limite:
                    _logger.info("mayor al limite %s ", record.name)

                    # A partir de 2022
                    if record.partner_id.dui:
                        valor = ""  # si tiene DUI, se deja vacío
                    elif record.partner_id.vat:
                        valor = record.partner_id.vat  # NIT
                    elif record.partner_id.nrc:
                        valor = record.partner_id.nrc  # NRC
                else:
                    # Antes de 2022, NIT o NRC obligatorio
                    if record.partner_id.vat:
                        valor = record.partner_id.vat
                    elif record.partner_id.nrc:
                        valor = record.partner_id.nrc
            _logger.info("record.nit_cliente %s ", record.nit_cliente)
            record.nit_o_nrc_anexo_contribuyentes = valor

    @api.depends('partner_id')
    def _compute_get_debito_fiscal(self):
        for record in self:
            record.debito_fiscal_contribuyentes = record.amount_tax


    @api.depends('partner_id')
    def _compute_get_debito_fiscal_terceros(self):
        for record in self:
            record.debito_fiscal_cuenta_terceros = 0.00

    @api.depends('partner_id')
    def _compute_get_nit_company(self):
        for record in self:
            if record.partner_id.vat:
                record.nit_company = record.partner_id.vat
            else:
                record.nit_company = ''

    def _compute_get_codigo_tipo_documento_cliente(self):
        for record in self:
            codigo = ""
            if record.partner_id.dui:
                codigo = "2"  # DUI
            elif record.partner_id.vat:
                codigo = "1"  # NIT
            elif record.partner_id.nrc:
                codigo = "3"  # NRC

            record.codigo_tipo_documento_cliente = codigo

    @api.depends('codigo_tipo_documento_cliente')
    def _compute_get_codigo_tipo_documento_cliente_display(self):
        """
        Busca en el catálogo el código y devuelve 'codigo. nombre'
        """
        for record in self:
            display = ""
            if record.codigo_tipo_documento_cliente:
                tipo_doc = self.env['account.tipo.documento.identificacion'].search(
                    [('codigo', '=', record.codigo_tipo_documento_cliente)],
                    limit=1
                )
                if tipo_doc:
                    display = f"{tipo_doc.codigo}. {tipo_doc.valor}"
            record.codigo_tipo_documento_cliente_display = display

    @api.depends("codigo_tipo_documento_cliente", "partner_id.vat", "partner_id.dui")
    def _compute_documento_sujeto_excluido(self):
        for record in self:
            if record.codigo_tipo_documento_cliente == "2":  # DUI
                record.documento_sujeto_excluido = record.partner_id.dui or ""
            elif record.codigo_tipo_documento_cliente == "1":  # NIT
                record.documento_sujeto_excluido = record.partner_id.vat or ""
            else:
                record.documento_sujeto_excluido = ""

    @api.depends('invoice_line_ids.price_subtotal', 'codigo_tipo_documento')
    def _compute_retencion_iva_amount(self):
        for record in self:
            if record.codigo_tipo_documento == '14':  # sujeto excluido
                record.retencion_iva_amount_1 = str(round(float(record.amount_untaxed) * 0.01, 2))
            else:
                record.retencion_iva_amount_1 = 0.0

    @api.depends('journal_id')
    def _compute_desde_tiquete_preimpreso(self):
        for record in self:
            if record.clase_documento == '4':
                record.desde_tiquete_preimpreso = 0
            else:
                record.desde_tiquete_preimpreso = 0

    @api.depends('journal_id')
    def _compute_hasta_tiquete_preimpreso(self):
        for record in self:
            if record.clase_documento == '4':
                record.hasta_tiquete_preimpreso = 0
            else:
                record.hasta_tiquete_preimpreso = 0

    @api.depends('journal_id')
    def _compute_tipo_detalle(self):
        for record in self:
            if record.has:
                record.tipo_de_detalle = 'D'
            else:
                record.tipo_de_detalle = ''

    @api.depends('journal_id')
    def _compute_desde(self):
        for record in self:
            if record.clase_documento == '4':
                record.desde = 0
            else:
                record.desde = 0

    @api.depends('journal_id')
    def _compute_hasta(self):
        for record in self:
            if record.clase_documento == '4':
                record.hasta = 0
            else:
                record.hasta = 0

    ###################################################################################################
    #                                  Funciones para descarga de csv                                 #
    ###################################################################################################

    def action_download_csv_anexo(self):
        ctx = self.env.context
        numero_anexo = str(ctx.get("numero_anexo") or self.numero_anexo or "")

        records_to_export = self or self.env[ctx.get("active_model", "account.move")].browse(
            ctx.get("active_ids", []))
        if not records_to_export:
            domain = ctx.get("active_domain") or ctx.get("domain") or []
            if domain:
                records_to_export = self.env["account.move"].search(domain)
        if not records_to_export:
            _logger.warning("Sin registros para exportar (selección vacía y sin dominio activo).")
            return

        view_id = None
        params = ctx.get("params") or {}
        action_xmlid = params.get("action")
        if action_xmlid:
            try:
                action = self.env["ir.actions.act_window"]._for_xml_id(action_xmlid)
                view_id = action.get("view_id") and action["view_id"][0] or None
            except Exception as e:
                _logger.warning("No se pudo resolver view_id desde acción %s: %s", action_xmlid, e)

        csv_data = self.env["anexo.csv.utils"].generate_csv(
            records_to_export, numero_anexo, view_id=view_id, include_header=False
        )

        attachment = self.env["ir.attachment"].create({
            "name": f"anexo_{numero_anexo}.csv",
            "type": "binary",
            "datas": base64.b64encode(csv_data),
            "res_model": "account.move",
            "res_id": False,
            "public": True,
        })
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }


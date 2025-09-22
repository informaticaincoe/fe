# -*- coding: utf-8 -*-
from odoo import fields, models, api
import logging
import re

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
    # consumidor final

    clase_documento = fields.Char(
        string="Clase de documento",
        compute='_compute_get_clase_documento',
        readonly=True,
        store=False,
    )

    codigo_tipo_documento = fields.Char(
        related='journal_id.sit_tipo_documento.codigo',
        store=True
    )

    invoice_month = fields.Char(
        string="Mes",
        compute='_compute_invoice_month',
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

    # hacienda_codigoGeneracion = fields.Char(
    #     string="Numero de documento DEL",
    #     compute='_compute_get_hacienda_codigo_generacion_sin_guion',
    #     readonly=True,
    #     store=False,
    # )

    numero_documento_del_al = fields.Char(
        compute='_compute_get_hacienda_codigo_generacion_sin_guion',
    )

    numero_maquina_registradora = fields.Char(
        string="Numero de maquina registradora",
        compute='_compute_get_numero_maquina_registradora',
        readonly=True,
        store=False,
    )

    total_exento = fields.Char(
        string="Ventas extentas",
        readonly=True,
    )

    total_no_sujeto = fields.Char(
        string="Ventas no sujetas",
        readonly=True,
    )

    total_gravado = fields.Char(
        string="Ventas gravadas",
        readonly=True,
    )

    ventas_exentas_no_sujetas = fields.Char(
        string="Ventas internas exentas no sujetas a proporcionalidad",
        compute='_compute_get_ventas_exentas_no_sujetas',
        readonly=True,
        store=False,
    )

    exportaciones_dentro_centroamerica = fields.Char(
        string="Exportaciones dentro del area de centroamerica",
        compute='_compute_get_exportaciones_dentro_centroamerica',
        readonly=True,
        store=False,
    )

    exportaciones_fuera_centroamerica = fields.Char(
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

    total_operacion = fields.Char(
        string="Total de ventas",
        readonly=True,
    )

    numero_anexo = fields.Char(
        string="Número del anexo",
        compute='_compute_get_numero_anexo',
        readonly=True,
    )

    retencion_iva_amount = fields.Char(
        string="Retencion IVA 13%",
        readonly=True,
    )

    @api.depends('invoice_date')
    def _compute_invoice_month(self):
        for record in self:
            if record.invoice_date:
                # Solo número del mes con dos dígitos
                record.invoice_month = record.invoice_date.strftime('%m')
            else:
                record.invoice_month = ''

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

    nit_o_nrc_cliente = fields.Char(
        string="NIT o NRC cliente",
        compute='_compute_get_nrc_o_nit',
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

    documento_sujeto_excluido = fields.Char(
        string="Documento sujeto excluido",
        compute="_compute_documento_sujeto_excluido",
        store=False,
        readonly=True,
    )

    @api.depends('journal_id')
    def _compute_get_clase_documento(self):
        for record in self:
            if record.sit_facturacion:
                record.clase_documento = '4'
            else:
                record.clase_documento = '1'

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
                if record.journal_id.name.startswith("DTE"):
                    numero = "DTE-" + record.journal_id.name
                elif record.journal_id.name.isdigit():
                    numero = record.journal_id.name
            record.numero_control_interno_del = numero

    @api.depends('journal_id')
    def _compute_get_numero_control_documento_interno_del(self):
        for record in self:
            if record.clase_documento == "4":
                record.numero_control_interno_del = ""

    @api.depends('journal_id')
    def _compute_get_numero_control_documento_interno_al(self):
        for record in self:
            if record.clase_documento == "4":
                record.numero_control_interno_al = ""
            else:
                record.numero_control_interno_al = ""

    @api.depends('journal_id')
    def _compute_get_hacienda_codigo_generacion_sin_guion(self):
        for record in self:
            record.numero_documento_del_al = record.hacienda_codigoGeneracion_identificacion

    @api.depends('journal_id')
    def _compute_get_numero_maquina_registradora(self):
        for record in self:
            record.numero_maquina_registradora = ''

    @api.depends('journal_id')
    def _compute_get_ventas_exentas_no_sujetas(self):
        for record in self:
            record.ventas_exentas_no_sujetas = '0.0'

    @api.depends('journal_id')
    def _compute_get_exportaciones_dentro_centroamerica(self):
        for record in self:
            if record.codigo_tipo_documento == '11':
                if record.partner_id.country_id.code in ['SV', 'GT', 'HN', 'CR', 'PA']:
                    record.exportaciones_dentro_centroamerica = record.total_gravado
                else:
                    record.exportaciones_dentro_centroamerica = 0.0
            else:
                record.exportaciones_dentro_centroamerica = 0.0

    @api.depends('journal_id', 'partner_id.country_id', 'codigo_tipo_documento', 'total_gravado')
    def _compute_get_exportaciones_fuera_centroamerica(self):
        for record in self:
            if record.codigo_tipo_documento == '11':
                # Exportaciones fuera de Centroamérica
                if record.partner_id.country_id.code not in ['SV', 'GT', 'HN', 'CR', 'PA']:
                    record.exportaciones_fuera_centroamerica = record.total_gravado
                else:
                    record.exportaciones_fuera_centroamerica = 0.0
            else:
                record.exportaciones_fuera_centroamerica = 0.0

    @api.depends('journal_id')
    def _compute_get_exportaciones_de_servicio(self):
        for record in self:
            record.exportaciones_de_servicio = '0.0'

    @api.depends('journal_id')
    def _compute_get_ventas_tasa_cero(self):
        for record in self:
            record.ventas_tasa_cero = '0.0'

    @api.depends('journal_id')
    def _compute_get_ventas_cuenta_terceros(self):
        for record in self:
            record.ventas_cuenta_terceros = '0.0'

    @api.depends('journal_id')
    def _compute_get_numero_anexo(self):
        for record in self:
            ctx = self.env.context
            if ctx.get('numero_anexo'):
                record.numero_anexo = str(ctx['numero_anexo'])

    @api.depends('partner_id')
    def _compute_get_nrc_o_nit(self):
        for record in self:
            if record.nrc_cliente:
                record.nit_o_nrc_cliente = record.nrc_cliente
            elif record.nit_cliente:
                record.nit_o_nrc_cliente = record.nit_cliente
            else:
                record.nit_o_nrc_cliente = ''

    @api.depends('partner_id')
    def _compute_get_debito_fiscal(self):
        for record in self:
            record.debito_fiscal_contribuyentes = '0.0'

    @api.depends('partner_id')
    def _compute_get_debito_fiscal_terceros(self):
        for record in self:
            record.debito_fiscal_cuenta_terceros = '0.0'

    @api.depends('partner_id')
    def _compute_get_dui_cliente(self):
        for record in self:
            if record.partner_id and record.numero_anexo == '1' and record.nit_o_nrc_cliente == '':
                record.tipo_documento_identificacion = " "
            else:
                record.tipo_documento_identificacion = record.partner_id.dui

    @api.depends('partner_id')
    def _compute_get_codigo_tipo_documento_cliente(self):
        for record in self:
            if record.partner_id and record.partner_id.dui:
                record.codigo_tipo_documento_cliente = "2"
            elif record.partner_id and record.partner_id.vat:
                record.codigo_tipo_documento_cliente = "1"
            else:
                record.codigo_tipo_documento_cliente = "3"

    @api.depends("codigo_tipo_documento_cliente", "partner_id.vat", "partner_id.dui")
    def _compute_documento_sujeto_excluido(self):
        for record in self:
            if record.codigo_tipo_documento_cliente == "2":  # DUI
                record.documento_sujeto_excluido = record.partner_id.dui or ""
            elif record.codigo_tipo_documento_cliente == "1":  # NIT
                record.documento_sujeto_excluido = record.partner_id.vat or ""
            else:
                record.documento_sujeto_excluido = ""
# -*- coding: utf-8 -*-
from odoo import fields, models, api
import logging
import re
import io
import base64

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

    tipo_ingreso_id = fields.Many2one(
        comodel_name="account.tipo.ingreso",
        string="Tipo de Ingreso"
    )

    tipo_costo_gasto_id = fields.Many2one(
        comodel_name="account.tipo.costo.gasto",
        string="Tipo de Costo/Gasto"
    )

    tipo_operacion = fields.Many2one(
        comodel_name="account.tipo.operacion",
        string="Tipo Operacion"
    )

    clasificacion_facturacion = fields.Many2one(
        comodel_name="account.clasificacion.facturacion",
        string="Clasificacion"
    )

    sector = fields.Many2one(
        comodel_name="account.sector",
        string="Sector"
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
        related='journal_id.sit_tipo_documento.codigo',
        store=False
    )

    codigo_tipo_documento_display = fields.Char(
        string="Tipo de documento",
        compute='_compute_codigo_tipo_documento_display',
        store=False
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

    tipo_operacion_renta = fields.Monetary(
        string="Tipo de operacion (renta)",
        compute='_compute_get_tipo_operacion_renta',
        readonly=True,
        store=False,
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

    # retencion_iva_amount = fields.Char(
    #     string="Retencion IVA 13%",
    #     readonly=True,
    # )

    # retencion_iva_amount_1 = fields.Char(
    #     string="Percepción IVA 1%",
    #     compute="_compute_retencion_iva_amount",
    #     readonly=True,
    #     store=False
    # )


    # === Campos display (codigo + nombre) ===
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

    # === Métodos compute ===
    @api.depends('tipo_ingreso_id')
    def _compute_tipo_ingreso_display(self):
        for rec in self:
            rec.tipo_ingreso_display = (
                f"{rec.tipo_ingreso_id.codigo}. {rec.tipo_ingreso_id.valor}"
                if rec.tipo_ingreso_id else ""
            )

    @api.depends('tipo_costo_gasto_id')
    def _compute_tipo_costo_gasto_display(self):
        for rec in self:
            rec.tipo_costo_gasto_display = (
                f"{rec.tipo_costo_gasto_id.codigo}. {rec.tipo_costo_gasto_id.valor}"
                if rec.tipo_costo_gasto_id else ""
            )

    @api.depends('tipo_operacion')
    def _compute_tipo_operacion_display(self):
        for rec in self:
            rec.tipo_operacion_display = (
                f"{rec.tipo_operacion.codigo}. {rec.tipo_operacion.valor}"
                if rec.tipo_operacion else ""
            )

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

    @api.depends('journal_id')
    def _compute_get_clase_documento_display(self):
        for record in self:
            if record.clase_documento == '4':
                record.clase_documento_display = '4. Documento tributario electronico DTE'
            else:
                record.clase_documento_display = '1. Impreso por imprenta o tiquetes'

    @api.depends('journal_id')
    def _compute_codigo_tipo_documento_display(self):
        for record in self:
            record.codigo_tipo_documento_display  =  record.codigo_tipo_documento + ' ' + record.journal_id.name

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
                record.numero_control_interno_del = 0
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

    @api.depends('partner_id')
    def _compute_get_nrc_o_nit(self):
        for record in self:
            if record.partner_id.vat:
                record.nit_o_nrc_cliente = record.partner_id.vat
            elif record.partner_id.nrc:
                record.nit_o_nrc_cliente = record.partner_id.nrc
            else:
                record.nit_o_nrc_cliente = ''

    @api.depends('partner_id')
    def _compute_get_debito_fiscal(self):
        for record in self:
            record.debito_fiscal_contribuyentes = 0.00

    @api.depends('partner_id')
    def _compute_get_debito_fiscal_terceros(self):
        for record in self:
            record.debito_fiscal_cuenta_terceros = 0.00

    @api.depends('partner_id')
    def _compute_get_dui_cliente(self):
        for record in self:
            if record.partner_id  and record.nit_o_nrc_cliente == '':
                _logger.info("dentro %s, %s", record.partner_id.dui, record.partner_id.name)
                record.dui_cliente = record.partner_id.dui
            else:
                _logger.info("fuera %s, %s", record.partner_id.dui, record.partner_id.name)
                record.dui_cliente = ""

    @api.depends('partner_id')
    def _compute_get_nit_company(self):
        for record in self:
            if record.partner_id.vat:
                record.nit_company = record.partner_id.vat
            else:
                record.nit_company = ''

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

    # @api.depends('invoice_line_ids.price_subtotal', 'codigo_tipo_documento')
    # def _compute_retencion_iva_amount(self):
    #     for record in self:
    #         if record.codigo_tipo_documento == '14':  # sujeto excluido
    #             record.retencion_iva_amount_1 = str(round(float(record.amount_untaxed) * 0.01, 2))
    #         else:
    #             record.retencion_iva_amount_1 = '0.0'



    def _get_anexo_contribuyentes_data(self): #Cambio a consumidor final
        """
        Función para generar los datos del anexo de contribuyentes en formato CSV.
        """

        # Mapea los nombres de los campos de Odoo al orden de la vista
        csv_fields = [
            'invoice_date',
            'clase_documento',
            'codigo_tipo_documento',
            'name',
            'hacienda_selloRecibido',
            'numero_control_interno_al',
            'numero_control_interno_al',
            'hacienda_codigoGeneracion_identificacion',
            'numero_control_interno_al',
            'numero_control_interno_al',
            'nit_o_nrc_cliente',
            'total_exento',
            'ventas_exentas_no_sujetas',
            'total_no_sujeto',
            'total_gravado',
            'debito_fiscal_contribuyentes',
            'ventas_cuenta_terceros',
            'debito_fiscal_cuenta_terceros',
            'total_operacion',
            'dui_cliente',
            'ventas_tasa_cero',
            'tipo_ingreso_renta',
            'tipo_operacion_renta',
            'numero_anexo',
        ]

        csv_content = io.StringIO()
        # csv_content.write(';'.join(csv_headers) + '\n')

        # Buscar explícitamente todos los registros que cumplen el dominio de la vista
        # Esto asegura que el CSV se genere con datos incluso si la vista está vacía.
        records_to_export = self.env['account.move'].search([
            ('codigo_tipo_documento', 'in', ["01", "11", "03"]),
            # ('hacienda_estado', '=', 'PROCESADO'),
            # ('hacienda_selloRecibido', '!=', '')
        ])

        for record in records_to_export:
            row_data = []
            for field_name in csv_fields:
                value = record[field_name]
                if value is None:
                    value = ""
                # Convertir a cadena y eliminar comillas y puntos
                clean_value = str(value).replace('"', '').replace("'", '').replace('.', '')

                # Formatear fecha en DD/MM/AAAA
                if field_name == "invoice_date" and record.invoice_date:
                    clean_value = record.invoice_date.strftime("%d/%m/%Y")

                if field_name in ["hacienda_selloRecibido", "hacienda_codigoGeneracion_identificacion", "name"] : #limpiar el sello de recibido sin guiones
                    clean_value = clean_value.replace("-", "")
                row_data.append(clean_value)

            csv_content.write(';'.join(row_data) + '\n')

        return csv_content.getvalue().encode('utf-8')


    def action_download_csv_anexo(self):
        """
        Función para descargar el anexo de contribuyentes como un archivo CSV.
        """
        csv_data = self._get_anexo_contribuyentes_data()

        # Crea un adjunto temporal para servir el archivo.
        attachment = self.env['ir.attachment'].create({
            'name': 'anexo_consumidor_final.csv',
            'type': 'binary',
            'datas': base64.b64encode(csv_data),
            'res_model': 'account.move',
            'res_id': False,
            'public': True,  # Esto permite que el archivo se sirva a través de la URL.
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
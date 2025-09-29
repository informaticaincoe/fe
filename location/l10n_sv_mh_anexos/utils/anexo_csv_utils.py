# -*- coding: utf-8 -*-
import io
import base64
import logging
from datetime import date
from odoo import fields, models, api

_logger = logging.getLogger(__name__)


class AnexoCSVUtils(models.AbstractModel):
    _name = "anexo.csv.utils"
    _description = "Utilidades para exportar anexos a CSV"

    def _get_anexo_fields(self, numero_anexo):
        """
        Retorna los nombres de los campos a exportar según el número de anexo.
        """
        _logger.info("fields %s", numero_anexo)
        if numero_anexo == '5':  # Sujeto Excluido
            return [
                'codigo_tipo_documento_cliente_display',
                'documento_sujeto_excluido',
                'razon_social',
                'invoice_date',
                'hacienda_selloRecibido',
                'name',
                'total_operacion',
                'retencion_iva_amount',
                'tipo_operacion_codigo',
                'clasificacion_facturacion_codigo',
                'sector_codigo',
                'tipo_costo_gasto_codigo',
                'numero_anexo',
            ]
        elif numero_anexo == '2':  # Consumidor final
            return [
                'invoice_date',
                'clase_documento',
                'codigo_tipo_documento',
                'name',
                'hacienda_selloRecibido',
                'numero_control_interno_del',
                'numero_control_interno_al',
                'numero_documento_del_al',
                'numero_documento_del_al',
                'numero_maquina_registradora',
                'total_exento',
                'ventas_exentas_no_sujetas',
                'total_no_sujeto',
                'total_gravado_local',
                'exportaciones_dentro_centroamerica',
                'exportaciones_fuera_centroamerica',
                'exportaciones_de_servicio',
                'ventas_tasa_cero',
                'ventas_cuenta_terceros',
                'total_operacion',
                'tipo_operacion_codigo',
                'tipo_ingreso_codigo',
                'numero_anexo',
            ]
        elif numero_anexo == '7':
            return [
                'name',
                'clase_documento',
                'desde_tiquete_preimpreso',
                'hasta_tiquete_preimpreso',
                'codigo_tipo_documento',
                'tipo_de_detalle',
                'hacienda_selloRecibido',
                'desde',
                'hasta',
                'hacienda_codigoGeneracion_identificacion',
            ]
        elif numero_anexo == '1':  # Contribuyente
            return [
                'invoice_date',
                'clase_documento',
                'codigo_tipo_documento',
                'name',
                'hacienda_selloRecibido',
                'numero_control_interno_al',
                'hacienda_codigoGeneracion_identificacion',
                'nit_o_nrc_anexo_contribuyentes',
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
        return []

    def generate_csv(self, records, numero_anexo, view_id=None):
        """
        Genera el CSV usando los campos visibles en la vista tree.
        Si no se pasa view_id, usa los campos por defecto definidos en _get_anexo_fields.
        """
        csv_content = io.StringIO()
        csv_fields = []

        # === Determinar campos desde la vista === #
        if view_id:
            try:
                view = self.env["ir.ui.view"].browse(view_id)
                arch = view.read_combined(["arch"])["arch"]
                from lxml import etree
                xml_root = etree.fromstring(arch.encode("utf-8"))
                csv_fields = [field.get("name") for field in xml_root.xpath("//field[@name]")]
            except Exception as e:
                _logger.warning("No se pudo leer la vista %s: %s", view_id, e)

        # === Si no hay campos de vista, fallback por anexo === #
        if not csv_fields:
            csv_fields = self._get_anexo_fields(numero_anexo)

        _logger.info("CSV fields finales usados: %s", csv_fields)

        # === Escribir cabecera === #
        csv_content.write(";".join(csv_fields) + "\n")

        # === Generar el CSV === #
        for record in records:
            row_data = []
            for field_name in csv_fields:
                try:
                    value = getattr(record, field_name, "")
                except Exception:
                    value = ""

                if value is None:
                    clean_value = ""
                elif isinstance(value, (int, float)):
                    clean_value = str(value)
                else:
                    clean_value = str(value)

                # Formato de fecha
                if field_name == "invoice_date" and record.invoice_date:
                    clean_value = record.invoice_date.strftime("%d/%m/%Y")

                # Quitar comillas y saltos de línea
                clean_value = clean_value.replace('"', '').replace("'", '').replace("\n", " ").replace("\r", " ")

                row_data.append(clean_value)

            csv_content.write(";".join(row_data) + "\n")

        return csv_content.getvalue().encode("utf-8-sig")  # BOM UTF-8 para Excel

class ReportFacturasPorDia(models.TransientModel):
    _name = "report.facturas.por.dia"
    _description = "Resumen de facturas por día"

    fecha = fields.Date(string="Fecha")
    cantidad = fields.Integer(string="Cantidad de facturas")
    total = fields.Monetary(string="Monto total")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id.id)

    @api.model
    def load_data(self):
        """Carga datos agrupados desde account.move"""
        self.search([]).unlink()  # limpiar antes de insertar
        data = self.env["account.move"].read_group(
            domain=[("move_type", "=", "out_invoice")],
            fields=["invoice_date", "amount_total:sum", "id:count"],
            groupby=["invoice_date"],
            orderby="invoice_date",
        )
        for row in data:
            self.create({
                "fecha": row["invoice_date"],
                "cantidad": row["invoice_date_count"],
                "total": row["amount_total"],
            })
        return {
            "type": "ir.actions.act_window",
            "res_model": "report.facturas.por.dia",
            "view_mode": "tree",
            "target": "current",
        }

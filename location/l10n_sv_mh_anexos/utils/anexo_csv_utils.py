# -*- coding: utf-8 -*-
import io
import base64
import logging
from datetime import date

from odoo import api, models

_logger = logging.getLogger(__name__)


class AnexoCSVUtils(models.AbstractModel):
    _name = "anexo.csv.utils"
    _description = "Utilidades para exportar anexos a CSV"

    def _get_anexo_fields(self, numero_anexo):
        """
        Retorna los nombres de los campos a exportar según el número de anexo.
        """
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

    def generate_csv(self, records, numero_anexo):
        """
        Genera el contenido del CSV para los registros y el anexo especificado.
        """
        _logger.info("prueba %s", numero_anexo)
        csv_fields = self._get_anexo_fields(numero_anexo)
        csv_content = io.StringIO()

        for record in records:
            row_data = []
            for field_name in csv_fields:
                value = record[field_name] if record[field_name] is not None else ""
                clean_value = str(value).replace('"', '').replace("'", '').replace('.', '')

                # Formato de fecha
                if field_name == "invoice_date" and record.invoice_date:
                    clean_value = record.invoice_date.strftime("%d/%m/%Y")

                # Limpieza de campos sensibles
                if field_name in ["hacienda_selloRecibido", "hacienda_codigoGeneracion_identificacion", "name"]:
                    clean_value = clean_value.replace("-", "")

                row_data.append(clean_value)

            csv_content.write(';'.join(row_data) + '\n')

        return csv_content.getvalue().encode('utf-8')

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

    def _get_fields_by_action_key(self, key: str):
        """
        key puede ser algo como 'ANX_CF' (tu clave) o un XMLID
        'l10n_sv_mh_anexos.action_anexo_consumidor_final'.
        """
        mapping = {
            # --- claves propias ---
            "ANX_CF_AGRUPADO": [
                "invoice_date",
                "clase_documento",
                "codigo_tipo_documento",
                "numero_resolucion_consumidor_final",
                "serie_documento_consumidor_final",
                "numero_control_interno_del",
                "numero_control_interno_al",
                "numero_documento_del",
                "numero_documento_al",
                "numero_maquina_registradora",
                "total_exento",
                "ventas_exentas_no_sujetas",
                "total_no_sujeto",
                "total_gravado_local",
                "exportaciones_dentro_centroamerica",
                "exportaciones_fuera_centroamerica",
                "exportaciones_de_servicio",
                "ventas_tasa_cero",
                "ventas_cuenta_terceros",
                "total_operacion_suma",
                "tipo_operacion_codigo",
                "tipo_ingreso_codigo",
                "numero_anexo",
            ],
            "ANX_CONTRIBUYENTE": [
                'invoice_date',
                'clase_documento',
                'codigo_tipo_documento',
                'hacienda_codigoGeneracion_identificacion',  # Número de Resolución
                'hacienda_selloRecibido',  # Número de Serie de Documento
                'name',  # Número de Documento
                'numero_control_interno_del',  # Número de Documento
                'nit_o_nrc_anexo_contribuyentes',
                'razon_social',
                'total_exento',
                'total_no_sujeto',
                'total_gravado',
                'debito_fiscal_contribuyentes',
                'ventas_cuenta_terceros',
                'debito_fiscal_cuenta_terceros',
                'total_operacion',
                'dui_cliente',
                'tipo_operacion_codigo',
                'tipo_ingreso_codigo',
                'numero_anexo'
            ],
            "ANX_SE": [
                'codigo_tipo_documento_cliente',
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
            ],
            "ANX_C162": [
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
            ],
            "ANX_CLIENTES_MENORES": [
                "invoice_month",
                "invoice_date",
                "cantidad_facturas",
                "monto_total_operacion",
                "monto_total_impuestos",
                "invoice_year",
                "numero_anexo",
                "name",
            ],
            "ANX_CLIENTES_MAYORES": [
                "invoice_month",
                "codigo_tipo_documento",
                "documento_sujeto_excluido",
                "razon_social",
                "invoice_date",
                "codigo_tipo_documento",
                "hacienda_codigoGeneracion_identificacion",
                "Número de documento",
                "tipo_operacion_display",
                "amount_tax",
                "invoice_year",
                "numero_anexo",
            ],
            "ANX_ANULADOS": [
                "name",
                "clase_documento",
                "desde_tiquete_preimpreso",
                "hasta_tiquete_preimpreso",
                "codigo_tipo_documento",
                "tipo_de_detalle",
                "hacienda_selloRecibido",
                "desde",
                "hasta",
                "hacienda_codigoGeneracion_identificacion"
            ]
        }
        return mapping.get(str(key), [])

    def generate_csv(self, records, numero_anexo=None, view_id=None, include_header=False):
        from lxml import etree
        import logging
        _logger = logging.getLogger(__name__)

        ctx = self.env.context
        csv_content = io.StringIO()

        # 1) Resolver lista "deseada" desde el mapping por clave
        key = ctx.get('anexo_action_id')
        desired_fields = self._get_fields_by_action_key(key) or []
        model_fields = set(records._fields.keys())

        # 2) Filtrar a los que SÍ existen en el modelo para evitar SQL errors
        existing_fields = [f for f in desired_fields if f in model_fields]
        missing_fields = [f for f in desired_fields if f not in model_fields]
        if missing_fields:
            _logger.warning("CSV(%s): campos faltantes en el modelo %s → %s",
                            key, records._name, missing_fields)

        # 3) Cabecera (solo con los que existen)
        header = existing_fields
        if include_header:
            csv_content.write(";".join(header) + "\n")

        # 4) Leer en bloque (una sola query)
        rows_data = records.read(existing_fields)

        # 5) Renderizar filas
        for row_vals in rows_data:
            row_out = []
            for fname in existing_fields:
                val = row_vals.get(fname, "")

                # --- Formatos / Limpiezas ---
                if fname == "invoice_date" and val:
                    # viene como 'YYYY-MM-DD' (date), formatear DD/MM/AAAA
                    try:
                        clean = fields.Date.to_date(val).strftime("%d/%m/%Y")
                    except Exception:
                        clean = str(val)
                else:
                    clean = "" if val is None else str(val)

                if fname in (
                        "hacienda_codigoGeneracion_identificacion",
                        "hacienda_selloRecibido",
                        "dui_cliente", "nit_o_nrc_anexo_contribuyentes",
                        "documento_sujeto_excluido"
                ):
                    clean = clean.replace("-", "")

                # se eliminan guines del numero de control a menos que sea para anexo de documentos anulados
                if fname == "name" and  key not in ("ANX_ANULADOS"):
                    clean = clean.replace("-", "")

                # “0” por defecto para estos códigos si están vacíos
                if fname in ("tipo_operacion_codigo", "tipo_ingreso_codigo") and not clean:
                    clean = "0"

                # Formato compacto ddmmaa para ciertos anexos menores/mayores
                if fname == "invoice_date" and key in ("ANX_CLIENTES_MENORES", "ANX_CLIENTES_MAYORES"):
                    try:
                        clean = fields.Date.to_date(val).strftime("%d%m%Y")
                    except Exception:
                        pass

                # Sanitizar comillas/saltos
                clean = clean.replace('"', '').replace("'", '').replace("\n", " ").replace("\r", " ")

                row_out.append(clean)

            csv_content.write(";".join(row_out) + "\n")

        return csv_content.getvalue().encode("utf-8-sig")


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

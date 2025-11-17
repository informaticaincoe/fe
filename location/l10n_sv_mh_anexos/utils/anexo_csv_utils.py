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
                "clase_documento_codigo",
                "codigo_tipo_documento_codigo",
                # "codigo_tipo_documento",
                # "numero_resolucion_consumidor_final",
                # "numero_control_interno_del",
                # "numero_control_interno_al",
                # "numero_documento_del",
                # "numero_documento_al",
                # "numero_maquina_registradora",
                # "total_exento",
                # "ventas_exentas_no_sujetas",
                # "total_no_sujeto",
                # "total_gravado_local",
                # "exportaciones_dentro_centroamerica",
                # "exportaciones_fuera_centroamerica",
                # "exportaciones_de_servicio",
                # "ventas_tasa_cero",
                # "ventas_cuenta_terceros",
                # "total_operacion_suma",
                # "tipo_operacion_codigo",
                # "tipo_ingreso_codigo",
                "numero_anexo",
            ],
            "ANX_CONTRIBUYENTE": [
                'invoice_date',
                'clase_documento',
                'codigo_tipo_documento',
                'numero_resolucion',  # Número de Resolución
                'hacienda_selloRecibido',  # Número de Serie de Documento
                'numero_documento',  # Número de Documento
                'numero_control_interno',
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
                'numero_documento',
                'total_operacion',
                'retencion_iva_amount',
                'tipo_operacion_codigo',
                'clasificacion_facturacion_codigo',
                'sector_codigo',
                'tipo_costo_gasto_codigo',
                'numero_anexo',
            ],
            "ANX_C162": [
                "nit_cliente",
                "fecha_documento",
                "sit_tipo_documento",
                "sello_recepcion",
                "numero_documento",
                "total_monto_sujeto",
                "total_iva_retenido",
                "dui_proveedor",
                "numero_anexo"
            ],
            "ANX_CLIENTES_MENORES": [
                "invoice_month",
                "invoice_date",
                "cantidad_facturas",
                "monto_total_operacion",
                "monto_total_impuestos",
                "invoice_year",
                "numero_anexo",
            ],
            "ANX_CLIENTES_MAYORES": [
                "invoice_month",
                "codigo_tipo_documento",
                "documento_sujeto_excluido",
                "razon_social",
                "invoice_date",
                "codigo_tipo_documento",
                "hacienda_codigoGeneracion_identificacion",
                "amount_untaxed",
                "amount_tax",
                "invoice_year",
                "numero_anexo"
            ],
            "ANX_ANULADOS": [
                "numero_resolucion_anexos_anulados",
                "clase_documento",
                "desde_tiquete_preimpreso",
                "hasta_tiquete_preimpreso",
                "codigo_tipo_documento",
                "tipo_de_detalle",
                "hacienda_selloRecibido",
                "desde",
                "hasta",
                "hacienda_codigoGeneracion_identificacion"
            ],
            "ANX_COMPRAS": [
                "invoice_date",
                "clase_documento",
                "codigo_tipo_documento_compra",
                "numero_documento",
                "nit_o_nrc_anexo_contribuyentes",
                "razon_social",
                "compras_internas_total_excento",
                "internaciones_exentas_no_sujetas",
                "importaciones_exentas_no_sujetas",
                "compras_internas_gravadas",
                "internaciones_gravadas_bienes",
                "importaciones_gravadas_bienes",
                "importaciones_gravadas_servicio",
                "credito_fiscal",
                "total_compra",
                "dui_cliente",
                "tipo_operacion_codigo",
                "clasificacion_facturacion_codigo",
                "sector_codigo",
                "tipo_costo_gasto_codigo",
                "numero_anexo",
            ]
        }
        return mapping.get(str(key), [])


    def generate_csv(self, records, numero_anexo=None, view_id=None, include_header=False):

        from decimal import Decimal, InvalidOperation
        import re
        _logger.info("RECORDS CSV: %s", records)

        # Campos que deben ir con 2 decimales en el CSV
        NUMERIC_2D_FIELDS = {"total_monto_sujeto", "total_iva_retenido"}

        _DEC2 = Decimal("0.01")

        def _to_decimal(val) -> Decimal:
            """Convierte val a Decimal de forma robusta (acepta str con comas, símbolos, etc.)."""
            if val is None or val is False:
                return Decimal("0")
            if isinstance(val, Decimal):
                return val
            if isinstance(val, (int, float)):
                return Decimal(str(val))
            if isinstance(val, str):
                s = val.strip()
                if not s:
                    return Decimal("0")
                # quitar separadores de miles y símbolos no numéricos (deja dígitos, punto y signo)
                s = s.replace(",", "")
                s = re.sub(r"[^0-9.\-]", "", s)
                try:
                    return Decimal(s)
                except InvalidOperation:
                    return Decimal("0")
            # cualquier otro tipo → 0
            return Decimal("0")

        ctx = self.env.context
        csv_content = io.StringIO()

        # 1) Resolver lista "deseada" desde el mapping por clave
        key = ctx.get('anexo_action_id') #TODO: REVISAR PORQUE NO SE ESTA ENVIANDO NADA
        _logger.info("keysss: %s", key)

        desired_fields = self._get_fields_by_action_key(key) or []
        _logger.info("ssssss: %s", key)

        model_fields = set(records._fields.keys())

        _logger.info("RECORDS CSV 2: %s", records)

        _logger.info("model_fields: %s", model_fields)
        _logger.info("desired_fieldsss: %s", desired_fields)


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
        _logger.info("rows_datassss: %s", rows_data)

        # 5) Renderizar filas
        for row_vals in rows_data:
            row_out = []
            _logger.info("row_valssss: %s", row_vals)
            _logger.info("existing_fieldssss: %s", existing_fields)

            for fname in existing_fields:
                _logger.info("fnamess: %s", fname)

                val = row_vals.get(fname, "")

                # --- Formatos / Limpiezas ---
                if fname == "invoice_date" and key in ("ANX_CLIENTES_MAYORES", "ANX_CLIENTES_MENORES") and val:
                    clean = clean.replace("/", "")
                else:
                    try:
                        clean = fields.Date.to_date(val).strftime("%d/%m/%Y")
                    except Exception:
                        clean = str(val)

                if fname in (  # Eliminar guiones de la siguiente lista de variables
                        "hacienda_codigoGeneracion_identificacion",
                        "hacienda_selloRecibido", "dui_proveedor",
                        "dui_cliente", "nit_o_nrc_anexo_contribuyentes",
                        "documento_sujeto_excluido", "numero_documento_del", "numero_documento_al", "numero_documento",
                        "numero_resolucion", "numero_resolucion_anexos_anulados"
                ):
                    clean = clean.replace("-", "")

                if fname in NUMERIC_2D_FIELDS:
                    amount = _to_decimal(clean).quantize(_DEC2)  # Decimal con 2 decimales
                    # si tu CSV debe ser numérico puro, puedes dejarlo como str con 2 decimales:
                    clean = f"{amount:.2f}"
                else:
                    # normaliza no-numéricos
                    clean = "" if clean in (None, False) else str(clean)

                is_empty = val in (None, False, "")

                # “” por defecto para estos códigos si están vacíos
                if fname in ("tipo_operacion_codigo", "tipo_ingreso_codigo", "tipo_costo_gasto_codigo", "sector_codigo", "clasificacion_facturacion_codigo") and is_empty:
                    clean = ""

                if fname in ("invoice_month") and not clean:
                    clean = f"{fname:.2f}"

                # Formato compacto ddmmaa para ciertos anexos menores/mayores
                if fname == "invoice_date" and key in ("ANX_CLIENTES_MENORES", "ANX_CLIENTES_MAYORES"):
                    try:
                        clean = fields.Date.to_date(val).strftime("%d%m%Y")
                    except Exception:
                        pass

                # Sanitizar comillas/saltos
                clean = clean.replace('"', '').replace("'", '').replace("\n", " ").replace("\r", " ")

                row_out.append(clean)

            _logger.info("row_outss: %s", row_out)
            csv_content.write(";".join(row_out) + "\n")
            _logger.info("csv_contentsss: %s", csv_content)

        _logger.info("csv_contentsss fuera: %s", csv_content)

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

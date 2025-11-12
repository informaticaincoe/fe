# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import models
import logging
_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo l10n_sv_dte_import [dte_import_parser]")
except ImportError as e:
    _logger.error(f"Error al importar 'constants': {e}")
    constants = None

class DTEImportParser(models.TransientModel):
    _name = "dte.import.parser"
    _description = "Parser JSON DTE (SV)"

    def parse_payload(self, data: dict) -> dict:
        """Normaliza el JSON de Hacienda a un dict homogéneo para el wizard."""
        _logger.info("[DTE Parser] Iniciando parseo de payload JSON de Hacienda...")
        data = data or {}

        # --- Secciones principales ---
        ident = data.get("identificacion", {}) or {}
        emisor = data.get("emisor", {}) or {}
        receptor = data.get("receptor", {}) or {}
        resumen = data.get("resumen", {}) or {}
        items_raw = data.get("cuerpoDocumento", []) or []
        respuesta_mh = data.get("jsonRespuestaMh", {}) or {}
        docs_relacionados = data.get("documentoRelacionado", []) or []

        # --- Datos principales del DTE ---
        tipo_dte = str(ident.get("tipoDte") or "").zfill(2)  # "01" consumidor final, "03" crédito fiscal
        numero_control = ident.get("numeroControl")
        codigo_gen = ident.get("codigoGeneracion")
        sello_recibido = respuesta_mh.get("selloRecibido")
        moneda = ident.get("tipoMoneda")

        _logger.info("Tipo DTE: %s | Número de control: %s | Código generación: %s | Moneda: %s", tipo_dte, numero_control, codigo_gen, moneda)

        # --- Fecha de emisión ---
        fecha_dt = None
        fecha_txt = ident.get("fecEmi")  # "YYYY-MM-DD"
        if fecha_txt:
            try:
                fecha_dt = datetime.strptime(fecha_txt, "%Y-%m-%d")
                _logger.info("Fecha de emisión parseada correctamente: %s", fecha_dt)
            except Exception as e:
                _logger.warning("Error al parsear fecha '%s': %s", fecha_txt, e)
                fecha_dt = None
        else:
            _logger.warning("No se encontró 'fecEmi' en identificación.")

        # --- Fecha de procesamiento ---
        fecha_hacienda_txt = respuesta_mh.get("fhProcesamiento")
        fecha_hacienda_dt = None
        if fecha_hacienda_txt:
            for fmt in ("%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    fecha_hacienda_dt = datetime.strptime(fecha_hacienda_txt, fmt)
                    break
                except Exception:
                    continue

        # --- Ítems del documento ---
        items = []
        for it in items_raw:
            try:
                item_data = {
                    "num_item": it.get("numItem"),
                    "codigo": it.get("codigo"),
                    "descripcion": it.get("descripcion"),
                    "cantidad": float(it.get("cantidad") or 1.0),
                    "precio_unit": float(it.get("precioUni") or it.get("precioUnitario") or 0.0),
                    "venta_gravada": float(it.get("ventaGravada") or 0.0),
                    "venta_exenta": float(it.get("ventaExenta") or 0.0),
                    "venta_no_suj": float(it.get("ventaNoSuj") or 0.0),
                    "iva_item": float(it.get("ivaItem") or 0.0),
                    "uni_medida": it.get("uniMedida"),
                    "tributos": it.get("tributos") or None,
                }
                items.append(item_data)
                _logger.info("Ítem #%s parseado: %s", item_data.get("num_item"), item_data)
            except Exception as e:
                _logger.warning("Error al procesar ítem: %s | Error: %s", it, e)

        # --- Datos del receptor ---
        # receptor_dir = (receptor.get("direccion") or {}).get("complemento")

        # --- Documentos relacionados ---
        docs = []
        for d in docs_relacionados:
            try:
                doc_data = {
                    "tipo_doc_relacionado": d.get("tipoDocumento") or None,
                    "codigo_gen_relacionado": d.get("numeroDocumento") or None,
                    "docr_fecha_emision": d.get("fechaEmision") or None,
                }
                docs.append(doc_data)
            except Exception as e:
                _logger.warning("Error al procesar documentos relacionados: %s | Error: %s", d, e)


        # --- Resumen ---
        total_iva = float(resumen.get("totalIva") or resumen.get("ivaPerci1") or 0.0)
        total_gravada = float(resumen.get("totalGravada") or 0.0)
        total_pagar = float(resumen.get("totalPagar") or 0.0)
        _logger.info("Totales: IVA=%s | Gravada=%s | Total a pagar=%s", total_iva, total_gravada, total_pagar)

        result = {
            "tipo_dte": tipo_dte,
            "numero_control": numero_control,
            "codigo_generacion": codigo_gen,
            "sello_hacienda": sello_recibido,
            "fecha_emision": fecha_dt,
            "moneda": moneda,

            "emisor_nit": emisor.get("nit"),

            "receptor_nombre": receptor.get("nombre") or receptor.get("nombreComercial"),
            "receptor_tipo_documento": receptor.get("tipoDocumento"),
            # "receptor_nit": receptor.get("numDocumento"),
            "receptor_nrc": receptor.get("nrc"),
            "receptor_correo": receptor.get("correo"),
            "receptor_tel": receptor.get("telefono"),
            "receptor_dir": (receptor.get("direccion") or {}).get("complemento"),

            "condicion_operacion": resumen.get("condicionOperacion"),
            "total_iva": float(resumen.get("totalIva") or resumen.get("ivaPerci1") or 0.0),
            "total_gravada": float(resumen.get("totalGravada") or 0.0),
            "total_exenta": float(resumen.get("totalExenta") or 0.0),
            "total_no_sujeta": float(resumen.get("totalNoSuj") or 0.0),
            "total_pagar": float(resumen.get("totalPagar") or 0.0),
            "dias_credito": resumen.get("plazo") or resumen.get("diasCredito"),

            "items": items,
            "pagos": resumen.get("pagos"),

            # Retencion/Percepcion/Renta
            "renta": float(resumen.get("reteRenta") or 0.0),
            "retencion_iva": float(resumen.get("ivaRete1") or 0.0),
            "iva_percibido": float(resumen.get("ivaPerci1") or 0.0),

            # Descuentos
            "descu_no_suj": float(resumen.get("descuNoSuj") or 0.0),
            "descu_exento": float(resumen.get("descuExenta") or 0.0),
            "descu_gravado": float(resumen.get("descuGravada") or 0.0),
            "porc_descu": resumen.get("porcentajeDescuento") or 0.0,

            # Doc Relacionado(CCF)
            "docs_relacionados": docs,

            # Respuesta MH
            "hacienda_estado": respuesta_mh.get("estado") or None,
            "fecha_hacienda": fecha_hacienda_dt.strftime("%Y-%m-%d %H:%M:%S") if fecha_hacienda_dt else None,
            "clasifica_msg": respuesta_mh.get("clasificaMsg") or None,
            "codigo_msg": respuesta_mh.get("codigoMsg") or None,
            "descripcion_msg": respuesta_mh.get("descripcionMsg") or None,
            "observaciones_hacienda": respuesta_mh.get("observaciones") or None,
        }

        # Determinar NIT según el tipo de documento
        if tipo_dte == constants.COD_DTE_FE:
            receptor_nit = receptor.get("numDocumento")
        else:
            receptor_nit = receptor.get("nit")

        result["receptor_nit"] = receptor_nit

        _logger.info("[DTE Parser] Parseo completado exitosamente. Tipo DTE: %s, Ítems: %s", tipo_dte, len(items))
        return result

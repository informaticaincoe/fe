# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import models

class DTEImportParser(models.TransientModel):
    _name = "dte.import.parser"
    _description = "Parser JSON DTE (SV)"

    def parse_payload(self, data: dict) -> dict:
        """Normaliza el JSON de Hacienda a un dict homogéneo para el wizard."""
        data = data or {}
        ident = data.get("identificacion", {}) or {}
        emisor = data.get("emisor", {}) or {}
        receptor = data.get("receptor", {}) or {}
        resumen = data.get("resumen", {}) or {}
        items_raw = data.get("cuerpoDocumento", []) or []

        tipo_dte = str(ident.get("tipoDte") or "").zfill(2)  # "01" consumidor final, "03" crédito fiscal
        numero_control = ident.get("numeroControl")
        codigo_gen = ident.get("codigoGeneracion")
        moneda = ident.get("tipoMoneda")

        fecha_dt = None
        fecha_txt = ident.get("fecEmi")  # "YYYY-MM-DD"
        if fecha_txt:
            try:
                fecha_dt = datetime.strptime(fecha_txt, "%Y-%m-%d")
            except Exception:
                fecha_dt = None

        items = []
        for it in items_raw:
            items.append({
                "num_item": it.get("numItem"),
                "codigo": it.get("codigo"),
                "descripcion": it.get("descripcion"),
                "cantidad": float(it.get("cantidad") or 1.0),
                "precio_unit": float(it.get("precioUni") or it.get("precioUnitario") or 0.0),
                "venta_gravada": float(it.get("ventaGravada") or 0.0),
                "venta_exenta": float(it.get("ventaExenta") or 0.0),
                "venta_no_suj": float(it.get("ventaNoSuj") or 0.0),
                "iva_item": float(it.get("ivaItem") or 0.0),
                "uni_medida": it.get("uniMedida"),  # código MH, p.ej. "59" = unidad
            })

        return {
            "tipo_dte": tipo_dte,
            "numero_control": numero_control,
            "codigo_generacion": codigo_gen,
            "fecha_emision": fecha_dt,
            "moneda": moneda,

            "emisor_nit": emisor.get("nit"),

            "receptor_nombre": receptor.get("nombre") or receptor.get("nombreComercial"),
            "receptor_nit": receptor.get("nit"),
            "receptor_nrc": receptor.get("nrc"),
            "receptor_correo": receptor.get("correo"),
            "receptor_tel": receptor.get("telefono"),
            "receptor_dir": (receptor.get("direccion") or {}).get("complemento"),

            "condicion_operacion": resumen.get("condicionOperacion"),
            "total_iva": float(resumen.get("totalIva") or resumen.get("ivaPerci1") or 0.0),
            "total_gravada": float(resumen.get("totalGravada") or 0.0),
            "total_pagar": float(resumen.get("totalPagar") or 0.0),

            "items": items,
        }

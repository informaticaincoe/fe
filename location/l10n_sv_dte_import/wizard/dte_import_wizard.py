# -*- coding: utf-8 -*-
import base64
import json
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import timedelta

_logger = logging.getLogger(__name__)

# Mapa editable de códigos MH → xmlids de UoM en Odoo.
# Completa con los códigos que uses en tus DTE y los xmlid reales de tus UoM.
MH_UOM_MAP = {
    # "59": "uom.product_uom_unit",   # Unidad
    # "58": "uom.product_uom_kgm",    # Kilogramo
    # "57": "uom.product_uom_litre",  # Litro
}

try:
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo l10n_sv_dte_import [dte_import_wizard]")
except ImportError as e:
    _logger.error(f"Error al importar 'constants': {e}")
    constants = None

class DTEImportWizardLine(models.TransientModel):
    _name = "dte.import.wizard.line"
    _description = "Archivo JSON DTE a importar"

    wizard_id = fields.Many2one("dte.import.wizard", required=True, ondelete="cascade")
    filename = fields.Char(required=True)
    file = fields.Binary(required=True)

class DTEImportWizard(models.TransientModel):
    _name = "dte.import.wizard"
    _description = "Importar DTEs (JSON) a Odoo"

    company_id = fields.Many2one("res.company", required=True, default=lambda s: s.env.company)

    # Impuestos por línea
    tax_iva_13_id = fields.Many2one("account.tax", string="IVA 13%", domain="[('type_tax_use','=','sale')]")
    tax_exento_id = fields.Many2one("account.tax", string="Impuesto Exento", domain="[('type_tax_use','=','sale')]")
    tax_no_suj_id = fields.Many2one("account.tax", string="Impuesto No Sujeto", domain="[('type_tax_use','=','sale')]")

    product_fallback_id = fields.Many2one("product.product", string="Producto genérico", required=True)

    lines = fields.One2many("dte.import.wizard.line", "wizard_id", string="Archivos")

    create_partners = fields.Boolean(string="Crear cliente si no existe", default=True)
    post_moves = fields.Boolean(string="Postear automáticamente", default=True)
    skip_mh_flow = fields.Boolean(
        string="Saltar flujo MH propio",
        default=True,
        help="Evita disparar lógicas propias de envío/validación durante el post."
    )


    def _normalize_maturity(self, move):
        """
        Regla Odoo: TODA línea en cuenta por cobrar/pagar debe tener date_maturity.
        Y ninguna línea de otra cuenta debe tener date_maturity.
        Forzamos eso antes del post.
        """
        # ar_ap_lines = move.line_ids.filtered(lambda l: l.account_id and l.account_id.internal_type in ('receivable', 'payable'))
        ar_ap_lines = move.line_ids.filtered(lambda l: l.partner_id and l.account_id)
        other_lines = move.line_ids - ar_ap_lines
        due = move.invoice_date_due or move.invoice_date

        # 1) Poner date_maturity en TODAS las receivable/payable
        if due:
            ar_ap_lines.write({'date_maturity': due})

        # 2) Quitar date_maturity en las demás líneas
        if other_lines:
            other_lines.write({'date_maturity': False})

    def _strip_payment_terms(self, move_vals):
        """
        Si el partner te está rellenando términos de pago vía onchange,
        Odoo genera N vencimientos. Para importar igual que el JSON,
        quitamos términos de pago y dejamos una sola fecha: invoice_date_due.
        """
        _logger.info("[_strip_payment_terms] Inicio del método para move_vals: %s", move_vals)

        if 'invoice_payment_term_id' in move_vals:
            move_vals.pop('invoice_payment_term_id', None)

        _logger.info("[_strip_payment_terms] move_vals final: %s", move_vals)
        return move_vals


    def _compute_due_date(self, parsed):
        fecha = parsed["fecha_emision"].date() if parsed["fecha_emision"] else False
        if not fecha:
            return False
        cond = str(parsed.get("condicion_operacion") or "").strip()
        if cond in ("1", "contado", "CONTADO"):
            return fecha
        # crédito: usar días si vienen; si no, misma fecha
        dias = 0
        try:
            dias = int(parsed.get("dias_credito") or 0)
        except Exception:
            dias = 0
        return fecha + timedelta(days=dias)

    def action_import(self):
        _logger.info("[DTE Import] Iniciando proceso de importación de archivos JSON (total=%s)", len(self.lines))

        if not self.lines:
            raise UserError(_("Adjunta al menos un archivo JSON."))

        created = self.env["account.move"]

        for idx, l in enumerate(self.lines, start=1):
            _logger.info("[DTE Import] Procesando archivo #%s: %s", idx, l.filename or "sin_nombre")

            try:
                raw = base64.b64decode(l.file or b"{}")
                _logger.info("[DTE Import] Archivo %s decodificado correctamente (%s bytes)", l.filename, len(raw))

                data = json.loads(raw.decode("utf-8"))
                _logger.info("[DTE Import] JSON parseado correctamente para archivo %s", l.filename)

            except Exception as e:
                _logger.exception("[DTE Import] Error al leer o parsear el JSON del archivo %s: %s", l.filename, e)
                raise UserError(_("Archivo %s no es JSON válido: %s") % (l.filename, e))

            try:
                move = self._create_move_from_json(data, filename=l.filename)
                if move:
                    created |= move
                    _logger.info("[DTE Import] Factura creada correctamente desde %s → Move ID=%s | Nombre=%s", l.filename, move.id, move.name)
                else:
                    _logger.warning("[DTE Import] No se creó ningún move para el archivo %s", l.filename)

            except Exception as e:
                _logger.exception("[DTE Import] Error crítico al crear el move desde archivo %s: %s", l.filename, e)
                raise UserError(_("Error al crear la factura desde %s: %s") % (l.filename, e))

        _logger.info("[DTE Import] Proceso finalizado. Total moves creados: %s", len(created))

        return {
            "type": "ir.actions.act_window",
            "name": _("Documentos creados (%s)") % len(created),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", created.ids)],
        }

    # -------------------------
    # Core JSON -> Odoo
    # -------------------------
    def _create_move_from_json(self, data, filename=None):
        """Crea un asiento contable balanceado a partir del JSON del DTE."""
        _logger.info("[DTE Import] Iniciando creación de factura desde JSON: %s", filename)
        parser = self.env["dte.import.parser"]
        parsed = parser.parse_payload(data)
        _logger.info("[DTE Import] Payload parseado correctamente: %s", data)

        tipo = parsed["tipo_dte"]
        _logger.info("[DTE Import] Tipo DTE detectado: %s", tipo)
        if tipo not in (constants.COD_DTE_FE, constants.COD_DTE_CCF):
            raise UserError(_("Tipo DTE no soportado: %s (sólo 01=CF y 03=CCF)") % (tipo,))

        # 01 y 03 => facturas de venta
        move_type = "out_invoice"

        # 1. Diario: buscar por sit_tipo_documento.codigo == tipo
        journal = self._find_sale_journal_by_tipo(tipo)
        if not journal:
            raise UserError(_("No se encontró un diario de ventas con sit_tipo_documento.codigo = %s") % tipo)
        _logger.info("[DTE Import] Diario encontrado: %s", journal.display_name)

        # 2. Buscar o crear partner
        partner = self._find_or_create_partner(parsed)
        _logger.info("[DTE Import] Partner: %s (NIT: %s)", partner.display_name, partner.vat)

        # 3. Descuentos globales
        porcentaje_descu_gravada = self._calc_pct(parsed["descu_gravado"], parsed["total_gravada"])
        porcentaje_descu_exenta = self._calc_pct(parsed["descu_exento"], parsed["total_exenta"])
        porcentaje_descu_no_suj = self._calc_pct(parsed["descu_no_suj"], parsed["total_no_sujeta"])
        _logger.info("Descuentos detectados: Gravado= %s | Exento= %s | No Sujeto= %s",
                     porcentaje_descu_gravada, porcentaje_descu_exenta, porcentaje_descu_no_suj)

        move_vals = {
            "move_type": move_type,
            "journal_id": journal.id,
            "partner_id": partner.id,
            "invoice_date": parsed["fecha_emision"].date() if parsed["fecha_emision"] else False,
            "invoice_date_due": self._compute_due_date(parsed),   # <- NUEVO

            # Tus campos existentes:
            "name": parsed.get("numero_control") or "/",
            "hacienda_codigoGeneracion_identificacion": parsed.get("codigo_generacion") or "",

            # Referencias visibles:
            "payment_reference": parsed.get("numero_control") or filename,
            "ref": parsed.get("codigo_generacion") or "",

            "sit_tipo_documento": journal.sit_tipo_documento.id if journal.sit_tipo_documento else None,
            "invoice_origin": parsed.get("numero_control") or filename,

            "condiciones_pago": parsed["condicion_operacion"],
            "forma_pago": parsed["condicion_operacion"],
            "invoice_line_ids": [],
            "currency_id": self._currency_from_code(parsed.get("moneda")),

            # Retencion/Percepcion/Renta
            "apply_retencion_renta": True if parsed["renta"] > 0 else False,
            "apply_retencion_iva": True if parsed["retencion_iva"] > 0 else False,
            "apply_iva_percibido": True if parsed["iva_percibido"] > 0 else False,

            # Descuentos
            "descuento_no_sujeto_pct": porcentaje_descu_no_suj,
            "descuento_exento_pct": porcentaje_descu_exenta,
            "descuento_gravado_pct": porcentaje_descu_gravada,
            "descuento_global_monto": parsed["porc_descu"],
        }

        # 4. Construcción de líneas de producto
        line_vals = []
        total_venta = 0.0
        total_impuesto = 0.0
        _logger.info("[DTE Import] Construyendo líneas de producto...")

        for it in parsed.get("items", []):
            product = self._find_product_by_code(it.get("codigo")) or self.product_fallback_id
            name = it.get("descripcion") or product.display_name
            qty = it.get("cantidad") or 1.0
            price = it.get("precio_unit") or 0.0
            raw_price = price
            uom_id = self._uom_from_mh_code(it.get("uni_medida"))

            impuesto_sv = 0.0
            taxes = self.env['account.tax'].browse()  # default vacío
            if tipo == constants.COD_DTE_FE: # Consumidor final
                taxes = self._taxes_for_line(
                    iva_item=it.get("iva_item") or 0.0,
                    exenta=it.get("venta_exenta") or 0.0,
                    no_suj=it.get("venta_no_suj") or 0.0,
                )
                impuesto_sv = taxes.amount or 0.0
                _logger.info("[DTE Import] Línea tipo 01, impuestos detectados: %s (%.2f%%)", taxes.mapped('name'), impuesto_sv)

                # Ajustar el precio unitario dinámicamente (quitar IVA si corresponde)
                if raw_price > 0 and impuesto_sv > 0:
                    try:
                        factor = 1.0 + (impuesto_sv / 100.0)
                        base_price = raw_price / factor
                        price = base_price
                        _logger.info("[Ítem %s] Precio unitario incluye IVA %.2f%% → sin IVA: %.4f (÷%.4f)", it.get("numItem"), impuesto_sv, base_price, factor)
                    except Exception as e:
                        _logger.warning("[Ítem %s] Error al calcular base sin IVA (precio=%s, IVA=%.2f%%): %s", it.get("numItem"), raw_price, impuesto_sv, e)
                else:
                    _logger.info("[Ítem %s] Precio unitario %.2f sin modificación (IVA=%.2f%%).", it.get("numItem"), raw_price, impuesto_sv)
            elif tipo == constants.COD_DTE_CCF:  # Crédito fiscal
                tipo_venta = getattr(product, 'tipo_venta', 'gravado')  # gravado, exento, no sujeto
                if tipo_venta == 'gravado':
                    taxes = self.tax_iva_13_id
                elif tipo_venta == 'exento':
                    taxes = self.tax_exento_id
                elif tipo_venta == 'no_sujeto':
                    taxes = self.tax_no_suj_id
                impuesto_sv = taxes.amount

                _logger.info("[DTE Import] Línea tipo 03, producto %s, tipo_venta=%s, impuesto=%s",
                             product.default_code, tipo_venta, taxes.display_name if taxes else None)

            if impuesto_sv and not taxes:
                raise UserError(_(
                    "No se encontró un impuesto del %s%% en la compañía '%s'. "
                    "Por favor, configure el impuesto correspondiente."
                ) % (impuesto_sv, self.company_id.display_name))

            account_id = (
                    product.property_account_income_id.id
                    or product.categ_id.property_account_income_categ_id.id
                    or journal.company_id.account_default_income_id.id
            )

            if not account_id:
                raise UserError(_("El producto '%s' no tiene cuenta de ingresos configurada.") % product.display_name)

            tax_ids = [(6, 0, [taxes.id])] if taxes else False
            subtotal = qty * price
            total_venta += subtotal
            total_impuesto += subtotal * (taxes.amount / 100.0) if taxes else 0.0

            line_vals.append((0, 0, {
                "name": name,
                "product_id": product.id,
                "product_uom_id": uom_id,
                "quantity": qty,
                "price_unit": price,
                "account_id": account_id,
                "tax_ids": tax_ids,
            }))

            _logger.info("Línea: %s | Cant=%.2f | Precio=%.2f | Impuesto=%s%% | Subtotal=%.2f",
                         product.display_name, qty, price, impuesto_sv, subtotal)

        if not line_vals:
            raise UserError(_("El DTE no contiene líneas de producto válidas."))

        # 5. Línea de CxC (balanceo)
        company = journal.company_id
        receivable_account = partner.property_account_receivable_id.id or company.account_default_receivable_id.id
        total_to_receive = total_venta + total_impuesto

        line_vals.append((0, 0, {
            "name": partner.property_account_receivable_id.name or partner.name,
            "account_id": receivable_account,
            "debit": total_to_receive,
            "credit": 0.0,
        }))
        _logger.info("🏦 Línea CxC agregada | Cuenta: %s | Total venta=%.2f | IVA=%.2f | Total=%.2f",
                     receivable_account, total_venta, total_impuesto, total_to_receive)

        move_vals["line_ids"] = line_vals
        _logger.info("[DTE Import] Asiento armado con %s líneas (productos + CxC).", len(line_vals))

        # 6. Crear movimiento contable
        move = self.env["account.move"].with_context(
            default_move_type=move_type,
            skip_dte_import_create=True,
        ).create(move_vals)
        _logger.info("[DTE Import] Asiento creado correctamente: %s", move.name)

        # 7. Normalizar vencimientos
        self._normalize_maturity(move)
        _logger.debug("[DTE Import] Fechas de vencimiento normalizadas para el move ID=%s", move.id)

        # 8. Ajustar contexto si se omite envío a Hacienda
        ctx = dict(self.env.context)
        if self.skip_mh_flow:
            ctx.update({
                "sit_import_dte_json": True,
                "sit_skip_mh_send": True,
                "skip_sequence_on_post": True,
                "skip_import_json": True,
            })
            _logger.info("[DTE Import] Contexto ajustado para importar DTE: %s", ctx)

        # 9. Postear factura
        _logger.info("[DTE Import] Posteando factura ID=%s...", move.id)
        move.with_context(ctx).action_post()
        _logger.info("Asiento %s publicado correctamente", move.name)

        # 10. Mensaje en chatter
        move.message_post(
            body=_("Importado desde DTE JSON<br/>Número control: %s<br/>Código generación: %s<br/>Tipo: %s")
                 % (parsed.get("numero_control"), parsed.get("codigo_generacion"), tipo)
        )
        _logger.info("[DTE Import] Mensaje agregado al chatter del move ID=%s", move.id)
        _logger.info("[DTE Import] Proceso finalizado para archivo %s", filename)

        return move

    # ---------- helpers ----------
    def _find_sale_journal_by_tipo(self, tipo_dte):
        """Busca un diario de ventas cuyo sit_tipo_documento.codigo == tipo_dte en la compañía actual."""
        Journal = self.env["account.journal"]
        return Journal.search([
            ("type", "=", "sale"),
            ("sit_tipo_documento.codigo", "=", tipo_dte),
            ("company_id", "=", self.company_id.id),
        ], limit=1)

    def _currency_from_code(self, code):
        if code == "USD":
            return self.env.ref("base.USD").id
        return self.env.company.currency_id.id

    def _uom_from_mh_code(self, mh_code):
        """Devuelve el UoM según el código MH (o Unidad si no hay mapeo/encuentro)."""
        if not mh_code:
            return self.env.ref("uom.product_uom_unit").id
        xmlid = MH_UOM_MAP.get(str(mh_code))
        if xmlid:
            try:
                return self.env.ref(xmlid).id
            except Exception:
                _logger.warning("UoM xmlid '%s' no encontrado; se usará Unidad.", xmlid)
        return self.env.ref("uom.product_uom_unit").id

    def _taxes_for_line(self, iva_item=0.0, exenta=0.0, no_suj=0.0):
        """Prioridad: IVA > Exento > No Sujeto. Devuelve recordset de account.tax."""
        Tax = self.env["account.tax"]
        if iva_item and self.tax_iva_13_id:
            return self.tax_iva_13_id
        if exenta and self.tax_exento_id:
            return self.tax_exento_id
        if no_suj and self.tax_no_suj_id:
            return self.tax_no_suj_id
        return Tax.browse()

    def _find_product_by_code(self, code):
        if not code:
            return False
        return self.env["product.product"].search([("default_code", "=", code)], limit=1)

    def _find_or_create_partner(self, parsed):
        Partner = self.env["res.partner"]
        receptor_nit = parsed.get("receptor_nit")
        receptor_correo = parsed.get("receptor_correo")
        receptor_tel = parsed.get("receptor_tel")
        receptor_tipo_doc = parsed.get("receptor_tipo_documento")
        tipo_dte = parsed["tipo_dte"]

        _logger.info("Datos del receptor: Tipo Documento=%s | NIT=%s | Correo=%s | Tel=%s | Tipo=%s",
                     receptor_tipo_doc, receptor_nit, receptor_correo, receptor_tel, tipo_dte)

        partner = Partner.browse()

        # 1 Normalizar NIT (quitar guiones para comparar)
        nit_normalizado = receptor_nit.replace("-", "").strip() if receptor_nit else None
        _logger.info("NIT normalizado: '%s' (original: '%s')", nit_normalizado, receptor_nit)

        # 2 Buscar por NIT
        if nit_normalizado:
            if (receptor_tipo_doc and receptor_tipo_doc == constants.COD_TIPO_DOCU_NIT) or (tipo_dte and tipo_dte == constants.COD_DTE_CCF):
                # Buscar partners cuyo NIT sea igual en cualquiera de los dos formatos
                domain = ["|",
                          ("vat", "=", receptor_nit),
                          ("vat", "=", nit_normalizado)]
                partner = Partner.search(domain, limit=1)
                _logger.info("[Partner Search] Encontrado por NIT: %s (%s)", partner.display_name, partner.vat)
            else:
                # Buscar partners cuyo NIT sea igual en cualquiera de los dos formatos
                domain = ["|",
                          ("dui", "=", receptor_nit),
                          ("dui", "=", nit_normalizado)]
                partner = Partner.search(domain, limit=1)
                _logger.info("[Partner Search] Encontrado por DUI: %s (%s)", partner.display_name, partner.dui)

        # 3 Buscar por correo o teléfono si no se encontró por NIT
        if not partner:
            domain = ["|", "|",
                      ("email", "=", receptor_correo),
                      ("phone", "=", receptor_tel),
                      ("mobile","=", receptor_tel)]
            partner = Partner.search(domain, limit=1)
            if partner:
                _logger.info("[Partner Search] Encontrado por correo/teléfono: %s (email=%s, tel=%s)", partner.display_name, receptor_correo, receptor_tel)
            else:
                _logger.info("[Partner Search] No se encontró partner con correo/teléfono.")

        # 4 Si existe o no se permite crear nuevos
        if partner or not self.create_partners:
            if partner:
                _logger.info("[Partner Result] Usando partner existente: %s (ID=%s)", partner.display_name, partner.id)
            else:
                _logger.warning("[Partner Result] No se encontró partner y create_partners=False. No se creará.")
            return partner or Partner.browse()

        # 5 Crear nuevo partner
        vals = {
            "name": parsed.get("receptor_nombre") or _("Cliente sin nombre"),
            "vat": parsed.get("receptor_nit") or False,
            "email": parsed.get("receptor_correo") or False,
            "phone": parsed.get("receptor_tel") or False,
            "street": parsed.get("receptor_dir") or False,
            "company_type": "company" if parsed.get("receptor_nrc") else "person",
            "customer_rank": 1,
        }

        _logger.info("[Partner Create] Creando nuevo partner con datos: %s", vals)
        partner = Partner.create(vals)
        _logger.info("[Partner Create] Partner creado exitosamente: %s (ID=%s, NIT=%s)", partner.display_name, partner.id, partner.vat)

        return partner

    def _calc_pct(self, monto, base):
        """Calcula el porcentaje real basado en monto y base, con logs detallados."""
        _logger.info("[DTE Import] Iniciando cálculo de porcentaje → monto=%.4f | base=%.4f", monto or 0.0, base or 0.0)

        if base and monto:
            try:
                porcentaje = round((monto / base), 2)
                resultado = round(porcentaje * 100, 2)
                _logger.info("[DTE Import] Porcentaje calculado correctamente: (%.4f / %.4f) = %.2f%%", monto, base, resultado)
                return resultado
            except Exception as e:
                _logger.warning("[DTE Import] Error al calcular porcentaje (monto=%s, base=%s): %s", monto, base, e)
                return 0.0

        _logger.debug("[DTE Import] Base o monto vacíos, devolviendo 0.0%% (monto=%s, base=%s)", monto, base)
        return 0.0

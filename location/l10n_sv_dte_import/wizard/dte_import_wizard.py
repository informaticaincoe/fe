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
        ar_ap_lines = move.line_ids.filtered(lambda l: l.account_id and l.account_id.internal_type in ('receivable', 'payable'))
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
        move_vals.pop('invoice_payment_term_id', None)
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
        if not self.lines:
            raise UserError(_("Adjunta al menos un archivo JSON."))

        created = self.env["account.move"]
        for l in self.lines:
            try:
                raw = base64.b64decode(l.file or b"{}")
                data = json.loads(raw.decode("utf-8"))
            except Exception as e:
                raise UserError(_("Archivo %s no es JSON válido: %s") % (l.filename, e))

            move = self._create_move_from_json(data, filename=l.filename)
            created |= move

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
    def _create_move_from_json(self, data, filename=""):
        parser = self.env["dte.import.parser"]
        parsed = parser.parse_payload(data)

        tipo = parsed["tipo_dte"]
        if tipo not in ("01", "03"):
            raise UserError(_("Tipo DTE no soportado: %s (sólo 01=CF y 03=CCF)") % (tipo,))

        # 01 y 03 => facturas de venta
        move_type = "out_invoice"

        # Diario: buscar por sit_tipo_documento.codigo == tipo
        journal = self._find_sale_journal_by_tipo(tipo)
        if not journal:
            raise UserError(_("No se encontró un diario de ventas con sit_tipo_documento.codigo = %s") % tipo)

        # Partner
        partner = self._find_or_create_partner(parsed)

        # Líneas (UoM + impuestos por línea)
        aml_vals = []
        for it in parsed["items"]:
            product = self._find_product_by_code(it.get("codigo")) or self.product_fallback_id
            name = it.get("descripcion") or product.display_name
            qty = it.get("cantidad") or 1.0
            price = it.get("precio_unit") or 0.0

            uom_id = self._uom_from_mh_code(it.get("uni_medida"))
            taxes = self._taxes_for_line(
                iva_item=it.get("iva_item") or 0.0,
                exenta=it.get("venta_exenta") or 0.0,
                no_suj=it.get("venta_no_suj") or 0.0,
            )

            line_vals = {
                "name": name,
                "product_id": product.id,
                "product_uom_id": uom_id,
                "quantity": qty,
                "price_unit": price,
            }
            if taxes:
                line_vals["tax_ids"] = [(6, 0, taxes.ids)]
            aml_vals.append((0, 0, line_vals))

        # Contexto para esquivar flujos propios (si aplica en tu _post)
        ctx = dict(self.env.context)
        if self.skip_mh_flow:
            ctx.update({
                "sit_import_dte_json": True,
                "sit_skip_mh_send": True,
                "skip_sequence_on_post": True,
            })

        move_vals = {
            "move_type": move_type,
            "journal_id": journal.id,
            "partner_id": partner.id,
            "invoice_date": parsed["fecha_emision"].date() if parsed["fecha_emision"] else False,
            "invoice_date_due": self._compute_due_date(parsed),   # <- NUEVO
            
            # Tus campos existentes:
            "name": parsed.get("numero_control") or "/",  # Número de Control
            "hacienda_codigoGeneracion_identificacion": parsed.get("codigo_generacion") or "",

            # Referencias visibles:
            "payment_reference": parsed.get("numero_control") or filename,
            "ref": parsed.get("codigo_generacion") or "",

            "invoice_line_ids": aml_vals,
            "currency_id": self._currency_from_code(parsed.get("moneda")),
        }

        move = self.env["account.move"].with_context(ctx).create(move_vals)

        self._normalize_maturity(move)
        
        if self.post_moves:
            move.with_context(ctx).action_post()

        move.message_post(
            body=_("Importado desde DTE JSON<br/>Número control: %s<br/>Código generación: %s<br/>Tipo: %s")
                 % (parsed.get("numero_control"), parsed.get("codigo_generacion"), tipo)
        )
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
        partner = Partner.search([("vat", "=", parsed.get("receptor_nit"))], limit=1) if parsed.get("receptor_nit") else Partner.browse()
        if not partner:
            partner = Partner.search(["|","|",
                                      ("email","=",parsed.get("receptor_correo")),
                                      ("phone","=",parsed.get("receptor_tel")),
                                      ("mobile","=",parsed.get("receptor_tel"))], limit=1)
        if partner or not self.create_partners:
            return partner or Partner.browse()
        vals = {
            "name": parsed.get("receptor_nombre") or _("Cliente sin nombre"),
            "vat": parsed.get("receptor_nit") or False,
            "email": parsed.get("receptor_correo") or False,
            "phone": parsed.get("receptor_tel") or False,
            "street": parsed.get("receptor_dir") or False,
            "company_type": "company" if parsed.get("receptor_nrc") else "person",
            "customer_rank": 1,
        }
        return Partner.create(vals)

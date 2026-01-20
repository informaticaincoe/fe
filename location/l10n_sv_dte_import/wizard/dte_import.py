# -*- coding: utf-8 -*-
import base64
import json
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import timedelta
from odoo.tools import float_round
from odoo.exceptions import ValidationError

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
    from odoo.addons.common_utils.utils import config_utils
    _logger.info("SIT Modulo l10n_sv_dte_import [dte_import_wizard]")
except ImportError as e:
    _logger.error(f"Error al importar 'constants': {e}")
    constants = None
    config_utils = None

class DTEImportLine(models.Model):
    _name = "dte.import.line"
    _description = "Archivo JSON DTE a importar"

    wizard_id = fields.Many2one("dte.import", required=True, ondelete="cascade", default=lambda self: self.env.context.get("wizard_id"))
    filename = fields.Char(required=True)
    file = fields.Binary(required=True)

    products_loaded = fields.Boolean(string="Productos cargados", default=False)

    product_line_ids = fields.One2many(
        "dte.import.product.line",
        "wizard_line_id",
        string="Productos del JSON"
    )

    observations = fields.Text(string="Observaciones")

    move_ids = fields.One2many(
        "account.move",
        "dte_import_line_id",
        string="Asientos contables",
        readonly=True,
    )

    def write(self, vals):
        for rec in self:
            _logger.info("DTE IMPORT: Estado: %s", rec.wizard_id.state)
            if rec.wizard_id.state not in ("draft", None):
                raise ValidationError("No se pueden modificar archivos de una importación confirmada.")
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.wizard_id.state not in ("draft", None):
                raise ValidationError("No se pueden eliminar archivos de una importación confirmada.")
        return super().unlink()

    def action_view_products(self):
        self.ensure_one()

        if not self.products_loaded:
            self.wizard_id._load_products_for_line(self)
            self.products_loaded = True

        return {
            "type": "ir.actions.act_window",
            "name": f"Productos - {self.filename}",
            "res_model": "dte.import.product.line",
            "view_mode": "list,form",
            "domain": [("wizard_line_id", "=", self.id)],
            "context": {
                "default_wizard_line_id": self.id,
                "default_company_id": self.wizard_id.company_id.id,
                "default_move_type": self.wizard_id.move_type,
            },
            "target": "current",
        }

class DTEImport(models.Model):
    _name = "dte.import"
    _description = "Importar DTEs (JSON) a Odoo"

    name = fields.Char(
        string="Referencia",
        required=True,
        readonly=True,
        copy=False,
        default="/",
        index=True
    )

    company_id = fields.Many2one("res.company", string="Empresa", required=True, default=lambda s: s.env.company)

    # Impuestos por línea
    tax_iva_13_id = fields.Many2one("account.tax", string="Impuesto")  # string="IVA 13%"
    tax_exento_id = fields.Many2one("account.tax", string="Impuesto Exento")
    tax_no_suj_id = fields.Many2one("account.tax", string="Impuesto No Sujeto")

    # product_fallback_id = fields.Many2one("product.product", string="Producto genérico", required=True)

    lines = fields.One2many("dte.import.line", "wizard_id", string="Archivos")

    create_partners = fields.Boolean(string="Crear cliente si no existe", default=True)
    post_moves = fields.Boolean(string="Postear automáticamente", default=True)
    skip_mh_flow = fields.Boolean(
        string="Saltar flujo MH propio",
        default=True,
        help="Evita disparar lógicas propias de envío/validación durante el post."
    )

    dte_import_journal_id = fields.Many2one(
        'account.journal',
        string='Diario compras',
        domain="[('type', '=', 'purchase')]",
        help="Seleccione un diario contable diferente al asignado para FSE al registrar la factura de proveedor.",
    )

    product_ids = fields.One2many(
        "dte.import.product.line",
        "wizard_id",
        string="Productos"
    )

    missing_products_info = fields.Text(
        string="Productos no encontrados",
        readonly=True
    )

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('done', 'Importado'),
        ('cancel', 'Cancelado'),
    ], string="Estado", default='draft')

    move_type = fields.Selection(
        string="Tipo",
        selection=[
            ('out_invoice', 'Venta'),
            ('in_invoice', 'Compra'),
        ],
        required=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        _logger.info("DTE IMPORT: Iniciando create() con %s registros", len(vals_list))

        for vals in vals_list:
            _logger.info("DTE IMPORT: Valores iniciales: %s", vals)

            if not vals.get("name") or vals.get("name") == "/":

                move_type = (vals.get("move_type") or self.env.context.get("default_move_type"))
                _logger.info("DTE IMPORT: move_type resuelto (vals/context): %s", move_type)

                if move_type == constants.OUT_INVOICE:
                    seq_code = "dte.import.sale"
                else:
                    seq_code = "dte.import.purchase"

                _logger.info( "DTE IMPORT: Secuencia seleccionada: %s", seq_code)

                seq = self.env["ir.sequence"].next_by_code(seq_code)
                _logger.info("DTE IMPORT: Valor retornado por secuencia: %s", seq)

                vals["name"] = seq or "/"
            else:
                _logger.info("DTE IMPORT: name ya definido (%s), no se genera secuencia", vals.get("name"))

        records = super().create(vals_list)

        _logger.info("DTE IMPORT: create() finalizado. Registros creados: %s", records.ids)
        return records

    def write(self, vals):
        _logger.info("DTE IMPORT WRITE → IDs=%s | vals=%s | ctx=%s", self.ids, vals, self.env.context)

        if self.env.context.get("skip_dte_import_write_validation"):
            _logger.info("DTE IMPORT WRITE → bypass activo por contexto")
            return super().write(vals)

        for rec in self:
            _logger.info("DTE IMPORT WRITE → ID=%s | estado=%s", rec.id, rec.state)

            if rec.state == "done":
                _logger.warning("DTE IMPORT WRITE BLOQUEADO → ID=%s", rec.id)
                raise UserError("No se puede modificar un DTE Importado que ya está confirmado.")

        return super().write(vals)

    def unlink(self):
        for rec in self:
            move_ids = rec.lines.mapped("move_ids").ids
            _logger.info(
                "DTE IMPORT UNLINK → ID=%s | moves relacionados=%s",
                rec.id,
                move_ids,
            )
            if move_ids:
                raise UserError(
                    "La importación no puede eliminarse mientras tenga asientos contables relacionados."
                )
        return super().unlink()

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
        self.ensure_one()

        _logger.info(
            "[DTE Import] Iniciando proceso de importación de archivos JSON (total=%s)",
            len(self.lines),
        )

        if not self.lines:
            raise UserError(_("Adjunta al menos un archivo JSON."))

        created_moves = self.env["account.move"]

        for idx, line in enumerate(self.lines, start=1):
            _logger.info(
                "[DTE Import] Procesando archivo #%s: %s",
                idx,
                line.filename or "sin_nombre",
            )

            try:
                raw = base64.b64decode(line.file or b"{}")
                _logger.info(
                    "[DTE Import] Archivo %s decodificado correctamente (%s bytes)",
                    line.filename,
                    len(raw),
                )

                data = json.loads(raw.decode("utf-8"))
                _logger.info(
                    "[DTE Import] JSON parseado correctamente para archivo %s",
                    line.filename,
                )

            except Exception as e:
                _logger.exception(
                    "[DTE Import] Error al leer o parsear el JSON del archivo %s",
                    line.filename,
                )
                raise UserError(
                    _("Archivo %s no es JSON válido: %s") % (line.filename, e)
                )

            try:
                move = self._create_move_from_json(
                    data,
                    filename=line.filename,
                )

                if move:
                    created_moves |= move
                    _logger.info(
                        "[DTE Import] Factura creada correctamente desde %s → Move ID=%s | Nombre=%s",
                        line.filename,
                        move.id,
                        move.name,
                    )
                else:
                    _logger.warning(
                        "[DTE Import] No se creó ningún move para el archivo %s",
                        line.filename,
                    )

            except Exception as e:
                _logger.exception(
                    "[DTE Import] Error crítico al crear el move desde archivo %s",
                    line.filename,
                )
                raise UserError(
                    _("Error al crear la factura desde %s: %s")
                    % (line.filename, e)
                )

        # ✅ SOLO AL FINAL se marca como done
        if created_moves:
            _logger.info(
                "[DTE Import] Marcando importación como DONE (moves creados=%s)",
                len(created_moves),
            )

            self.with_context(
                skip_dte_import_write_validation=True
            ).write({
                "state": "done"
            })

        _logger.info(
            "[DTE Import] Proceso finalizado correctamente. Total moves creados: %s",
            len(created_moves),
        )

        return True

    def action_cancel(self):
        for rec in self:
            rec.move_ids.button_cancel()
            rec.state = 'cancel'

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
        move_type = None
        _logger.info("[DTE Import] Tipo DTE detectado: %s", tipo)
        if tipo not in (constants.COD_DTE_FE, constants.COD_DTE_CCF, constants.COD_DTE_NC, constants.COD_DTE_ND, constants.COD_DTE_FEX, constants.COD_DTE_FSE):
            raise UserError(_("Tipo DTE no soportado: %s (sólo 01=CF, 03=CCF, 05=NC, 06=ND, 11=FEX, 14=FSE)") % (tipo,))

        # Evaluar el codigo de generacion
        codigo_generacion = parsed.get("codigo_generacion") or None
        _logger.info("[DTE Import] Codigo de generacion detectado: %s | Tipo de movimiento: %s", codigo_generacion, self.move_type)
        # 01 y 03 => facturas de venta
        if tipo:
            if tipo in(constants.COD_DTE_FE, constants.COD_DTE_CCF, constants.COD_DTE_ND, constants.COD_DTE_FEX):
                if self.move_type == constants.OUT_INVOICE:
                    move_type = constants.OUT_INVOICE
                else:
                    move_type = constants.IN_INVOICE
            elif tipo == constants.COD_DTE_NC:
                if self.move_type == constants.OUT_INVOICE:
                    move_type = constants.OUT_REFUND
                else:
                    move_type = constants.IN_REFUND
            elif tipo == constants.COD_DTE_FSE:
                move_type = constants.IN_INVOICE

        # 1. Diario: buscar por sit_tipo_documento.codigo == tipo
        journal = self._find_sale_journal_by_tipo(tipo, self.move_type)
        if not journal:
            raise UserError(_("No se encontró un diario de ventas con sit_tipo_documento.codigo = %s") % tipo)
        _logger.info("[DTE Import] Diario contable detectado: %s Tipo de diario: %s", journal.name, journal.type)

        if journal and not journal.currency_id:
            raise UserError(_("No se encontró una moneda configurada en el diario %s") % journal.name)

        currency = journal.currency_id
        _logger.info("[DTE Import] Diario encontrado: %s | Moneda: %s", journal.display_name, currency)

        # 2. Buscar o crear partner
        partner = self._find_or_create_partner(parsed)
        _logger.info("[DTE Import] Partner: %s (NIT: %s)", partner.display_name, partner.vat)

        # 3. Buscar documento relacionado cuando se registre una nota de credito o debito
        related_moves = []
        for dr in parsed.get("docs_relacionados", []):
            tipo_dte_r = dr.get("tipo_doc_relacionado")
            codigo = dr.get("codigo_gen_relacionado")
            reversed_or_debit = self._find_by_related_document(codigo, tipo_dte_r)
            if reversed_or_debit:
                related_moves.append(reversed_or_debit)

        # 4. Descuentos globales
        if tipo and tipo == constants.COD_DTE_FSE:
            porcentaje_descu_gravada = self._calc_pct(parsed["descu"], parsed["total_gravada"])
        else:
            porcentaje_descu_gravada = self._calc_pct(parsed["descu_gravado"], parsed["total_gravada"])

        porcentaje_descu_exenta = self._calc_pct(parsed["descu_exento"], parsed["total_exenta"])
        porcentaje_descu_no_suj = self._calc_pct(parsed["descu_no_suj"], parsed["total_no_sujeta"])
        _logger.info("Descuentos detectados: Gravado= %s | Exento= %s | No Sujeto= %s",
                     porcentaje_descu_gravada, porcentaje_descu_exenta, porcentaje_descu_no_suj)

        # Datos Factura de Exportacion
        ItemEmisor = item_emisor_id = Recinto = recinto_id = Regimen = regimen_id = Incoterm = incoterm_id = None

        if tipo and tipo == constants.COD_DTE_FEX:
            ItemEmisor = self.env['account.move.tipo_item.field']
            item_emisor_id = ItemEmisor.search([("codigo", "=", str(parsed.get("item_exportacion")))], limit=1)

            Recinto = self.env['account.move.recinto_fiscal.field']
            recinto_id = Recinto.search([("codigo", "=", parsed["recinto_fiscal"])], limit=1)

            Regimen = self.env['account.move.regimen.field']
            regimen_id = Regimen.search([("codigo", "=", parsed["regimen"])], limit=1)

            Incoterm = self.env['account.incoterms']
            incoterm_id = Incoterm.search([("codigo_mh", "=", parsed["cod_incoterms"])], limit=1)

        # Facturas de compra
        numero_control_json = parsed.get("numero_control")
        numero_control = None
        tipo_documento = None
        clase_documento_id = False

        if numero_control_json:
            numero_control = numero_control_json.replace("-", "").replace(" ", "")
        else:
            numero_control = numero_control_json or "/"

        if codigo_generacion:
            codigo_generacion = codigo_generacion.replace("-", "").replace(" ", "")
        else:
            codigo_generacion = codigo_generacion or "/"

        if self.move_type == constants.IN_INVOICE:
            tipo_dte_compra = self.env["account.journal.tipo_documento.field"].search([("codigo", "=", tipo)], limit=1)
            tipo_documento = tipo_dte_compra.id if tipo_dte_compra else None

            if numero_control and numero_control.startswith("DTE"):
                clase_doc = self.env["account.clase.documento"].search(
                    [("codigo", "=", constants.DTE_COD)],
                    limit=1
                )
                if not clase_doc:
                    clase_doc = self.env["account.clase.documento"].search(
                        [("codigo", "=", constants.IMPRESO_COD)],
                        limit=1
                    )
                if not  clase_doc:
                    raise ValidationError("No se encontró configurada la Clase de Documento.")
                clase_documento_id = clase_doc.id

        wizard_line = self.lines.filtered(lambda l: l.filename == filename)
        _logger.info("[DTE Import] Lineas json: %s", wizard_line)

        move_vals = {
            "dte_import_line_id": wizard_line.id if wizard_line else False,
            "move_type": self.move_type,
            "journal_id": journal.id,
            "partner_id": partner.id,
            "invoice_date": parsed["fecha_emision"].date() if parsed["fecha_emision"] else False,
            "invoice_time": parsed["hora_emision"] or None,
            "invoice_date_due": self._compute_due_date(parsed),   # <- NUEVO
            "state": "draft",

            # Tus campos existentes:
            "name": numero_control,
            "hacienda_codigoGeneracion_identificacion": codigo_generacion or "",
            "hacienda_selloRecibido": parsed.get("sello_hacienda") or None,

            # Referencias visibles:
            "payment_reference": numero_control or filename,
            "ref": codigo_generacion or "",

            "sit_tipo_documento": journal.sit_tipo_documento.id if journal.sit_tipo_documento else None,
            "sit_tipo_documento_id": tipo_documento,
            "invoice_origin": numero_control or filename,

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

            # Respuesta MH
            "hacienda_estado": parsed["hacienda_estado"],
            "fecha_facturacion_hacienda": parsed["fecha_hacienda"],
            "hacienda_clasificaMsg": parsed["clasifica_msg"],
            "hacienda_codigoMsg": parsed["codigo_msg"],
            "hacienda_descripcionMsg": parsed["descripcion_msg"],
            "hacienda_observaciones": parsed["observaciones_hacienda"],
        }

        # Notas de Credito y Debito
        skip_retention_discounts = False
        if tipo == constants.COD_DTE_NC:
            skip_retention_discounts = True
            move_vals["reversed_entry_id"] = related_moves[0].id if related_moves else None
            move_vals["inv_refund_id"] = related_moves[0].id if related_moves else None
            _logger.info("[DTE Import] Nota de crédito vinculada con factura %s (Código generación: %s)", related_moves[0].name, related_moves[0].hacienda_codigoGeneracion_identificacion)
        elif tipo == constants.COD_DTE_ND:
            skip_retention_discounts= True
            move_vals["debit_origin_id"] = related_moves[0].id if related_moves else None
            _logger.info("[DTE Import] Nota de debito vinculada con factura %s (Código generación: %s)", related_moves[0].name, related_moves[0].hacienda_codigoGeneracion_identificacion)

        if skip_retention_discounts:
            move_vals["apply_retencion_renta"] = False
            move_vals["retencion_renta_amount"] = 0.0
            move_vals["descuento_global_monto"] = 0.0
            move_vals["descuento_global"] = 0.0

        # Campos Factura de Exportacion
        if tipo == constants.COD_DTE_FEX:
            move_vals["tipoItemEmisor"] = item_emisor_id.id if item_emisor_id else None
            move_vals["sit_regimen"] = regimen_id.id if regimen_id else None
            move_vals["recinto_sale_order"] = recinto_id.id if recinto_id else None
            move_vals["invoice_incoterm_id"] = incoterm_id.id if incoterm_id else None

        # Guardar campos del modelo de compras
        if self.move_type == constants.IN_INVOICE:
            move_vals["clase_documento_id"] = clase_documento_id
            move_vals["sit_observaciones"] = wizard_line.observations if wizard_line else False

        # 5. Construcción de líneas de producto
        line_vals = []
        total_venta = 0.0
        total_impuesto = 0.0
        _logger.info("[DTE Import] Construyendo líneas de producto...")

        # PRIORIDAD: líneas editadas por el usuario
        if wizard_line and wizard_line.products_loaded and wizard_line.product_line_ids:
            _logger.info("[DTE Import] Usando líneas editadas por el usuario (%s)", filename)

            source_lines = wizard_line.product_line_ids

            for line in source_lines:
                product = line.product_id
                qty = line.quantity
                price = line.price_unit
                taxes = line.tax_ids[:1]

                account_id = (
                        product.property_account_income_id.id
                        or product.categ_id.property_account_income_categ_id.id
                        or journal.company_id.account_default_income_id.id
                )
                if not account_id:
                    raise UserError(
                        _("El producto '%s' no tiene cuenta de ingresos configurada.") % product.display_name)

                subtotal = qty * price
                total_venta += subtotal
                total_impuesto += subtotal * (taxes.amount / 100.0) if taxes else 0.0

                line_vals.append((0, 0, {
                    "name": line.name,
                    "product_id": product.id,
                    "quantity": qty,
                    "price_unit": price,
                    "account_id": account_id,
                    "tax_ids": [(6, 0, taxes.ids)] if taxes else False,
                }))

        if not line_vals:
            raise UserError(_("El DTE no contiene líneas de producto válidas."))

        # 6. Línea de CxC (balanceo)
        # company = journal.company_id
        receivable_account = None

        if move_type and move_type == constants.IN_INVOICE:
            receivable_account = partner.property_account_payable_id.id
        else:
            receivable_account = partner.property_account_receivable_id.id

        total_venta = float_round(total_venta, precision_rounding=currency.rounding)
        total_impuesto = float_round(total_impuesto, precision_rounding=currency.rounding)
        total_to_receive = float_round(total_venta + total_impuesto, precision_rounding=currency.rounding)
        _logger.info("SIT - Valores previos | total_venta=%s | total_impuesto=%s | total_to_receive=%s", total_venta, total_impuesto, total_to_receive)

        line_vals.append((0, 0, {
            "name": partner.property_account_receivable_id.name or partner.name,
            "account_id": receivable_account,
            "debit": total_to_receive if move_type == constants.OUT_INVOICE else 0.0,
            "credit": total_to_receive if move_type != constants.OUT_INVOICE else 0.0,
        }))
        _logger.info("🏦 Línea CxC agregada | Cuenta: %s | Total venta=%.2f | IVA=%.2f | Total=%.2f",
                     receivable_account, total_venta, total_impuesto, total_to_receive)

        move_vals["line_ids"] = line_vals
        _logger.info("[DTE Import] Asiento armado con %s líneas (productos + CxC).", len(line_vals))

        # 7. Crear movimiento contable
        move = self.env["account.move"].with_context(
            default_move_type=move_type,
            skip_dte_import_create=True,
        ).create(move_vals)
        _logger.info("[DTE Import] Asiento creado correctamente: %s", move.name)

        # 8. Normalizar vencimientos
        self._normalize_maturity(move)
        _logger.debug("[DTE Import] Fechas de vencimiento normalizadas para el move ID=%s", move.id)

        # 9. Ajustar contexto si se omite envío a Hacienda
        ctx = dict(self.env.context)
        if self.skip_mh_flow:
            ctx.update({
                "sit_import_dte_json": True,
                "sit_skip_mh_send": True,
                "skip_sequence_on_post": True,
                "skip_import_json": True,
            })
        else:
            ctx.update({
                "sit_import_dte_json": True,
            })
            _logger.info("[DTE Import] Contexto ajustado para importar DTE: %s", ctx)

        # 10. Postear factura
        _logger.info("[DTE Import] Posteando factura ID=%s...", move.id)
        if self.post_moves:
            _logger.info("[DTE Import] Posteando factura ID=%s...", move.id)
            move.with_context(ctx).action_post()
            _logger.info("Asiento %s publicado correctamente", move.name)
        else:
            _logger.info("[DTE Import] NO se publica el movimiento (post_moves=False). Queda en borrador.")

        # 11. Mensaje en chatter
        move.message_post(
            body=_("Importado desde DTE JSON<br/>Número control: %s<br/>Código generación: %s<br/>Tipo: %s")
                 % (parsed.get("numero_control"), parsed.get("codigo_generacion"), tipo)
        )
        _logger.info("[DTE Import] Mensaje agregado al chatter del move ID=%s", move.id)
        _logger.info("[DTE Import] Proceso finalizado para archivo %s", filename)

        return move

    # ---------- helpers ----------
    def _find_sale_journal_by_tipo(self, tipo_dte, tipo_movimiento):
        """Busca un diario de ventas cuyo sit_tipo_documento.codigo == tipo_dte en la compañía actual."""
        Journal = self.env["account.journal"]
        if tipo_dte and tipo_dte == constants.COD_DTE_FSE:
            return Journal.search([
                ("type", "=", constants.TYPE_COMPRA),
                ("sit_tipo_documento.codigo", "=", tipo_dte),
                ("company_id", "=", self.company_id.id),
            ], limit=1)
        else:
            if tipo_movimiento and tipo_movimiento == constants.OUT_INVOICE:
                return Journal.search([
                    ("type", "=", constants.TYPE_VENTA),
                    ("sit_tipo_documento.codigo", "=", tipo_dte),
                    ("company_id", "=", self.company_id.id),
                ], limit=1)
            else:
                return self.dte_import_journal_id

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
        _logger.info("[_taxes_for_line] Entrando con valores -> IVA: %.2f | Exenta: %.2f | No Sujeto: %.2f", iva_item, exenta, no_suj)

        # --- Caso 1: IVA Gravado ---
        if iva_item:
            if not self.tax_iva_13_id:
                raise UserError(_("No se encontró un impuesto configurado para productos gravados (IVA 13%)."))
            _logger.info("[_taxes_for_line] ✅ Seleccionado impuesto IVA: %s (%.2f%%)", self.tax_iva_13_id.display_name, self.tax_iva_13_id.amount)
            return self.tax_iva_13_id

        # --- Caso 2: Exento ---
        if exenta:
            if not self.tax_exento_id:
                raise UserError(_("No se encontró un impuesto configurado para productos exentos."))
            _logger.info("[_taxes_for_line] ✅ Seleccionado impuesto exento: %s", self.tax_exento_id.display_name)
            return self.tax_exento_id

        # --- Caso 3: No Sujeto ---
        if no_suj:
            if not self.tax_no_suj_id:
                raise UserError(_("No se encontró un impuesto configurado para productos no sujetos."))
            _logger.info("[_taxes_for_line] ✅ Seleccionado impuesto no sujeto: %s", self.tax_no_suj_id.display_name)
            return self.tax_no_suj_id

        # --- Caso sin impuestos ---
        _logger.warning("[_taxes_for_line] No se detectó ningún tipo de impuesto aplicable para esta línea.")
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
        receptor_tipo_doc = parsed.get("receptor_tipo_documento") or None
        tipo_dte = parsed["tipo_dte"]
        receptor_pais = parsed.get("cod_pais")
        receptor_dir = parsed.get("receptor_direccion")

        _logger.info(
            "[Partner Init] Datos del receptor: TipoDoc=%s | NIT=%s | Correo=%s | Tel=%s | TipoDTE=%s | País=%s | Dirección=%s",
            receptor_tipo_doc, receptor_nit, receptor_correo, receptor_tel, tipo_dte, receptor_pais, receptor_dir)

        partner = Partner.browse()

        # 1 Normalizar NIT (quitar guiones para comparar)
        nit_normalizado = receptor_nit.replace("-", "").strip() if receptor_nit else None
        _logger.info("[Partner Search] NIT normalizado='%s' (original='%s')", nit_normalizado, receptor_nit)

        # Buscar por NIT
        if ((receptor_tipo_doc and receptor_tipo_doc == constants.COD_TIPO_DOCU_NIT) or
                (tipo_dte and tipo_dte in (constants.COD_DTE_CCF, constants.COD_DTE_NC, constants.COD_DTE_ND))):
            domain = ["|", ("vat", "=", receptor_nit), ("vat", "=", nit_normalizado)]
            partner = Partner.search(domain, limit=1)
            _logger.info("[Partner Search] Resultado búsqueda por NIT: %s (VAT=%s)", partner.display_name or "Ninguno", partner.vat)
        elif receptor_tipo_doc:
            if receptor_tipo_doc == constants.COD_TIPO_DOCU_DUI:
                domain = ["|", ("dui", "=", receptor_nit), ("dui", "=", nit_normalizado)]
                partner = Partner.search(domain, limit=1)
                _logger.info("[Partner Search] Resultado búsqueda por DUI: %s (DUI=%s)", partner.display_name or "Ninguno", partner.dui)
            elif receptor_tipo_doc == constants.COD_TIPO_DOCU_NIT:
                domain = ["|", ("vat", "=", receptor_nit), ("vat", "=", nit_normalizado)]
                partner = Partner.search(domain, limit=1)
                _logger.info("[Partner Search] Resultado búsqueda por NIT (tipo_doc): %s (VAT=%s)", partner.display_name or "Ninguno", partner.vat)

        # 3 Buscar por correo o teléfono si no se encontró por NIT
        if not partner:
            conditions = []

            if receptor_correo:
                conditions.append(("email", "=", receptor_correo))

            if receptor_tel:
                conditions.extend([
                    ("phone", "=", receptor_tel),
                    ("mobile", "=", receptor_tel),
                ])

            if conditions:
                domain = ["|"] * (len(conditions) - 1) + conditions
                partner = Partner.search(domain, limit=1)
            else:
                partner = False

            if partner:
                _logger.info("[Partner Search] Encontrado por correo/teléfono: %s (email=%s, tel=%s)", partner.display_name, receptor_correo, receptor_tel)
            else:
                _logger.info("[Partner Search] No se encontró partner por correo o teléfono.")

        # 4 Si existe o no se permite crear nuevos
        if partner or not self.create_partners:
            if partner:
                _logger.info("[Partner Result] Usando partner existente: %s (ID=%s)", partner.display_name, partner.id)
            else:
                _logger.warning("[Partner Result] No se encontró partner y create_partners=False. No se creará uno nuevo.")
            return partner or Partner.browse()

        # 5 Crear nuevo partner
        TipoIdentificacion = self.env['l10n_latam.identification.type']
        tipo_identificacion_id = TipoIdentificacion.search([("codigo", "=", receptor_tipo_doc)], limit=1)
        _logger.info("[Partner Create] Tipo de identificación encontrado: %s (ID=%s)", tipo_identificacion_id.display_name, tipo_identificacion_id.id)

        ActividadEco = self.env['account.move.actividad_economica.field']
        cod_actividad_eco_id = ActividadEco.search([("codigo", "=", parsed["receptor_cod_actividad"])], limit=1)
        _logger.info("[Partner Create] Actividad económica: %s (ID=%s)", cod_actividad_eco_id.display_name, cod_actividad_eco_id.id)

        Pais = self.env['res.country']
        Municipio = self.env['res.municipality']
        Departamento = self.env['res.country.state']

        pais_id = depto_id = municipio_id = None

        # Determinar país
        if receptor_pais:
            pais_id = Pais.search([("code", "=", receptor_pais)], limit=1)
            _logger.info("[Partner Create] País determinado desde JSON: %s (code=%s)", pais_id.display_name, receptor_pais)
        else:
            if receptor_tipo_doc in (constants.COD_TIPO_DOCU_DUI, constants.COD_TIPO_DOCU_NIT) or tipo_dte in(constants.COD_DTE_CCF, constants.COD_DTE_NC, constants.COD_DTE_ND):
                pais_id = Pais.search([("code", "=", constants.COD_PAIS_SV)], limit=1)
                _logger.info("[Partner Create] País asumido como El Salvador (por DUI/NIT): %s", pais_id.display_name)
            else:
                _logger.info("[Partner Create] País no proporcionado ni inferido.")

        # Determinar departamento y municipio
        dept_code = receptor_dir.get("departamento") if receptor_dir else None
        muni_code = receptor_dir.get("municipio") if receptor_dir else None
        _logger.info("[Partner Create] Códigos ubicación: depto=%s | municipio=%s", dept_code, muni_code)

        if pais_id and tipo_dte != constants.COD_DTE_FEX:
            depto_id = Departamento.search([("country_id", "=", pais_id.id), ("code", "=", dept_code)], limit=1)
            municipio_id = Municipio.search([("dpto_id", "=", depto_id.id), ("code", "=", muni_code)], limit=1)
            _logger.info("[Partner Create] Buscando con país '%s': Depto=%s (ID=%s) | Municipio=%s (ID=%s)",
                         pais_id.display_name, depto_id.display_name, depto_id.id, municipio_id.display_name, municipio_id.id)
        else:
            if tipo_dte != constants.COD_DTE_FEX:
                depto_id = Departamento.search([("code", "=", dept_code)], limit=1)
                municipio_id = Municipio.search([("code", "=", muni_code)], limit=1)
                _logger.info("[Partner Create] Sin país — usando primer depto/muni encontrado: Depto=%s (ID=%s) | Municipio=%s (ID=%s)",
                             depto_id.display_name, depto_id.id, municipio_id.display_name, municipio_id.id)

        # Preparar vals
        vals = {
            "name": parsed.get("receptor_nombre") or _("Cliente sin nombre"),
            "l10n_latam_identification_type_id": tipo_identificacion_id.id or None,
            # "vat": parsed.get("receptor_nit") or False,
            "nrc": parsed.get("receptor_nrc") or False,
            "email": parsed.get("receptor_correo") or False,
            "phone": parsed.get("receptor_tel") or False,
            "street": parsed.get("receptor_dir") or False,
            "company_type": "company" if parsed.get("receptor_nrc") else "person",
            "customer_rank": 1,
            "codActividad": cod_actividad_eco_id.id,
            "country_id": pais_id.id if pais_id else None,
            "state_id": depto_id.id if depto_id else False,
            "munic_id": municipio_id.id if municipio_id else False,
        }

        # Asignar identificación
        if receptor_tipo_doc == constants.COD_TIPO_DOCU_DUI:
            vals["dui"] = parsed.get("receptor_nit") or False
        elif receptor_tipo_doc == constants.COD_TIPO_DOCU_NIT or tipo_dte in(constants.COD_DTE_CCF, constants.COD_DTE_NC, constants.COD_DTE_ND):
            vals["vat"] = parsed.get("receptor_nit") or False
        else:
            vals["dui"] = parsed.get("receptor_nit") or False

        _logger.info("[Partner Create] Valores finales para creación: %s", vals)
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

    def _find_by_related_document(self, codigo, tipo_dte):
        _logger.info("[DTE Import] Buscando movimiento relacionado:")
        _logger.info("Código Generación: %s | Tipo DTE: %s | Compañía: %s", codigo, tipo_dte, self.company_id.name)

        Move = self.env["account.move"]
        domain = [
            ("journal_id.sit_tipo_documento.codigo", "=", tipo_dte),
            ("hacienda_codigoGeneracion_identificacion", "=", codigo),
            ("company_id", "=", self.company_id.id),
        ]
        _logger.info("[DTE Import] Dominio de búsqueda: %s", domain)

        move = Move.search(domain, limit=1)
        if move:
            _logger.info("[DTE Import] Movimiento encontrado: %s (ID: %s, Estado: %s)", move.name, move.id, move.state)
        else:
            _logger.warning("[DTE Import] No se encontró ningún movimiento con el código '%s' y tipo '%s'.", codigo, tipo_dte)
        return move

    def _load_products_for_line(self, wizard_line):
        self.ensure_one()
        missing = []

        raw = base64.b64decode(wizard_line.file)
        payload = json.loads(raw.decode("utf-8"))

        parser = self.env["dte.import.parser"]
        parsed = parser.parse_payload(payload)

        for it in parsed.get("items", []):
            product = self._find_product_by_code(it.get("codigo"))
            if not product:
                missing.append({
                    "archivo": wizard_line.filename or "",
                    "descripcion": it.get("descripcion"),
                    "codigo": it.get("codigo"),
                    "cantidad": it.get("cantidad"),
                })
                continue

            taxes = self._taxes_for_line(
                iva_item=it.get("venta_gravada") or 0.0,
                exenta=it.get("venta_exenta") or 0.0,
                no_suj=it.get("venta_no_suj") or 0.0,
            )

            self.env["dte.import.product.line"].create({
                "wizard_line_id": wizard_line.id,
                "product_id": product.id,
                "name": it.get("descripcion") or product.display_name,
                "quantity": it.get("cantidad") or 1.0,
                "price_unit": it.get("precio_unit") or 0.0,
                "tax_ids": [(6, 0, taxes.ids)],
            })

        # Guardar resumen al FINAL (tal como acordamos)
        if missing:
            self.missing_products_info = "\n".join(
                "- Archivo: %(archivo)s | Producto: %(descripcion)s | Código: %(codigo)s | Cantidad: %(cantidad)s"
                % m for m in missing
            )
        else:
            self.missing_products_info = False

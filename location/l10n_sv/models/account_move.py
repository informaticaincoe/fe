# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
import logging

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import config_utils
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils [l10n_sv account_move]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None
    constants = None

class sit_account_move(models.Model):

    _inherit = 'account.move'
    forma_pago = fields.Many2one('account.move.forma_pago.field', store=True)
    invoice_payment_term_name = fields.Char(related='invoice_payment_term_id.name')
    condiciones_pago = fields.Selection(
        selection='_get_condiciones_pago_selection', string='Condición de la Operación (Pago) - Hacienda')
    sit_plazo = fields.Many2one('account.move.plazo.field', string="Plazos")
    sit_periodo = fields.Integer(string="Periodo")

    sit_tipo_contingencia = fields.Many2one('account.move.tipo_contingencia.field', string="Tipo de Contingencia")
    sit_tipo_contingencia_otro = fields.Text(string="Especifique el Otro Tipo de Contingencia")
    sit_tipo_contingencia_valores = fields.Char(related="sit_tipo_contingencia.valores", string="Tipo de contingiancia(nombre)")
    #sit_modelo_facturacion = fields.Selection(selection='_get_modelo_facturacion_selection', string='Modelo de Facturacion - Hacienda', store=True)
    sit_tipo_transmision = fields.Selection(selection='_get_tipo_transmision_selection', string='Tipo de Transmisión - Hacienda', store=True)
    sit_referencia = fields.Text(string="Referencia", default="")
    sit_observaciones = fields.Text(string="Observaciones", default="")
    sit_qr_hacienda = fields.Binary("QR Hacienda", default=False)
    sit_json_respuesta = fields.Text("Json de Respuesta", default="")
    sit_regimen = fields.Many2one('account.move.regimen.field', string="Régimen de Exportación")
    journal_code = fields.Char(related='journal_id.code', string='Journal Code')

    codigo_tipo_documento = fields.Char(
        related='journal_id.sit_tipo_documento.codigo',
        store=True
    )

    hacienda_estado = fields.Text("Hacienda Estado")
    amount_tax = fields.Float("amount_tax")

    anexo_type = fields.Selection([
        ("consumidor_final", "Consumidor Final"),
        ("credito_fiscal", "Crédito Fiscal"),
        ("exportacion", "Exportación"),
    ], string="Tipo de Anexo - Hacienda")

    invoice_month = fields.Char(
        string="Mes",
        compute='_compute_invoice_month',
        store=False
    )

    @api.depends('invoice_date')
    def _compute_invoice_month(self):
        """
        Calcula el mes de la factura a partir de `invoice_date` y lo almacena en `invoice_month`
        en formato de dos dígitos; deja vacío si no hay fecha de factura.
        """
        for record in self:
            if record.invoice_date:
                # Solo número del mes con dos dígitos
                record.invoice_month = record.invoice_date.strftime('%m')
            else:
                record.invoice_month = ''

    sit_facturacion = fields.Boolean(
        readonly=True,
        store=True,
    )

    razon_social = fields.Char(
        string="Cliente/Proveedor",
        related='partner_id.name',
        readonly=True,
        store=False,  # no se guarda en la base de datos
    )

    tipo_documento_identificacion = fields.Char(
        string="Tipo documento identificacion",
        compute='_compute_get_tipo_documento',
        readonly=True,
        store=False,
    )

    numero_documento = fields.Char(
        string="Número de documento de identificacion",
        compute='_compute_get_tipo_documento',
        readonly=True,
        store=False,  # no se guarda en la base de datos
    )

    def _is_dte_json_import(self):
        """Bandera centralizada para detectar import desde wizard DTE JSON."""
        return bool(self.env.context.get("sit_import_dte_json"))

    @api.depends('partner_id')
    def _compute_get_tipo_documento(self):
        """
        Asigna automáticamente el número de documento del partner a `numero_documento`,
        usando DUI si está disponible o VAT/NIT como alternativa; vacío si no existe.
        """
        for record in self:
            if record.partner_id:
                _logger.info("DUI: %s", record.partner_id.dui)
                record.numero_documento = record.partner_id.dui
            elif record.partner_vat:
                    record.numero_documento = record.partner_id.vat
            else:
                record.numero_documento = ''

    @api.depends('partner_id')
    def _compute_get_tipo_documento(self):
        """
        Calcula automáticamente el tipo y número de documento de identificación del partner
        asignando DUI ("01") o NIT/VAT ("03"), o vacío si no está disponible.
        """
        for record in self:
            if record.partner_id and record.partner_id.dui:
                record.tipo_documento_identificacion = "01"
                record.numero_documento = record.partner_id.dui
            elif record.partner_id and record.partner_id.vat:
                record.tipo_documento_identificacion = "03"
                record.numero_documento = record.partner_id.vat
            else:
                record.tipo_documento_identificacion = ''
                record.numero_documento = ''

    def _get_condiciones_pago_selection(self):
        return [
            ('1', '1-Contado'),
            ('2', '2-A Crédito'),
            ('3', '3-Otro'),
        ]

    def _get_modelo_facturacion_selection(self):
        return [
            ('1', 'Modelo Facturación previo'),
            ('2', 'Modelo Facturación diferido'),
        ]
    def _get_tipo_transmision_selection(self):
        return [
            ('1', 'Transmisión normal'),
            ('2', 'Transmisión por contingencia'),
        ]

    @api.onchange('condiciones_pago')
    def change_sit_plazo(self):
        if self.condiciones_pago == 1:
            self.sit_plazo = None

        # ---- Autorelleno para documentos de VENTA ----

    @api.onchange('partner_id', 'company_id', 'move_type')
    def _onchange_partner_defaults_ventas(self):
        """
        Aplica automáticamente los valores por defecto de pagos y condiciones
        para ventas al cambiar el partner, la empresa o el tipo de movimiento.
        """
        # primero el onchange estándar de Odoo
        super(sit_account_move, self)._onchange_partner_id()

        for move in self:
            if not move.partner_id or not move.is_sale_document(include_receipts=True):
                continue
            p = move.partner_id.with_company(move.company_id)

            # 1) Términos de pago (venta)
            if not move.invoice_payment_term_id and p.terminos_pago_venta_id:
                move.invoice_payment_term_id = p.terminos_pago_venta_id

            # 2) Condición de pago (Hacienda)
            if not move.condiciones_pago and p.condicion_pago_venta_id:
                move.condiciones_pago = p.condicion_pago_venta_id

            # 3) Forma de pago
            if not move.forma_pago and p.formas_pago_venta_id:
                move.forma_pago = p.formas_pago_venta_id

    def _apply_partner_defaults_ventas_if_needed(self):
        """Cubre creaciones sin UI (import/API), donde no corre el onchange."""
        for move in self:
            if not move.partner_id or not move.is_sale_document(include_receipts=True):
                continue
            p = move.partner_id.with_company(move.company_id)
            if not move.invoice_payment_term_id and p.terminos_pago_venta_id:
                move.invoice_payment_term_id = p.terminos_pago_venta_id
            if not move.condiciones_pago and p.condicion_pago_venta_id:
                move.condiciones_pago = p.condicion_pago_venta_id
            if not move.forma_pago and p.formas_pago_venta_id:
                move.forma_pago = p.formas_pago_venta_id

    @api.onchange('partner_id', 'company_id', 'move_type')
    def _onchange_partner_defaults_compras(self):
        """
        Establece automáticamente términos de pago, condición y forma de pago al seleccionar un proveedor,
        considerando facturación electrónica y configuración del partner.
        """
        # primero el onchange estándar de Odoo
        super(sit_account_move, self)._onchange_partner_id()

        for move in self:
            if not move.partner_id or not move.is_purchase_document(include_receipts=True):
                continue
            p = move.partner_id.with_company(move.company_id)

            # 1) Términos de pago (compra)
            if not move.invoice_payment_term_id and p.terminos_pago_compras_id:
                move.invoice_payment_term_id = p.terminos_pago_compras_id

            # 2) Condición de pago (Hacienda)
            if not move.condiciones_pago and p.condicion_pago_compras_id:
                move.condiciones_pago = p.condicion_pago_compras_id

            # 3) Forma de pago
            if move.journal_id.sit_tipo_documento and move.journal_id.sit_tipo_documento.codigo == constants.COD_DTE_FSE:
                if not move.forma_pago and p.formas_pago_compras_id:
                    move.forma_pago = p.formas_pago_compras_id

    def _apply_partner_defaults_compras_if_needed(self):
        """Cubre creaciones sin UI (import/API), donde no corre el onchange."""
        for move in self:
            if not move.partner_id or not move.is_purchase_document(include_receipts=True):
                continue
            p = move.partner_id.with_company(move.company_id)
            if not move.invoice_payment_term_id and p.terminos_pago_compras_id:
                move.invoice_payment_term_id = p.terminos_pago_compras_id
            if not move.condiciones_pago and p.condicion_pago_compras_id:
                move.condiciones_pago = p.condicion_pago_compras_id
            if move.journal_id.sit_tipo_documento and move.journal_id.sit_tipo_documento.codigo == constants.COD_DTE_FSE:
                if not move.forma_pago and p.formas_pago_compras_id:
                    move.forma_pago = p.formas_pago_compras_id

    @api.model_create_multi
    def create(self, vals_list):
        """
        Crea registros de AccountMove con soporte para facturación electrónica, asignando nombres
        secuenciales y aplicando lógicas de descuentos, retenciones, seguro/flete y defaults de partner.
        """
        _logger.info("SIT | Iniciando create unificado para AccountMove. Vals_list: %s", vals_list)

        # --- Nuevo bypass: si viene del importador de DTE ---
        if self._context.get('skip_dte_import_create'):
            _logger.info(
                "🟢 [SIT] Bypass activo (skip_dte_import_create): creando movimientos sin lógica DTE ni secuencia")
            return super().create(vals_list)

        for vals in vals_list:
            move_type = vals.get('move_type')
            if not move_type:
                _logger.warning("SIT | Registro sin move_type detectado, puede ser nómina u otro flujo especial: %s", vals)
            else:
                _logger.info("SIT | Registro con move_type definido: %s", move_type)

        # --- Llenar name provisional '/' antes de crear registros ---
        for vals in vals_list:
            # Buscar el diario si está en los valores
            journal = None
            _logger.info("SIT | Move type: %s", vals.get("move_type"))
            if vals.get('journal_id'):
                journal = self.env['account.journal'].browse(vals.get('journal_id') or 0)
                _logger.info("SIT | Journal: %s", journal)

            if not vals.get('name') or not str(vals['name']).strip():
                vals['name'] = '/'
                if journal and journal.sequence_id.exists():
                    _logger.info("SIT | Diario con secuencia '%s', se deja name provisional '/' para generación automática", journal.sequence_id.name)
                else:
                    _logger.info("SIT | Diario sin secuencia, asignado name provisional '/'")

        # BYPASS para movimientos que no son factura/nota (nómina, asientos manuales, recibos)
        if any(v.get('move_type') in (constants.TYPE_ENTRY, constants.OUT_RECEIPT, constants.IN_RECEIPT) for v in vals_list):
            _logger.info("SIT | Todos los movimientos son entry/receipts. Bypass completo al super().create()")
            return super().create(vals_list)

        # --- Crear registros base (solo una vez) ---
        base_records = super().create(vals_list)
        _logger.info("SIT | Registros base creados: %s", base_records.ids)

        # --- Procesamiento individual de cada registro ---
        for rec in base_records:
            vals = {k: v for k, v in rec._cache.items() if not isinstance(v, (list, tuple))}
            move_type = rec.move_type
            journal = rec.journal_id
            company = rec.company_id

            # Verificamos si el nombre es correcto antes de guardar
            if not rec.name or rec.name == '/':
                _logger.info("SIT | Asignando name secuencial %s para move_id=%s", rec.name, rec.id)

                # Verificar si el diario tiene secuencia configurada
                if company and not company.sit_facturacion and rec.journal_id.sequence_id:
                    # Asignar el nombre secuencial si existe la secuencia
                    rec.name = rec.journal_id.sequence_id.next_by_id()
                    _logger.info("SIT | Secuencia asignada a move_id=%s: %s", rec.id, rec.name)
                else:
                    _logger.warning("SIT | Diario sin secuencia, asignando nombre predeterminado a move_id=%s: %s", rec.id, rec.name)

            # Aplicar el nombre generado en la base de datos
            if rec.name and rec.name != '/':
                _logger.info("SIT | Asignado name: %s para move_id=%s", rec.name, rec.id)
                rec.write({'name': rec.name})
                _logger.info("SIT | move_id=%s: Name confirmado y persistido en base de datos: %s", rec.id, rec.name)

            # --- Evitar interferir con pagos ---
            skip_dte = self._context.get('active_model') == 'account.payment' or rec.origin_payment_id
            if skip_dte:
                _logger.info("SIT-haciendaws_fe | Creación desde pago detectada, omitiendo DTE para move_id=%s", rec.id)
                continue

            # --- Lógica para compras (sin importar facturación activa) ---
            if move_type in (constants.IN_INVOICE, constants.IN_REFUND):
                if journal and (not journal.sit_tipo_documento or journal.sit_tipo_documento.codigo != constants.COD_DTE_FSE):
                    _logger.info("SIT-haciendaws_fe | Documento de compra sin tipo DTE, omitiendo lógica DTE. move_id=%s", rec.id)
                    rec.hacienda_codigoGeneracion_identificacion = None
                    tipo_documento_obj = self.env['account.journal.tipo_documento.field']
                    if move_type == constants.IN_REFUND:
                        doc = tipo_documento_obj.search([('codigo', '=', constants.COD_DTE_NC)], limit=1)
                        rec.sit_tipo_documento_id = doc
                    elif move_type == constants.IN_INVOICE and rec.debit_origin_id:
                        doc = tipo_documento_obj.search([('codigo', '=', constants.COD_DTE_ND)], limit=1)
                        rec.sit_tipo_documento_id = doc
                else:
                    _logger.info("SIT-haciendaws_fe | Documento de compra con tipo DTE FSE, procesando con lógica personalizada. move_id=%s", rec.id)

            # --- Validación de empresa con facturación activa ---
            if not any(vals.get('company_id') and self.env['res.company'].browse(vals['company_id']).sit_facturacion for
                       vals in vals_list):
                _logger.info("SIT-create: Ninguna factura pertenece a empresa con facturación activa, se usa create estándar.")
                return base_records

            # --- Generación dinámica de nombre para venta/compra ---
            if journal and (journal.type == constants.TYPE_VENTA or move_type == constants.IN_INVOICE):
                if not rec.name or rec.name in ('/', False):
                    virtual_move = self.env['account.move'].new(vals)
                    generated_name = virtual_move.with_context(_dte_auto_generated=True)._generate_dte_name()
                    if generated_name:
                        rec.name = generated_name
                        _logger.info("SIT-haciendaws_fe | Nombre generado dinámicamente: %s para move_id=%s", rec.name, rec.id)
                    else:
                        _logger.warning("SIT-haciendaws_fe | No se pudo generar nombre dinámicamente para move_id=%s", rec.id)

            # --- Reforzar partner obligatorio ---
            partner_id = rec.partner_id.id
            if not partner_id:
                for line in rec.line_ids:
                    if line.partner_id:
                        partner_id = line.partner_id.id
                        break
                if partner_id:
                    rec.partner_id = partner_id
            if not rec.partner_id and journal.type == constants.TYPE_VENTA:
                raise UserError(_("No se pudo obtener el partner para move_id=%s") % rec.id)

            # --- Ajustes finales: logs, retenciones y seguro/flete ---
            if rec.partner_id:
                if rec.partner_id.gran_contribuyente:
                    rec.apply_retencion_iva = True
                else:
                    rec.apply_retencion_iva = False
            rec.agregar_lineas_seguro_flete()
            rec._copiar_retenciones_desde_documento_relacionado()

        # Aplicar defaults de partner si aplica
        moves_facturacion = base_records.filtered(lambda m: m.company_id.sit_facturacion)
        if moves_facturacion:
            moves_facturacion._apply_partner_defaults_ventas_if_needed()
            moves_facturacion._apply_partner_defaults_compras_if_needed()

        _logger.info("SIT | FIN create unificado. IDs creados: %s", base_records.ids)
        return base_records

    # -------------------------------
    # MÉTODO WRITE UNIFICADO
    # -------------------------------
    def write(self, vals):
        """
        Write unificado con soporte para:
        - Import DTE JSON: no generar/alterar líneas auxiliares ni renumerar 'name'.
        - Entradas simples/recibos: bypass rápido.
        - Compras no FSE: bypass rápido.
        - Respetar facturación activa por compañía antes de aplicar lógicas.
        - Evitar recursión y sobrevalidaciones.
        """
        _logger.info("SIT | Iniciando write unificado. Vals: %s", vals)

        # A) BYPASS para entries/receipts (mantén tu comportamiento)
        if all(m.move_type in (constants.TYPE_ENTRY, constants.OUT_RECEIPT, constants.IN_RECEIPT) for m in self):
            _logger.info("SIT | write bypass completo para move_type in (entry/receipts)")
            vals_to_write = vals.copy() if vals else {}
            for move in self:
                if move.name == "/" and move.journal_id and move.journal_id.sequence_id and move.journal_id.sequence_id.exists():
                    vals_to_write['name'] = move.journal_id.sequence_id.next_by_id()
                    _logger.info("SIT | Asignado name %s para entry %s", vals_to_write['name'], move.id)
            return super().write(vals_to_write)

        # B) Instalación, autogenerado u órdenes explícitas de saltar validaciones → bypass
        if self.env.context.get('install_mode') or self.env.context.get('_dte_auto_generated'):
            _logger.info("SIT | write ignorado por install_mode/_dte_auto_generated")
            return super().write(vals)

        if self.env.context.get('skip_sv_ensure_name'):
            _logger.info("SIT | write bypass por skip_sv_ensure_name")
            return super().write(vals)

        # C) Cambio a borrador: permitir reset sin fricción
        if vals.get('state') == 'draft':
            _logger.info("SIT | write bypass por cambio a borrador")
            return super().write(vals)

        # D) Cálculos internos que se autorreferencian
        if self.env.context.get('skip_compute'):
            _logger.info("SIT | write ignorado (skip_compute=True)")
            return super().write(vals)

        # E) Compras no FSE → bypass
        if all(m.move_type in (constants.IN_INVOICE, constants.IN_REFUND)
               and (not m.journal_id.sit_tipo_documento or m.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_FSE)
               for m in self):
            _logger.info("SIT-invoice_sv: Compra sin FSE detectada, write estándar.")
            return super().write(vals)

        # F) Si ninguna compañía de los moves tiene facturación activa → bypass
        if not any(m.company_id.sit_facturacion for m in self):
            _logger.info("SIT-write: Compañías sin facturación activa, write estándar.")
            return super().write(vals)

        # G) **Import DTE JSON**: write "seguro" (no tocar name, no inyectar líneas auxiliares)
        if self._is_dte_json_import():
            _logger.info("SIT | DTE JSON import detectado: write seguro (sin agregados ni renumeración).")

            # No forzar generación de name ni secuencias
            safe_ctx = dict(self.env.context)
            safe_ctx.update({
                'skip_name_validation': True,
                'skip_sv_ensure_name': True,
                '_dte_auto_generated': True,   # evita recursiones en tus propios hooks
            })

            # Escribir tal cual (no llamamos a agregar_lineas_seguro_flete ni copy retenciones)
            res = super(sit_account_move, self.with_context(safe_ctx)).write(vals)

            # Log mínimo post-write
            if len(self) == 1:
                _logger.warning("[WRITE-POST JSON] move_id=%s, name=%s", self.id, self.name)
            else:
                _logger.warning("[WRITE-POST JSON] Múltiples IDs: %s", self.ids)
            return res

        # H) Flujo normal (NO import JSON): asegurar name válido antes
        ctx = dict(self.env.context)
        ctx.update({
            'skip_name_validation': True,
            'skip_sv_ensure_name': True,
            '_dte_auto_generated': True,   # evita recursiones en tus propios hooks
        })
        for move in self:
            if not move.name or move.name == '/':
                try:
                    move.with_context(ctx)._ensure_name()
                except Exception as e:
                    _logger.exception("SIT | _ensure_name falló para move_id=%s: %s", move.id, e)

        # I) Escribir con contexto protegido
        self = self.with_context(ctx)
        res = super().write(vals)

        # J) Logs post-write (solo informativos)
        if len(self) == 1:
            _logger.warning("[WRITE-POST unificado] move_id=%s, name=%s", self.id, self.name)
        else:
            _logger.warning("[WRITE-POST unificado] Múltiples registros IDs: %s", self.ids)

        # K) Post-procesos SOLO si NO es import JSON
        facturas_aplican = self.filtered(lambda inv:
            inv.company_id.sit_facturacion and (
                inv.move_type in (constants.OUT_INVOICE, constants.OUT_REFUND)
                or (inv.move_type in (constants.IN_INVOICE, constants.IN_REFUND)
                    and inv.journal_id and inv.journal_id.sit_tipo_documento
                    and inv.journal_id.sit_tipo_documento.codigo == constants.COD_DTE_FSE)
            )
        )

        # Copiar retenciones si se tocan campos clave
        if facturas_aplican and any(k in vals for k in ['codigo_tipo_documento', 'reversed_entry_id', 'debit_origin_id']):
            try:
                facturas_aplican._copiar_retenciones_desde_documento_relacionado()
            except Exception:
                _logger.exception("SIT | Error copiando retenciones desde documento relacionado.")

        # Manejo de descuentos → tu lógica de líneas auxiliares
        if any(k in vals for k in {'descuento_gravado', 'descuento_exento', 'descuento_no_sujeto', 'descuento_global_monto'}):
            _logger.info("[WRITE-DESCUENTO] Detectado cambio de descuentos, agregando líneas de seguro/flete.")
            try:
                self.agregar_lineas_seguro_flete()
            except Exception:
                _logger.exception("SIT | Error en agregar_lineas_seguro_flete()")

        return res

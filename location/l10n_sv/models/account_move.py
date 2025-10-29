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
        for record in self:
            if record.invoice_date:
                # Solo número del mes con dos dígitos
                record.invoice_month = record.invoice_date.strftime('%m')
            else:
                record.invoice_month = ''


    sit_facturacion = fields.Boolean(
        related='company_id.sit_facturacion',
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

    @api.depends('partner_id')
    def _compute_get_tipo_documento(self):
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
        _logger.info("SIT | Iniciando create unificado para AccountMove. Vals_list: %s", vals_list)

        # BYPASS para movimientos que no son factura/nota (nómina, asientos manuales, recibos)
        # if any(v.get('move_type') in ('entry', 'out_receipt', 'in_receipt') for v in vals_list):
        #     return super().create(vals_list)

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
                    _logger.info(
                        "SIT | Diario con secuencia '%s', se deja name provisional '/' para generación automática",
                        journal.sequence_id.name)
                else:
                    _logger.info("SIT | Diario sin secuencia, asignado name provisional '/'")

        # --- Si ya viene move_type definido, usar create estándar ---
        # if all(not v.get('move_type') or v.get('move_type') not in (None, '') for v in vals_list):
        #     _logger.info("SIT | Todos los registros ya tienen move_type, se usa create estándar")
        #     return super().create(vals_list)

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

            # if rec.name == '/' and rec.journal_id.sequence_id:
            #     generated_name = rec.with_context(_dte_auto_generated=True)._generate_dte_name()
            #     if generated_name:
            #         rec.name = generated_name
            #     else:
            #         rec._ensure_name()

            # Verificamos si el nombre es correcto antes de guardar
            if not rec.name or rec.name == '/':
                _logger.info("SIT | Asignando name secuencial %s para move_id=%s", rec.name, rec.id)

                # Verificar si el diario tiene secuencia configurada
                if company and not company.sit_facturacion and rec.journal_id.sequence_id:
                    # Asignar el nombre secuencial si existe la secuencia
                    rec.name = rec.journal_id.sequence_id.next_by_id()
                    _logger.info("SIT | Secuencia asignada a move_id=%s: %s", rec.id, rec.name)
                else:
                    # Asignar un nombre predeterminado o manejar el caso si no hay secuencia
                    # rec.name = '/'
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
                if journal and (
                        not journal.sit_tipo_documento or journal.sit_tipo_documento.codigo != constants.COD_DTE_FSE):
                    _logger.info(
                        "SIT-haciendaws_fe | Documento de compra sin tipo DTE, omitiendo lógica DTE. move_id=%s",
                        rec.id)
                    rec.hacienda_codigoGeneracion_identificacion = None
                    tipo_documento_obj = self.env['account.journal.tipo_documento.field']
                    if move_type == constants.IN_REFUND:
                        doc = tipo_documento_obj.search([('codigo', '=', constants.COD_DTE_NC)], limit=1)
                        rec.sit_tipo_documento_id = doc
                    elif move_type == constants.IN_INVOICE and rec.debit_origin_id:
                        doc = tipo_documento_obj.search([('codigo', '=', constants.COD_DTE_ND)], limit=1)
                        rec.sit_tipo_documento_id = doc
                else:
                    _logger.info(
                        "SIT-haciendaws_fe | Documento de compra con tipo DTE FSE, procesando con lógica personalizada. move_id=%s",
                        rec.id)

            # --- Validación de empresa con facturación activa ---
            if not any(vals.get('company_id') and self.env['res.company'].browse(vals['company_id']).sit_facturacion for
                       vals in vals_list):
                _logger.info(
                    "SIT-create: Ninguna factura pertenece a empresa con facturación activa, se usa create estándar.")
                # Asignar name secuencial después
                # for move in base_records:
                # if (move.name in ('/', False)) and move.journal_id.sequence_id:
                # move.name = move.journal_id.sequence_id.next_by_id()
                # _logger.info("SIT-create: Asignado name secuencial %s para move_id=%s", move.name, move.id)
                return base_records

            # --- Generación dinámica de nombre para venta/compra ---
            if journal and (journal.type == 'sale' or move_type == 'in_invoice'):
                if not rec.name or rec.name in ('/', False):
                    virtual_move = self.env['account.move'].new(vals)
                    generated_name = virtual_move.with_context(_dte_auto_generated=True)._generate_dte_name()
                    if generated_name:
                        rec.name = generated_name
                        _logger.info("SIT-haciendaws_fe | Nombre generado dinámicamente: %s para move_id=%s", rec.name,
                                     rec.id)
                    else:
                        _logger.warning("SIT-haciendaws_fe | No se pudo generar nombre dinámicamente para move_id=%s",
                                        rec.id)

            # --- Reforzar partner obligatorio ---
            partner_id = rec.partner_id.id
            if not partner_id:
                for line in rec.line_ids:
                    if line.partner_id:
                        partner_id = line.partner_id.id
                        break
                if partner_id:
                    rec.partner_id = partner_id
            if not rec.partner_id and journal.type == 'sale':
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
        _logger.info("SIT | Iniciando write unificado. Vals: %s", vals)

        # --- Evitar lógica personalizada para asientos contables simples (entry) ---
        if all(inv.move_type == constants.TYPE_ENTRY for inv in self):
            _logger.info("SIT | write bypass completo para move_type=entry")

            # Crear un diccionario temporal para asignar nombres de secuencia
            vals_to_write = vals.copy() if vals else {}
            for move in self:
                if move.name == "/" and move.journal_id:
                    # Prioriza la secuencia de entry si existe
                    sequence = move.journal_id.sequence_id
                    if sequence and sequence.exists():
                        # Asignamos al diccionario, evitando recursión
                        vals_to_write['name'] = sequence.next_by_id()
                        _logger.info(f"SIT | Asignado name {vals_to_write['name']} para entry {move.id}")
            return super().write(vals_to_write)

        # --- OMITIR validación si NO es factura de venta con DTE ---
        if self.env.context.get('install_mode') or self.env.context.get('_dte_auto_generated'):
            _logger.info("SIT | write ignorado por instalación de módulo o autogenerado")
            return super().write(vals)

        # Bypass total cuando venimos del _ensure_name() del otro modulo
        # evitar reentrar en validaciones y cortar la recursion
        if self.env.context.get('skip_sv_ensure_name'):
            _logger.info("SIT | write bypass por skip_sv_ensure_name en contexto")
            return super().write(vals)

        # Si estamos pasando a booorrrrador (button_draft) omitimos validaciones de name
        # al despostear Odoo puede resetear el name a '/' y esto debe permitirse
        if vals.get('state') == 'draft':
            _logger.info("SIT | write bypass por cambio a borrador en contexto")
            return super().write(vals)

        # --- Evitar recursión si viene desde _compute_totales_retencion_percepcion ---
        if self.env.context.get('skip_compute'):
            _logger.info("SIT | write ignorado (skip_compute=True)")
            return super().write(vals)

        # --- Evitar lógica para compras sin tipo de documento FSE (14) ---
        # Si es una factura de compra y el tipo de documento no es FSE (código 14), omitir lógica personalizada
        if all(inv.move_type in (constants.IN_INVOICE, constants.IN_REFUND)
               and (not inv.journal_id.sit_tipo_documento or inv.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_FSE)
               for inv in self):
            _logger.info("SIT-invoice_sv: Factura de compra detectada, se salta la lógica personalizada.")
            return super().write(vals)

        # --- Validación de empresa ---
        if not any(move.company_id.sit_facturacion for move in self):
            _logger.info("SIT-write: Ninguna factura pertenece a empresa con facturación activa. Usando write estándar.")
            res = super().write(vals)
            # for move in self:
            #     if not move.name or move.name == '/':
            #         sequence = move.journal_id.sequence_id
            #         if sequence:
            #             move.name = sequence.next_by_id()
            #             _logger.info("SIT | Asignado name estándar %s para move_id=%s", move.name, move.id)
            # return res
            return super().write(vals)

        ctx = self.env.context.copy()
        ctx['_dte_auto_generated'] = True
        ctx['skip_name_validation'] = True
        ctx['skip_sv_ensure_name'] = True

        # Asegurar name válido antes de super()
        for move in self:
            if not move.name or move.name == '/':
                move.with_context(ctx)._ensure_name()

        # asegurarnos que las facturas de venta sin nombre lo tengan
        # to_name = self.filtered(
        #     lambda m: (m.move_type not in (constants.IN_INVOICE, constants.IN_REFUND) or
        #                (m.move_type in (
        #                    constants.IN_INVOICE) and m.journal_id and m.journal_id.sit_tipo_documento and m.journal_id.sit_tipo_documento.codigo == constants.COD_DTE_FSE))
        #               and (not m.name or m.name == '/')
        # )
        # if to_name:
        #     _logger.info("[WRITE-pre haciendaws_fe] Asegurando name para facturas de venta sin nombre: %s", to_name.ids)
        #     to_name.with_context(ctx, skip_sv_ensure_name=True)._ensure_name()

        # res = super(AccountMove, self.with_context(ctx)).write(vals)
        self = self.with_context(ctx)
        res = super().write(vals)

        # Logs post-write
        if len(self) == 1:
            _logger.warning("[WRITE-POST unificado] move_id=%s, name=%s", self.id, self.name)
        else:
            _logger.warning("[WRITE-POST unificado] Múltiples registros IDs: %s", self.ids)

        # Filtrar facturas que aplican a facturación electrónica
        facturas_aplican = self.filtered(lambda inv: inv.company_id.sit_facturacion and
                                                     (inv.move_type in (constants.OUT_INVOICE, constants.OUT_REFUND) or
                                                      (inv.move_type in (constants.IN_INVOICE, constants.IN_REFUND) and inv.journal_id and inv.journal_id.sit_tipo_documento and inv.journal_id.sit_tipo_documento.codigo == constants.COD_DTE_FSE))
                                         )

        # Copiar retenciones si se modifican campos clave
        if facturas_aplican and any(
                k in vals for k in ['codigo_tipo_documento', 'reversed_entry_id', 'debit_origin_id']):
            facturas_aplican._copiar_retenciones_desde_documento_relacionado()

        # Recalcular totales de percepción/retención/renta
        # for move in self:
        #     if move.line_ids:
        #         move._compute_totales_retencion_percepcion()
        #         _logger.info(
        #             "SIT | Totales recalculados write move_id=%s -> Percepción=%.2f | Retención IVA=%.2f | Renta=%.2f",
        #             move.id, move.percepcion_amount, move.retencion_iva_amount, move.retencion_renta_amount)

        # Manejo de descuentos
        campos_descuento = {'descuento_gravado', 'descuento_exento', 'descuento_no_sujeto', 'descuento_global_monto'}
        if any(c in vals for c in campos_descuento):
            _logger.info("[WRITE-DESCUENTO] Se detectaron campos de descuento, agregando líneas de seguro/flete")
            self.agregar_lineas_seguro_flete()

        return res




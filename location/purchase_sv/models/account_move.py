# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime
from odoo.tools import float_round
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError

import logging
_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo constants [purchase-account_move]")
except ImportError as e:
    _logger.error(f"Error al importar 'constants': {e}")
    constants = None

class AccountMove(models.Model):
    _inherit = 'account.move'

    document_number = fields.Char("Número de documento de proveedor")

    # Campo real: Many2one que se guarda en la BD
    sit_tipo_documento_id = fields.Many2one(
        'account.journal.tipo_documento.field',
        string='Tipo de Documento',
        # related='journal_id.sit_tipo_documento',
        store=True,
        default=lambda self: self._get_default_tipo_documento(),
        # domain=lambda self: self._get_tipo_documento_domain(),
    )

    fecha_aplicacion = fields.Date(string="Fecha de Aplicación")

    fecha_iva = fields.Date(string="Fecha IVA")

    #CAMPOS NUMERICOS EN DETALLE DE COMPRAS
    # comp_exenta_nsuj = fields.Float(
    #     string="Compras Internas Exentas y/o No Sujetas",
    #     digits=(16, 2),  # 16 dígitos totales, 2 decimales
    #     help="Ingrese un valor decimal, por ejemplo 1234.56"
    # )
    #
    # inter_exenta_nsuj = fields.Float(
    #     string="Internaciones Exentas y/o No Sujetas",
    #     digits=(16, 2),  # 16 dígitos totales, 2 decimales
    #     help="Ingrese un valor decimal, por ejemplo 1234.56"
    # )
    #
    # importacion_exenta_nsuj = fields.Float(
    #     string="Importaciones Exentas y/o No Sujetas",
    #     digits=(16, 2),  # 16 dígitos totales, 2 decimales
    #     help="Ingrese un valor decimal, por ejemplo 1234.56"
    # )
    #
    # inter_gravada = fields.Float(
    #     string="Compras Internas Gravadas",
    #     digits=(16, 2),  # 16 dígitos totales, 2 decimales
    #     help="Ingrese un valor decimal, por ejemplo 1234.56"
    # )
    #
    # inter_gravada_bien = fields.Float(
    #     string="Internaciones Gravadas de Bienes",
    #     digits=(16, 2),  # 16 dígitos totales, 2 decimales
    #     help="Ingrese un valor decimal, por ejemplo 1234.56"
    # )
    #
    # impor_gravada_bien = fields.Float(
    #     string="Importaciones Gravadas de Bienes",
    #     digits=(16, 2),  # 16 dígitos totales, 2 decimales
    #     help="Ingrese un valor decimal, por ejemplo 1234.56"
    # )
    #
    # impor_gravada_servicio = fields.Float(
    #     string="Importaciones Gravadas de Servicios",
    #     digits=(16, 2),  # 16 dígitos totales, 2 decimales
    #     help="Ingrese un valor decimal, por ejemplo 1234.56"
    # )


    # Campo name editable
    name = fields.Char(
        string='Number',
        readonly=False,  # editable siempre
        copy=False,
        default='/',
        help="Editable siempre por el usuario"
    )

    _original_name = fields.Char(compute='_compute_original_name', store=False)

    sit_amount_tax_system = fields.Monetary(
        string="SIT Amount Tax System",
        compute="_compute_sit_amount_tax_system",
        store=True,
    )

    invoice_line_ids_view_id = fields.Many2one(
        'ir.ui.view',
        string="Vista de líneas",
        compute='_compute_invoice_line_view',
        store=False
    )

    # @api.depends('move_type')
    # def _compute_invoice_line_view(self):
    #     for move in self:
    #         if move.move_type == 'in_invoice':  # compras
    #             move.invoice_line_ids_view_id = self.env.ref('purchase_sv.invoice_line_in_purchase_list').id
    #         else:  # ventas
    #             move.invoice_line_ids_view_id = self.env.ref('purchase_sv.invoice_line_out_sale_list').id
    #         _logger.info("SIT | move_id=%s | move_type=%s | view=%s", move.id, move.move_type, move.invoice_line_ids_view_id.name)

    @api.model_create_multi
    def create(self, vals_list):
        _logger.info("SIT Purchase | Creando AccountMove(s)")

        # Primero creamos los registros normalmente
        moves = super().create(vals_list)

        # Luego forzamos None en compras y notas de crédito de compra
        for move in moves:
            if (move.move_type in (constants.IN_INVOICE, constants.IN_REFUND) and
                    (not move.journal_id.sit_tipo_documento or move.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_FSE)):
                _logger.info(f"SIT | move_type={move.move_type} → Forzando None a hacienda_codigoGeneracion_identificacion para move_id={move.id}")
                move.hacienda_codigoGeneracion_identificacion = None
        return moves

    def _get_default_tipo_documento(self):
        # Lógica para obtener el valor predeterminado según el contexto o condiciones
        return self.env['account.journal.tipo_documento.field'].search([('codigo', '=', '01')], limit=1)

    @api.onchange('move_type')
    def _get_tipo_documento_domain(self):
        # Lógica para establecer el dominio del campo para siempre mostrar los documentos con los códigos especificados
        # Mostrar los tipos de documentos con los códigos '03', '05', '06', '11' en todos los casos
        # Las compras de tipo nota de credito(05) y nota de debito(06) se generan desde la funcionalidad de odoo
        if self.move_type == 'in_refund' and self.sit_tipo_documento_id.codigo == constants.COD_DTE_NC: # Nota de credito en compras
            return [('codigo', 'in', ['05'])]
        elif self.move_type == 'in_invoice' and self.sit_tipo_documento_id.codigo == constants.COD_DTE_ND: # Notas de debito en compras
            return [('codigo', 'in', ['06'])]
        else:
            return [('codigo', 'in', ['01', '03', '11'])]

    @api.onchange('name', 'hacienda_codigoGeneracion_identificacion', 'hacienda_selloRecibido')
    def _onchange_remove_hyphen_and_spaces(self):
        if (self.move_type not in(constants.IN_INVOICE, constants.IN_REFUND) or
                (self.move_type == constants.IN_INVOICE and self.journal_id.sit_tipo_documento and self.journal_id.sit_tipo_documento.codigo == constants.COD_DTE_FSE)):
            return

        # name
        if self.name:
            old_name = self.name
            self.name = self.name.replace('-', '').replace(' ', '')
            if old_name != self.name:
                _logger.info("[ONCHANGE] move_id=%s: 'name' changed from '%s' to '%s'", self.id, old_name, self.name)

        # hacienda_codigoGeneracion_identificacion
        if self.hacienda_codigoGeneracion_identificacion:
            old_val = self.hacienda_codigoGeneracion_identificacion
            self.hacienda_codigoGeneracion_identificacion = old_val.replace('-', '').replace(' ', '')
            if old_val != self.hacienda_codigoGeneracion_identificacion:
                _logger.info(
                    "[ONCHANGE] move_id=%s: 'hacienda_codigoGeneracion_identificacion' changed from '%s' to '%s'",
                    self.id, old_val, self.hacienda_codigoGeneracion_identificacion)

        # hacienda_selloRecibido
        if self.hacienda_selloRecibido:
            old_val = self.hacienda_selloRecibido
            self.hacienda_selloRecibido = old_val.replace('-', '').replace(' ', '')
            if old_val != self.hacienda_selloRecibido:
                _logger.info(
                    "[ONCHANGE] move_id=%s: 'hacienda_selloRecibido' changed from '%s' to '%s'",
                    self.id, old_val, self.hacienda_selloRecibido)

    @api.depends('invoice_line_ids.price_unit', 'invoice_line_ids.quantity', 'invoice_line_ids.discount', 'invoice_line_ids.tax_ids', 'currency_id', 'move_type', 'partner_id',)
    def _compute_sit_amount_tax_system(self):
        for move in self:
            if (move.move_type in (constants.IN_INVOICE, constants.IN_REFUND) and
                    (not move.journal_id.sit_tipo_documento or move.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_FSE)):
                total_tax = 0.0
                _logger.info("SIT | Calculando impuestos para move: %s", move.name)

                for line in move.invoice_line_ids:
                    if not line.tax_ids:
                        _logger.info("SIT | Línea %s sin impuestos", line.name)
                        continue

                    price_after_discount = line.price_unit * (1 - (line.discount or 0.0) / 100)
                    _logger.info("SIT | Línea %s precio unitario: %s, cantidad: %s, precio tras descuento: %s",
                                 line.name, line.price_unit, line.quantity, price_after_discount)

                    tax_res = line.tax_ids.compute_all(
                        price_after_discount,
                        quantity=line.quantity,
                        product=line.product_id,
                        partner=move.partner_id,
                    )

                    total_tax_line = tax_res['total_included'] - tax_res['total_excluded']
                    _logger.info("SIT | Línea %s total_tax calculado: %s", line.name, total_tax_line)
                    total_tax += total_tax_line

                if move.move_type in ('in_refund', 'out_refund'):
                    total_tax *= -1
                    _logger.info("SIT | Ajuste por nota de crédito: total_tax=%s", total_tax)

                move.sit_amount_tax_system = move.currency_id.round(total_tax)
                _logger.info("SIT | move %s sit_amount_tax_system final: %s", move.name, move.sit_amount_tax_system)

    def write(self, vals):
        _logger.info("SIT | Entrando a write, context=%s", self.env.context)
        _logger.info("SIT | Vals write: %s", vals)

        # --- OMITIR validación si NO es factura de venta con DTE ---
        if self.env.context.get('module') or self.env.context.get('_dte_auto_generated'):
            _logger.info("SIT | write ignorado por instalación de módulo o autogenerado")
            return super().write(vals)

        _logger.info("SIT | Vals write: %s", vals)
        # Validar si el campo 'name' está presente en vals y si está vacío
        if (not self.exists() or self.filtered(lambda m: not m.name)) and ('name' not in vals or not vals['name']):
            _logger.warning(
                "[WRITE-VALIDATION] Asignando '/' por defecto al campo 'name' porque estaba vacío o no existe")
            vals['name'] = '/'

        if 'name' in vals:
            for move in self:
                if (move.move_type in (constants.IN_INVOICE, constants.IN_REFUND) and
                        (not move.journal_id.sit_tipo_documento or move.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_FSE)):
                    continue

                _logger.info("Tipo de documento(dte): %s", move.codigo_tipo_documento)
                if not move.codigo_tipo_documento:
                    continue

                old_name = move.name or ''
                new_name = vals.get('name') or ''

                _logger.info(
                    "[WRITE-VALIDATION] move_id=%s, state=%s, old_name=%s, new_name=%s, "
                    "auto_generated=%s, manual_update=%s, allow_name_reset=%s",
                    move.id, move.state, old_name, new_name,
                    self.env.context.get("_dte_auto_generated"),
                    self.env.context.get("_dte_manual_update"),
                    self.env.context.get("allow_name_reset")
                )

                # Si el valor no cambia, dejamos pasar
                if old_name == new_name:
                    _logger.info(
                        "Account_move_purchase [WRITE-VALIDATION] El valor de 'name' no cambió (se mantiene %s). Permitido.",
                        old_name
                    )
                    continue

                # Si no viene con el flag de generación automática → bloquear
                bloquear = True  # asumimos que siempre se bloquea

                # Permitir reset a '/'
                if old_name == '/' and new_name != '/':
                    bloquear = False
                # Permitir actualización desde onchange / auto-generada
                elif self.env.context.get("_dte_auto_generated") or self.env.context.get('install_mode'):
                    bloquear = False
                # Permitir actualización manual explícita
                elif self.env.context.get("_dte_manual_update"):
                    bloquear = False
                    # Permitir limpiar el name si se está recreando (nuevo_name vacío)
                elif not new_name and old_name:
                    _logger.info(
                        "Se permite limpiar el campo name temporalmente (old_name=%s, new_name vacío, move_id=%s)",
                        old_name, move.id)
                    bloquear = False

                _logger.info(
                    "SIT Bloquear modificacion de name: %s, name anterior: %s, nuevo name. %s",
                    bloquear, old_name, new_name
                )

                _logger.info("SIT Bloquear modificacion de name: %s, name anterior: %s, nuevo name. %s", bloquear,
                             old_name, new_name)
                if bloquear:
                    _logger.warning(
                        "[WRITE-VALIDATION] Intento de modificar manualmente el 'name' en factura de venta "
                        "(move_id=%s). Valor anterior: %s → Nuevo valor: %s",
                        move.id, old_name, new_name
                    )
                    raise UserError(
                        _("No está permitido modificar manualmente el número de la factura de venta, "
                          "ni en borrador ni validada.")
                    )

                _logger.info(
                    "[WRITE-VALIDATION] Cambio de 'name' permitido. Valor anterior: %s → Nuevo valor: %s",
                    old_name, new_name
                )
        return super().write(vals)

    def action_post(self):
        _logger.info("SIT Action post purchase: %s", self)
        for move in self:

            _logger.info("SIT-Compra move type: %s, tipo documento %s: ", move.move_type, move.codigo_tipo_documento)
            if move.move_type not in(constants.IN_INVOICE, constants.IN_REFUND):
                _logger.info("SIT Action post no aplica a modulos distintos a compra.")
                continue
            if move.move_type == constants.IN_INVOICE and move.journal_id.sit_tipo_documento:
                _logger.info("SIT Action post no aplica para compras electronicas(como suejto excluido).")
                continue

            if move.move_type == constants.IN_INVOICE and move.journal_id.sit_tipo_documento and move.hacienda_codigoGeneracion_identificacion:
                existing = self.search([
                    ('id', '!=', move.id),
                    ('hacienda_codigoGeneracion_identificacion', '=', move.hacienda_codigoGeneracion_identificacion)
                ], limit=1)
                if existing:
                    raise ValidationError(_(
                        "El Número de Resolución '%s' ya existe en otro documento (%s)."
                    ) % (move.hacienda_codigoGeneracion_identificacion, existing.name))

            if not move.fecha_aplicacion:
                _logger.info("SIT | Fecha de aplicacion no seleccionada.")
                raise ValidationError("Debe seleccionar la Fecha de Aplicación.")

            if not move.fecha_iva:
                _logger.info("SIT | Fecha IVA no seleccionada.")
                raise ValidationError("Debe seleccionar la Fecha de IVA.")

            fecha_iva = move.fecha_iva
            date_invoice = move.invoice_date

            _logger.info("SIT | Fecha factura: %s, Fecha IVA: %s.", date_invoice, fecha_iva)
            if fecha_iva and date_invoice:
                # Ambas son fechas, se comparan directamente
                if fecha_iva < date_invoice:
                    _logger.info(
                        "SIT | Fecha IVA (%s) no debe ser menor a la fecha de la factura (%s).",
                        fecha_iva,
                        date_invoice
                    )
                    raise ValidationError(
                        "Fecha IVA (%s) no debe ser menor a la fecha de la factura (%s)." % (
                            fecha_iva,
                            date_invoice
                        )
                    )
            if not move.sit_tipo_documento_id:
                _logger.info("SIT | Tipo de documento no seleccionado.")
                raise ValidationError("Debe seleccionar el Tipo de documento de compra.")

            if not move.clase_documento_id:
                _logger.info("SIT | Clase de documento no seleccionada.")
                raise ValidationError("Debe seleccionar la Clase de documento.")

            if not move.hacienda_selloRecibido:
                _logger.info("SIT | Sello Recepcion no agregado.")
                raise ValidationError("Debe agregar el Sello de recepción.")

            if not move.hacienda_codigoGeneracion_identificacion:
                _logger.info("SIT | Codigo de generacion no agregado.")
                raise ValidationError("Debe agregar el Codigo de generación.")

            # Generar las líneas de percepción/retención/renta antes de postear
            move.generar_asientos_retencion_compras()
        return super(AccountMove, self).action_post()

    def _post(self, soft=True):
        _logger.info("SIT Purchase.")

        result = super(AccountMove, self)._post(soft=soft)

        for move in self:
            if move.move_type not in (constants.IN_INVOICE, constants.IN_REFUND):
                _logger.info("SIT Post no aplica a modulos distintos a compra.")
                continue

            if move.move_type == constants.IN_INVOICE and move.journal_id.sit_tipo_documento:
                _logger.info("SIT Post no aplica para compras electronicas(como suejto excluido).")
                continue

            _logger.info("SIT-Purchase Move id: %s", move.id)

            _logger.info("SIT-Purchase Compra anulada: %s", move.sit_invalidar)
            AccountInvalidacion = self.env['account.move.invalidation']
            if move.sit_invalidar:
                invalidacion = AccountInvalidacion.search([
                    ('sit_factura_a_reemplazar', '=', move.id)
                ])
                _logger.info("SIT-Purchase Invaldiacion: %s", invalidacion)

                if invalidacion:
                    _logger.info("SIT-Purchase Invaldiacion existe: %s", invalidacion)
                    continue  # Ya existe la invalidación, no hacer nada más, pero seguir con el resto del flujo
                else:
                    _logger.info("SIT-Purchase Invaldiacion no existe, creando anulacion: %s", invalidacion)
                    move.sit_factura_a_reemplazar = move.id
                    move.action_button_anulacion()

        # Devuelve el resultado original para que Odoo siga funcionando
        return result

    exp_duca_id = fields.One2many('exp_duca', 'move_id', string='DUCAs')
    def generar_asientos_retencion_compras(self):
        """
        Genera automáticamente las líneas contables de **percepción**, **retención** y **renta**
        para facturas de compra (`in_invoice`) y notas de crédito de compra (`in_refund`), acumulando
        los valores de cada línea (`account.move.line`) y creando líneas contables en el asiento.

        Solo se aplica si el asiento está en borrador.
        No reemplaza otras líneas del asiento que no sean de percepción/retención/renta.
        Las cuentas deben estar configuradas en la compañía:
        - `iva_percibido_account_id`
        - `retencion_iva_account_id`
        - `retencion_renta_account_id`
        """
        for move in self:
            _logger.info(f"SIT | [Move {move.id}] Inicio de generación de asientos ret./perc./renta")

            if (move.move_type not in (constants.IN_INVOICE, constants.IN_REFUND) or
                    (move.move_type == constants.IN_INVOICE and move.journal_id.sit_tipo_documento)):
                _logger.info(f"SIT | [Move {move.id}] No aplica: solo compras o notas de crédito de compra.")
                continue

            if move.state != 'draft':
                _logger.warning(
                    f"SIT | [Move {move.id}] No se puede modificar, no está en borrador (estado={move.state}).")
                continue

            company = move.company_id
            currency = move.currency_id
            precision = currency.rounding or 0.01

            # --- Detalle de líneas
            _logger.info(f"SIT | [Move {move.id}] Revisando {len(move.invoice_line_ids)} líneas de factura")
            for line in move.invoice_line_ids:
                _logger.info(
                    f"SIT | [Move {move.id}] Línea {line.id}: subtotal={line.price_subtotal}, "
                    f"apply_percepcion={line.apply_percepcion}, percepcion_amount={line.percepcion_amount}, "
                    f"apply_retencion={line.apply_retencion}, retencion_amount={line.retencion_amount}, "
                    f"renta_percentage={line.renta_percentage}"
                )

            # Acumular montos
            total_percepcion = sum(line.percepcion_amount for line in move.invoice_line_ids)
            total_retencion = sum(line.retencion_amount for line in move.invoice_line_ids)
            total_renta = sum(line.renta_amount for line in move.invoice_line_ids)

            _logger.info(
                f"SIT | [Move {move.id}] Totales calculados -> Percepción: {total_percepcion}, "
                f"Retención IVA: {total_retencion}, Renta: {total_renta}"
            )

            # Eliminar líneas previas de este tipo
            previas = move.line_ids.filtered(lambda l: l.name in ["Percepción", "Retención IVA", "Renta"])
            if previas:
                _logger.info(
                    f"SIT | [Move {move.id}] Eliminando {len(previas)} líneas previas de retención/percepción/renta")
                previas.unlink()

            lineas = []

            def redondear(monto):
                return float_round(monto or 0.0, precision_rounding=precision)

            # --- Percepción
            if total_percepcion > 0 and company.iva_percibido_account_id:
                lineas.append({
                    'name': 'Percepción',
                    'account_id': company.iva_percibido_account_id.id,
                    'debit': redondear(total_percepcion),
                    'credit': 0.0,
                    'move_id': move.id,
                })
                _logger.info(f"SIT | [Move {move.id}] Línea de Percepción lista: {redondear(total_percepcion)}")

            # --- Retención IVA
            if total_retencion > 0 and company.retencion_iva_account_id:
                lineas.append({
                    'name': 'Retención IVA',
                    'account_id': company.retencion_iva_account_id.id,
                    'debit': 0.0,
                    'credit': redondear(total_retencion),
                    'move_id': move.id,
                })
                _logger.info(f"SIT | [Move {move.id}] Línea de Retención IVA lista: {redondear(total_retencion)}")

            # --- Renta
            if total_renta > 0 and company.retencion_renta_account_id:
                lineas.append({
                    'name': 'Renta',
                    'account_id': company.retencion_renta_account_id.id,
                    'debit': 0.0,
                    'credit': redondear(total_renta),
                    'move_id': move.id,
                })
                _logger.info(f"SIT | [Move {move.id}] Línea de Renta lista: {redondear(total_renta)}")

            if lineas:
                move.write({'line_ids': [(0, 0, vals) for vals in lineas]})
                _logger.info(f"SIT | [Move {move.id}] Se agregaron {len(lineas)} líneas contables de ret./perc./renta")
            else:
                _logger.info(f"SIT | [Move {move.id}] No hay montos para agregar (percepción/retención/renta)")

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
from odoo.tools import float_round
from datetime import time, timedelta
import pytz

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants

    _logger.info("SIT Modulo config_utils")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    constants = None

TIPOS_AUSENCIA = {
    # 'ASISTENCIA': 'WORK100',
    'PERMISO_SG': 'PERMISO_SG',
    'VACACIONES': 'VACACIONES',
    'INCAPACIDAD': 'INCAPACIDAD',
    'FALTA_INJ': 'FALTA_INJ',
}


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # Filtrado líneas salariales (solo las reglas que aparecen en payslip)
    line_ids_filtered = fields.One2many(
        comodel_name='hr.payslip.line',
        compute='_compute_line_ids_filtered',
        string='Cálculo del salario (filtrado)',
        store=False,
    )

    # Filtrado líneas de inputs según códigos de reglas visibles
    input_line_ids_filtered = fields.One2many(
        comodel_name='hr.payslip.input',
        compute='_compute_input_line_ids_filtered',
        string='Entradas filtradas',
        store=False,
    )

    payslip_principal_id = fields.Many2one(
        'hr.payslip',
        string='Nómina Principal',
        help='Nómina regular relacionada para tomar deducciones al generar esta nómina de vacaciones'
    )

    skip_deductions = fields.Boolean(
        string="Omitir deducciones",
        help="Si se marca, no se calcularán deducciones en este recibo."
    )

    @api.depends('line_ids.salary_rule_id.appears_on_payslip')
    def _compute_line_ids_filtered(self):
        """
        Computa las líneas de la nómina (`line_ids_filtered`) que deben mostrarse en el recibo de pago.

        Este campo computado filtra las líneas de salario (`hr.payslip.line`) cuya regla salarial
        asociada (`salary_rule_id`) tenga el campo `appears_on_payslip=True`.

        Esto permite separar visualmente, por ejemplo, descuentos patronales u otras reglas técnicas
        que no deben mostrarse al empleado en el recibo.
        """
        for rec in self:
            rec.line_ids_filtered = rec.line_ids.filtered(
                lambda l: l.salary_rule_id and l.salary_rule_id.appears_on_payslip
            )

    @api.depends('input_line_ids', 'line_ids.salary_rule_id.appears_on_payslip')
    def _compute_input_line_ids_filtered(self):
        """
        Computa las entradas (inputs) filtradas (`input_line_ids_filtered`) que deben mostrarse.

        Se basa en los códigos de las reglas salariales visibles (definidas por `appears_on_payslip=True`).
        Solo los inputs (`hr.payslip.input`) cuyo código coincida con una regla visible serán incluidos.

        Esto permite que, por ejemplo, los aportes del empleador (que no deben mostrarse) también
        se filtren de la vista de otras entradas.
        """
        for rec in self:
            # Obtiene los códigos de las líneas de nómina visibles
            visible_codes = rec.line_ids.filtered(
                lambda l: l.salary_rule_id and l.salary_rule_id.appears_on_payslip
            ).mapped('code')

            # Filtra las líneas de input que coinciden con esos códigos
            rec.input_line_ids_filtered = rec.input_line_ids.filtered(
                lambda i: i.code in visible_codes
            )

    # Método sobrescrito para calcular la nómina (payslip) personalizada
    def compute_sheet(self):
        # Registra el inicio del cálculo personalizado de la nómina
        _logger.info(">>> [INICIO] compute_sheet personalizado para %d nóminas", len(self))

        # Itera sobre cada nómina en la lista
        for payslip in self:
            # ✅ Si está marcado "Omitir deducciones", solo calcula lo demás
            if payslip.skip_deductions:
                _logger.info("Saltando deducciones en nómina %s (marcada como omitir)", payslip.name)
                super(HrPayslip, payslip).compute_sheet()
                continue  # seguimos con la siguiente nómina

            # ✅ Si es nómina de vacaciones (tiene principal asociada)
            if payslip.payslip_principal_id:
                principal = payslip.payslip_principal_id
                _logger.info("Nómina %s es de vacaciones y tiene principal vinculada: %s", payslip.name, principal.name)

                # Siempre ejecutamos el cálculo base primero
                super(HrPayslip, payslip).compute_sheet()

                # Verificamos si la principal omitió deducciones
                if principal.skip_deductions:
                    _logger.info("Principal %s tiene skip_deductions=True → sumaremos principal + vacaciones",
                                 principal.name)
                    payslip._calcular_deducciones_desde_dias_trabajados(include_principal=True)
                else:
                    _logger.info("Principal %s YA calculó deducciones → solo calculamos sobre vacaciones",
                                 principal.name)
                    payslip._calcular_deducciones_desde_dias_trabajados(include_principal=False)

                # ✅ Ahora agregamos automáticamente la regla VACACIONES (30% extra)
                payslip._agregar_regla_vacaciones(payslip)

                continue  # terminamos con esta nómina y seguimos

            # ✅ 3. Nómina normal SIN relación con vacaciones
            contract = payslip.contract_id
            _logger.info("Procesando nómina normal: %s para contrato %s", payslip.name,
                         contract.name if contract else "N/A")

            if not contract:
                _logger.warning("Nómina %s sin contrato, saltando deducciones", payslip.name)
                super(HrPayslip, payslip).compute_sheet()
                continue

            # Calcular base imponible acumulada (actual + previa)
            base_imponible = payslip.get_base_imponible_acumulada()
            _logger.info("Base imponible= %d", base_imponible)

            # Ejecutar cálculo base primero
            super(HrPayslip, payslip).compute_sheet()

            # Usar el método centralizado para crear los inputs
            self._crear_inputs_deducciones(payslip, contract, base_imponible)

        # Una vez generadas las deducciones → agregamos sabados/domingos y descuentos séptimo
        # self._agregar_inputs_sabado_y_domingos()
        # Aplicar descuento de séptimo por faltas injustificadas
        self._aplicar_descuento_septimo_por_faltas()

        # Llama al método original para completar el cálculo de la nómina

        res = super().compute_sheet()
        # Registra el fin del cálculo personalizado de la nómina
        _logger.info(">>> [FIN] compute_sheet personalizado completado")
        return res

    # ==========TIPOS DE ASISTENCIAS
    def _obtener_deducciones(self, contract, base_imponible):
        try:
            renta = contract.calcular_deduccion_renta(bruto=base_imponible)
            afp = contract.calcular_afp(bruto=base_imponible)
            isss = contract.calcular_isss(bruto=base_imponible)
            afp_patronal = contract.calcular_aporte_patronal(constants.TIPO_DED_AFP, bruto=base_imponible)
            isss_patronal = contract.calcular_aporte_patronal(constants.TIPO_DED_ISSS, bruto=base_imponible)
            incaf = contract.calcular_incaf(bruto=base_imponible)
        except Exception as e:
            _logger.error("Error al calcular deducciones para contrato %s: %s", contract.id, e)
            raise UserError(_("Ocurrió un error al calcular deducciones: %s") % str(e))

        return renta, afp, isss, afp_patronal, isss_patronal, incaf

    def get_base_imponible_acumulada(self):
        """Retorna la base imponible acumulada sumando nómina actual + nómina previa si aplica"""
        self.ensure_one()

        # ✅ Tomar el contrato
        contract = self.contract_id
        if not contract:
            _logger.warning("No hay contrato asociado a %s → base=0", self.name)
            return 0.0

        # ✅ Base actual (salario mensual del contrato)
        base_actual = contract.wage or 0.0
        _logger.info("Base imponible actual para %s = %.2f", self.name, base_actual)

        bruto_prev = 0.0

        # Si hay nómina previa asociada, sumarla
        if self.payslip_principal_id:
            bruto_prev = sum(self.payslip_principal_id.line_ids.filtered(
                lambda l: l.category_id and l.category_id.code == 'BASIC'
            ).mapped('total'))

            _logger.info(
                "Sumando nómina previa %s con bruto=%.2f",
                self.payslip_principal_id.name,
                bruto_prev
            )

        return base_actual + bruto_prev

    def _get_bruto_total(self):
        """
        Devuelve el total bruto de este payslip
        considerando salario base + asignaciones (categoría ALW)
        """
        bruto = sum(
            self.line_ids.filtered(
                lambda l: l.code == 'BASIC' or (l.category_id and l.category_id.code == 'ALW')
            ).mapped('total')
        )
        _logger.info("Bruto total calculado para %s = %.2f", self.name, bruto)
        return bruto

    def _crear_inputs_deducciones(self, slip, contract, base_total):
        """
        Método reutilizable para crear los inputs de deducciones (RENTA, AFP, ISSS, etc.)
        a partir de una base imponible.
        """
        # Primero eliminamos entradas previas para evitar duplicados
        for code in ['RENTA', 'AFP', 'ISSS', 'ISSS_EMP', 'AFP_EMP', 'INCAF']:
            old_inputs = slip.input_line_ids.filtered(lambda l: l.code == code)
            if old_inputs:
                _logger.info("Eliminando inputs previos código %s para nómina %d", code, slip.id)
                old_inputs.unlink()

        # Obtener valores de deducciones
        renta, afp, isss, afp_patronal, isss_patronal, incaf = self._obtener_deducciones(contract, base_total)
        tipos = {
            code: self.env['hr.payslip.input.type'].search([('code', '=', code)], limit=1)
            for code in ['RENTA', 'AFP', 'ISSS', 'ISSS_EMP', 'AFP_EMP', 'INCAF']
        }

        # Validar que existan tipos
        for code, tipo in tipos.items():
            if not tipo:
                raise UserError(_("No se encontró el tipo de input para %s.") % code)

        # Determinar si es contrato profesional
        is_professional = contract.wage_type == constants.SERVICIOS_PROFESIONALES
        valores = []

        if is_professional:
            valores.append(('RENTA', -abs(renta)))
            _logger.info("Contrato de servicios profesionales → solo se agrega RENTA")
        else:
            valores = [
                ('RENTA', -abs(renta)),
                ('AFP', -abs(afp)),
                ('ISSS', -abs(isss)),
                ('ISSS_EMP', abs(isss_patronal)),
                ('AFP_EMP', abs(afp_patronal)),
                ('INCAF', -abs(incaf)),
            ]
            _logger.info("Deducciones calculadas: %s", valores)

        # Crear inputs en la nómina
        for code, valor in valores:
            tipo = tipos.get(code)
            if tipo:
                slip.input_line_ids.create({
                    'name': tipo.name,
                    'code': code,
                    'amount': float_round(valor, precision_digits=2),
                    'payslip_id': slip.id,
                    'input_type_id': tipo.id,
                })
                _logger.info("Input %s agregado a nómina %d con monto %.2f", code, slip.id, valor)

    def _calcular_deducciones_desde_dias_trabajados(self, include_principal=False):
        """
        Se usa para nóminas de vacaciones.
        Calcula deducciones basado en WORK100 actual + principal si aplica.
        """
        for slip in self:
            _logger.info("===== INICIO cálculo deducciones vacaciones =====")
            _logger.info("📄 Payslip: %s (ID: %d)", slip.name, slip.id)
            _logger.info("📅 Período: %s → %s", slip.date_from, slip.date_to)
            _logger.info("🏷️ Código interno: %s", slip.number or "SIN NUMERO")
            _logger.info("📦 Lote: %s", slip.payslip_run_id.name if slip.payslip_run_id else "N/A")
            _logger.info("🏗️ Estructura salarial: %s", slip.struct_id.name if slip.struct_id else "N/A")
            _logger.info("👤 Empleado: %s", slip.employee_id.name if slip.employee_id else "N/A")
            _logger.info("✅ Omitir deducciones? %s", "SÍ" if slip.skip_deductions else "NO")

            contract = slip.contract_id
            if not contract:
                _logger.warning("❌ NO HAY contrato asociado, se omite cálculo de deducciones")
                continue

            _logger.info("📑 Contrato: %s (ID %d)", contract.name, contract.id)
            _logger.info("💰 Salario base contrato: %.2f", contract.wage)

            # ===================== WORK100 ACTUAL ======================
            lineas_actual = slip.worked_days_line_ids.filtered(
                lambda l: l.code in ['WORK100', 'VAC', 'VACACIONES']
            )
            importe_actual = sum(linea.amount for linea in lineas_actual)
            _logger.info("WORK100 actual → %d líneas | Total $%.2f", len(lineas_actual), importe_actual)
            for l in lineas_actual:
                _logger.info("  - %s: días=%.2f horas=%.2f monto=%.2f",
                             l.name, l.number_of_days, l.number_of_hours, l.amount)

            # ===================== WORK100 PRINCIPAL (si aplica) ======================
            importe_principal = 0.0
            if include_principal and slip.payslip_principal_id:
                principal = slip.payslip_principal_id
                lineas_principal = principal.worked_days_line_ids.filtered(lambda l: l.code == 'WORK100')
                importe_principal = sum(linea.amount for linea in lineas_principal)
                _logger.info("✅ Incluyendo nómina principal: %s | Total $%.2f", principal.name, importe_principal)
                for lp in lineas_principal:
                    _logger.info("  - PRINCIPAL %s: días=%.2f horas=%.2f monto=%.2f",
                                 lp.name, lp.number_of_days, lp.number_of_hours, lp.amount)
            else:
                _logger.info("❌ No se incluye nómina principal para este cálculo")
        # ✅ Agregar entradas por asistencias como permisos sin goce, vacaciones, etc.
        # self._generar_worked_days_asistencia()
        # Dentro del método compute_sheet, al final:
        # self._agregar_inputs_sabado_y_domingos()
        self._asignar_importe_asistencia()
        # Llama al método original para completar el cálculo de la nómina

        # ===================== BASE FINAL ======================
        base_total = importe_actual + importe_principal if include_principal else importe_actual
        _logger.info("💵 Base imponible VACACIONES calculada = %.2f (actual %.2f + principal %.2f)",
                     base_total, importe_actual, importe_principal)

        # Log en chatter para que quede registrado en la nómina
        slip.message_post(body=_(
            "🔎 Cálculo de deducciones vacaciones:\n"
            "- Principal incluido: %s\n"
            "- Importe principal: %.2f\n"
            "- Importe actual: %.2f\n"
            "- Base total: %.2f"
        ) % (
           "✅ Sí" if include_principal else "❌ No",
           importe_principal, importe_actual, base_total
       ))

        _logger.info(">>> Ahora se llamará a _crear_inputs_deducciones con base %.2f", base_total)
        self._crear_inputs_deducciones(slip, contract, base_total)
        _logger.info("===== FIN cálculo deducciones vacaciones para %s =====", slip.name)

    def _asignar_importe_asistencia(self):
        """
        WORK100 = asistencia + permiso con goce + incapacidad pagada (máx 3 días)
        INCAPACIDAD_SIN_PAGO = incapacidad desde día 4, monto siempre 0
        """
        _logger.info(">>> Iniciando cálculo de días trabajados para %d nóminas", len(self))

        tz_local = pytz.timezone('America/El_Salvador')
        almuerzo_inicio = time(12, 0)
        almuerzo_fin = time(13, 0)
        duracion_almuerzo = 1.0  # horas de almuerzo a descontar si aplica

        for payslip in self:
            contract = payslip.contract_id
            if not contract:
                _logger.warning("Nómina %s sin contrato. Se omite.", payslip.name)
                continue

            empleado = payslip.employee_id
            if not empleado:
                _logger.warning("Nómina %s sin empleado asignado. Se omite.", payslip.name)
                continue

            fecha_inicio = payslip.date_from
            fecha_fin = payslip.date_to
            if not fecha_inicio or not fecha_fin:
                _logger.warning("Nómina %s no tiene rango de fechas definido, se omite.", payslip.name)
                continue

            _logger.info("#########################################################################")
            salario_mensual = (contract.wage * 2) or 0.0
            _logger.info("SALARIO MENSUAL:%s ", salario_mensual)

            salario_por_hora = salario_mensual / 30.0 / 8.0
            _logger.info("SALARIO HORA:%s ", salario_por_hora)

            _logger.info("#########################################################################")

            # 🔄 Limpiar líneas anteriores
            for code in ['WORK100', 'INCAPACIDAD_SIN_PAGO', 'INCAPACIDAD_PAGADA']:
                payslip.worked_days_line_ids.filtered(lambda l: l.code == code).unlink()

            # ======================================================
            # ✅ 1) Calcular ASISTENCIA + PERMISO_CG
            # ======================================================
            asistencias = self.env['hr.attendance'].search([
                ('employee_id', '=', empleado.id),
                ('check_in', '>=', fecha_inicio),
                ('check_out', '<=', fecha_fin),
                ('tipo_asistencia', 'in', ['ASISTENCIA', 'PERMISO_CG']),
                ('se_paga', '=', True)
            ])

            horas_asistencia = 0.0
            for att in asistencias:
                if att.check_in and att.check_out:
                    ci = att.check_in.astimezone(tz_local)
                    _logger.info("HORA DE ENTRADA:%s ", ci)
                    co = att.check_out.astimezone(tz_local)
                    _logger.info("HORA DE SALIDA:%s ", co)
                    diff = (co - ci).total_seconds() / 3600.0
                    _logger.info("HORA DE DIFERENCIA:%s ", diff)

                    # Descuento de almuerzo
                    cruza_almuerzo = (ci.time() < almuerzo_fin and co.time() > almuerzo_inicio)
                    if diff >= 5.0 and cruza_almuerzo:
                        diff -= duracion_almuerzo

                    horas_asistencia += round(diff, 2)

            # ======================================================
            # ✅ 2) Calcular INCAPACIDAD
            # ======================================================
            incapacidad = self.env['hr.attendance'].search([
                ('employee_id', '=', empleado.id),
                ('check_in', '>=', fecha_inicio),
                ('check_out', '<=', fecha_fin),
                ('tipo_asistencia', '=', 'INCAPACIDAD'),
                ('se_paga', '=', True),
            ])

            horas_incap_total = 0.0
            for att in incapacidad:
                if att.check_in and att.check_out:
                    ci = att.check_in.astimezone(tz_local)
                    co = att.check_out.astimezone(tz_local)
                    diff = (co - ci).total_seconds() / 3600.0

                    cruza_almuerzo = (ci.time() < almuerzo_fin and co.time() > almuerzo_inicio)
                    if diff >= 5.0 and cruza_almuerzo:
                        diff -= duracion_almuerzo

                    horas_incap_total += round(diff, 2)

            dias_incapacidad = horas_incap_total / 8.0
            # Máx 3 días pagados por empresa
            dias_pagados = min(dias_incapacidad, 3.0)
            horas_pagadas = dias_pagados * 8.0

            # El resto es sin pago
            dias_sin_pago = max(dias_incapacidad - 3.0, 0.0)
            horas_sin_pago = dias_sin_pago * 8.0

            _logger.info("[%s] Incapacidad %.2f días -> %.2f pagados, %.2f sin pago",
                         empleado.name, dias_incapacidad, dias_pagados, dias_sin_pago)

            # ======================================================
            # ✅ 3) Crear línea única WORK100 (asistencia + permiso con goce) sin incapacidad pagada
            # ======================================================
            if horas_asistencia > 0:
                tipo_work_entry = self.env['hr.work.entry.type'].search([('code', '=', 'WORK100')], limit=1)
                if not tipo_work_entry:
                    tipo_work_entry = self.env['hr.work.entry.type'].create({
                        'name': 'Asistencia',
                        'code': 'WORK100',
                        'sequence': 10,
                        'is_leave': False,
                        'is_unforeseen': False,
                    })

                self.env['hr.payslip.worked_days'].create({
                    'name': 'Asistencia',
                    'code': 'WORK100',
                    'number_of_days': round(horas_asistencia / 8.0, 2),
                    'number_of_hours': horas_asistencia,
                    'contract_id': contract.id,
                    'payslip_id': payslip.id,
                    'work_entry_type_id': tipo_work_entry.id,
                    'amount': float_round(horas_asistencia * salario_por_hora, 2),
                })
                _logger.info("[%s] WORK100: %.2f h asistencia -> %.2f",
                             empleado.name, horas_asistencia, horas_asistencia * salario_por_hora)

            # ======================================================
            # ✅ 4) Crear línea única INCAPACIDAD PAGADA (máx 3 días)
            # ======================================================
            if horas_pagadas > 0:
                tipo_incap_pagada = self.env['hr.work.entry.type'].search([('code', '=', 'INCAPACIDAD_PAGADA')],
                                                                          limit=1)
                if not tipo_incap_pagada:
                    tipo_incap_pagada = self.env['hr.work.entry.type'].create({
                        'name': 'Incapacidad pagada por empresa',
                        'code': 'INCAPACIDAD_PAGADA',
                        'sequence': 20,
                        'is_leave': True,
                        'is_unforeseen': False,
                    })

                self.env['hr.payslip.worked_days'].create({
                    'name': 'Incapacidad pagada por empresa (máx 3 días)',
                    'code': 'INCAPACIDAD_PAGADA',
                    'number_of_days': round(horas_pagadas / 8.0, 2),
                    'number_of_hours': horas_pagadas,
                    'contract_id': contract.id,
                    'payslip_id': payslip.id,
                    'work_entry_type_id': tipo_incap_pagada.id,
                    'amount': float_round(horas_pagadas * salario_por_hora, 2),
                })
                _logger.info("[%s] INCAPACIDAD_PAGADA: %.2f h -> %.2f",
                             empleado.name, horas_pagadas, horas_pagadas * salario_por_hora)

            # ======================================================
            # ✅ 5) Crear línea incapacidad SIN PAGO (si hay más de 3 días)
            # ======================================================
            if horas_sin_pago > 0:
                tipo_incap_sp = self.env['hr.work.entry.type'].search([('code', '=', 'INCAPACIDAD_SIN_PAGO')], limit=1)
                if not tipo_incap_sp:
                    tipo_incap_sp = self.env['hr.work.entry.type'].create({
                        'name': 'Incapacidad sin pago',
                        'code': 'INCAPACIDAD_SIN_PAGO',
                        'sequence': 31,
                        'is_leave': True,
                        'is_unforeseen': True,
                    })

                self.env['hr.payslip.worked_days'].create({
                    'name': 'Incapacidad sin pago',
                    'code': 'INCAPACIDAD_SIN_PAGO',
                    'number_of_days': dias_sin_pago,
                    'number_of_hours': horas_sin_pago,
                    'contract_id': contract.id,
                    'payslip_id': payslip.id,
                    'work_entry_type_id': tipo_incap_sp.id,
                    'amount': 0.0,  # nunca suma
                })
                _logger.info("[%s] INCAPACIDAD sin pago: %.2f h -> $0", empleado.name, horas_sin_pago)

        _logger.info(">>> Fin del cálculo de WORK100 + incapacidad pagada y sin pago")


    def _agregar_inputs_sabado_y_domingos(self):
        """
        Crea entradas automáticas para sábados (4h) y domingos (8h) según el periodo de la nómina.
        Elimina entradas anteriores para evitar duplicados.
        """
        _logger.info(">>> Generando inputs SAB_TARDE y DOMINGO")

        input_type_model = self.env['hr.payslip.input.type']
        tipo_sab = input_type_model.search([('code', '=', 'SAB_TARDE')], limit=1)
        tipo_dom = input_type_model.search([('code', '=', 'DOMINGO')], limit=1)

        if not tipo_sab or not tipo_dom:
            _logger.warning("No se encontraron tipos de entrada para SAB_TARDE o DOMINGO")
            return

        for payslip in self:
            contrato = payslip.contract_id
            if not contrato:
                continue

            # 🔴 Eliminar entradas previas para evitar duplicación
            payslip.input_line_ids.filtered(lambda l: l.code in ['SAB_TARDE', 'DOMINGO']).unlink()

            # Calcular salario por hora
            salario_mensual = (contrato.wage * 2) or 0.0
            salario_por_hora = salario_mensual / 30.0 / 8.0

            fecha_actual = payslip.date_from
            fecha_fin = payslip.date_to

            total_domingos = 0
            total_sabados = 0

            while fecha_actual <= fecha_fin:
                dia_semana = fecha_actual.weekday()
                if dia_semana == 6:
                    total_domingos += 1
                elif dia_semana == 5:
                    total_sabados += 1
                fecha_actual += timedelta(days=1)

            monto_dom = float_round(total_domingos * 8.0 * salario_por_hora, 2)
            monto_sab = float_round(total_sabados * 4.0 * salario_por_hora, 2)

            if monto_dom > 0:
                payslip.input_line_ids.create({
                    'name': 'Domingo',
                    'code': 'DOMINGO',
                    'amount': monto_dom,
                    'payslip_id': payslip.id,
                    'input_type_id': tipo_dom.id,
                })

            if monto_sab > 0:
                payslip.input_line_ids.create({
                    'name': 'Sábado tarde',
                    'code': 'SAB_TARDE',
                    'amount': monto_sab,
                    'payslip_id': payslip.id,
                    'input_type_id': tipo_sab.id,
                })

            _logger.info("[%s] Domingos: %d ($%.2f) | Sábados: %d ($%.2f)",
                         payslip.employee_id.name, total_domingos, monto_dom,
                         total_sabados, monto_sab)


    # ==========FALTAS INJUSTIFICADAS
    def _aplicar_descuento_septimo_por_faltas(self):
        """
        Si hay al menos 1 entrada de trabajo con código FALTA en una semana ISO,
        se pierde el séptimo (domingo) de esa semana.
        """
        _logger.info(">>> Evaluando descuento de séptimo por faltas injustificadas")

        for slip in self:
            contract = slip.contract_id
            if not contract:
                _logger.warning("Nómina %s sin contrato. Se omite cálculo de séptimo.", slip.name)
                continue

            salario_diario = (contract.wage * 2) / 30.0  # quincenal → mensual → diario
            _logger.info("[%s] Salario diario calculado: %.2f", slip.employee_id.name, salario_diario)

            # Buscar solo las FALTAS injustificadas en el periodo de la nómina
            faltas_entries = self.env['hr.work.entry'].search([
                ('employee_id', '=', slip.employee_id.id),
                ('date_start', '>=', slip.date_from),
                ('date_stop', '<=', slip.date_to),
                ('work_entry_type_id.code', '=', 'FALTA')
            ])

            if not faltas_entries:
                _logger.info("[%s] No hay FALTAS → no se descuenta séptimo", slip.employee_id.name)
                continue

            # Agrupar las semanas ISO en las que hubo al menos una falta
            semanas_con_falta = set()
            for entry in faltas_entries:
                fecha_falta = fields.Date.to_date(entry.date_start)
                semana_iso = fecha_falta.isocalendar()[1]
                semanas_con_falta.add(semana_iso)

            total_semanas_afectadas = len(semanas_con_falta)
            _logger.info("[%s] Semanas con faltas injustificadas: %d", slip.employee_id.name, total_semanas_afectadas)

            if total_semanas_afectadas == 0:
                continue

            # Por cada semana con falta → se pierde 1 domingo
            dias_perdidos = total_semanas_afectadas
            monto_descuento = salario_diario * dias_perdidos

            _logger.info("[%s] Pierde %d domingos → descuento %.2f",
                         slip.employee_id.name, dias_perdidos, monto_descuento)

            # Buscar el tipo de entrada YA creado en XML
            tipo_input = self.env['hr.payslip.input.type'].search([('code', '=', 'DESC_FALTA_SEPTIMO')], limit=1)
            if not tipo_input:
                _logger.warning("[%s] Tipo de entrada DESC_FALTA_SEPTIMO no existe en BD → revisar XML",
                                slip.employee_id.name)
                continue  # No creamos nada, el XML debe existir

            # Buscar o crear el input en la nómina
            input_line = slip.input_line_ids.filtered(lambda inp: inp.code == 'DESC_FALTA_SEPTIMO')
            if input_line:
                input_line.amount = -abs(monto_descuento)
                _logger.info("[%s] Actualizado input DESC_FALTA_SEPTIMO con %.2f", slip.employee_id.name,
                             monto_descuento)
            else:
                self.env['hr.payslip.input'].create({
                    'name': 'Descuento séptimo (faltas injustificadas)',
                    'code': 'DESC_FALTA_SEPTIMO',
                    'amount': -abs(monto_descuento),
                    'payslip_id': slip.id,
                    'input_type_id': tipo_input.id,
                })
                _logger.info("[%s] Creado input DESC_FALTA_SEPTIMO con %.2f", slip.employee_id.name, monto_descuento)


    # ==========VACACIONES
    def calcular_vacaciones(self, salario_mensual, meses_trabajados):
        """
        Calcula el pago de vacaciones en El Salvador.

        - salario_mensual: sueldo mensual del empleado
        - meses_trabajados: número de meses trabajados

        Retorna dict con:
          dias_vacaciones, pago_base, extra_30, total, motivo_pago
        """
        # Salario diario (30 días según ley)
        salario_diario = salario_mensual / 30.0

        # Si trabajó >= 12 meses tiene derecho completo
        if meses_trabajados >= 12:
            dias_vacaciones = 15
            motivo_pago = "Vacaciones anuales"
        else:
            dias_vacaciones = (meses_trabajados / 12.0) * 15
            motivo_pago = "Vacaciones proporcionales"

        # Calcular montos
        pago_base = salario_diario * dias_vacaciones
        extra_30 = pago_base * 0.30
        total = pago_base + extra_30

        _logger.info(
            f"Vacaciones calculadas: {dias_vacaciones:.2f} días, "
            f"base={pago_base:.2f}, extra_30={extra_30:.2f}, total={total:.2f}"
        )

        return {
            "dias_vacaciones": round(dias_vacaciones, 2),
            "pago_base": round(pago_base, 2),
            "extra_30": round(extra_30, 2),
            "total": round(total, 2),
            "motivo_pago": motivo_pago
        }


    def _agregar_regla_vacaciones(self, slip):
        contract = slip.contract_id
        if not contract:
            return

        salario_mensual = (contract.wage * 2) or 0.0

        # Calcular meses trabajados
        meses_trabajados = 0
        if contract.date_start:
            diff_days = (fields.Date.today() - contract.date_start).days
            meses_trabajados = diff_days / 30.0

        # Calcular vacaciones según ley
        datos_vac = self.calcular_vacaciones(salario_mensual, meses_trabajados)

        # ✅ Solo creamos input si hay extra_30
        if datos_vac["extra_30"] > 0:
            # Buscar el tipo de otras entradas VACACIONES
            tipo_vacaciones = self.env['hr.payslip.input.type'].search([('code', '=', 'VACACIONES')], limit=1)
            if not tipo_vacaciones:
                _logger.error("⚠ No existe tipo de entrada VACACIONES en Otras Entradas")
                return

            # Buscar si ya existe input VACACIONES en este slip
            input_existente = slip.input_line_ids.filtered(lambda i: i.code == 'VACACIONES')

            if input_existente:
                input_existente.write({
                    'amount': float_round(datos_vac["extra_30"], precision_digits=2),
                })
                _logger.info(f"♻ Actualizado input VACACIONES → {datos_vac['extra_30']}")
            else:
                slip.input_line_ids.create({
                    'name': f"Vacaciones ({datos_vac['dias_vacaciones']} días)",
                    'code': 'VACACIONES',
                    'amount': float_round(datos_vac["extra_30"], precision_digits=2),
                    'payslip_id': slip.id,
                    'input_type_id': tipo_vacaciones.id,
                })
                _logger.info(
                    f"✅ Creado input VACACIONES en {slip.name} → días={datos_vac['dias_vacaciones']} extra={datos_vac['extra_30']}"
                )

    # def _copiar_deducciones_desde_principal(self):
    #     self.ensure_one()
    #     if not self.payslip_principal_id:
    #         return
    #
    #     deducciones_principal = self.payslip_principal_id.line_ids.filtered(
    #         lambda l: l.category_id.code == 'DED'
    #     )
    #
    #     for ded in deducciones_principal:
    #         linea_existente = self.line_ids.filtered(lambda l: l.code == ded.code)
    #         if linea_existente:
    #             linea_existente.write({
    #                 'amount': ded.amount,
    #                 'total': ded.total,
    #             })
    #         else:
    #             self.env['hr.payslip.line'].create({
    #                 'slip_id': self.id,
    #                 'code': ded.code,
    #                 'name': ded.name,
    #                 'category_id': ded.category_id.id,
    #                 'amount': ded.amount,
    #                 'total': ded.total,
    #             })

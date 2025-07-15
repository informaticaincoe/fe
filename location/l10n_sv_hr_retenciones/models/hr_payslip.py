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
    #'ASISTENCIA': 'WORK100',
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
            contract = payslip.contract_id  # Se obtiene el contrato asociado a la nómina

            # Eliminar entradas previas (inputs) para evitar duplicados en el cálculo
            for code in ['RENTA', 'AFP', 'ISSS', 'ISSS_EMP', 'AFP_EMP', 'INCAF']:
                # Filtra las líneas de input existentes con los códigos específicos
                old_inputs = payslip.input_line_ids.filtered(lambda l: l.code == code)
                if old_inputs:
                    # Si se encuentran entradas previas, se eliminan para evitar duplicados
                    _logger.info("Eliminando inputs previos código %s para nómina %d", code, payslip.id)
                    old_inputs.unlink()

            try:
                # Llama a los métodos del contrato para calcular las deducciones
                renta = contract.calcular_deduccion_renta()
                afp = contract.calcular_afp()
                isss = contract.calcular_isss()
                afp_patronal = contract.calcular_aporte_patronal('afp')
                isss_patronal = contract.calcular_aporte_patronal('isss')
                incaf = contract.calcular_incaf()
            except Exception as e:
                _logger.error("Error al calcular deducciones para nómina %d: %s", payslip.id, e)
                renta = afp = isss = afp_patronal = isss_patronal = incaf = 0.0

                # Mostrar error al usuario en pantalla
                raise UserError(
                    _("Ocurrió un error al calcular las deducciones para la nómina '%s':\n%s") % (payslip.name, str(e)))

            # Busca los tipos de inputs en Odoo usando el código correspondiente (RENTA, AFP, ISSS)
            tipos = {
                code: self.env['hr.payslip.input.type'].search([('code', '=', code)], limit=1)
                for code in ['RENTA', 'AFP', 'ISSS', 'ISSS_EMP', 'AFP_EMP', 'INCAF']
            }

            _logger.info("Tipos de entradas: %s", tipos)

            # Si no se encuentra el tipo de input, lanzamos un error
            for code, tipo in tipos.items():
                if not tipo:
                    raise UserError(
                        _("No se encontró el tipo de input para %s. Por favor, asegúrese de que los tipos de deducción estén configurados correctamente.",
                          code))

            # Verificar si el contrato es de servicios profesionales
            is_professional = contract.wage_type == constants.SERVICIOS_PROFESIONALES
            _logger.info("Contrato tipo '%s'. ¿Es servicios profesionales? %s", contract.wage_type, is_professional)

            valores = []

            # Definir los valores a ser añadidos como inputs a la nómina (con signo negativo, ya que son deducciones)
            if is_professional:
                valores.append(('RENTA', -abs(renta)))
                _logger.info("Contrato de servicios profesionales: solo se agregará RENTA")
            else:
                valores = [
                    ('RENTA', -abs(renta)),
                    ('AFP', -abs(afp)),
                    ('ISSS', -abs(isss)),
                    ('ISSS_EMP', abs(isss_patronal)),
                    ('AFP_EMP', abs(afp_patronal)),
                    ('INCAF', -abs(incaf)),
                ]
                _logger.error("Valores: %s", valores)

            # Crear nuevas entradas para cada tipo de deducción
            for code, valor in valores:
                tipo = tipos.get(code)
                if tipo:
                    # Si el tipo de input es válido, se crea una nueva línea de input para la nómina
                    payslip.input_line_ids.create({
                        'name': tipo.name,  # Nombre del tipo de deducción
                        'code': code,  # Código de la deducción (RENTA, AFP, ISSS)
                        'amount': float_round(valor, precision_digits=2),  # Monto de la deducción (valor negativo)
                        'payslip_id': payslip.id,  # ID de la nómina
                        'input_type_id': tipo.id,  # ID del tipo de input en el sistema
                    })
                    # Registra en el log la adición de un input para la nómina
                    _logger.info("Input %s agregado a nómina %d con monto %.2f", code, payslip.id, valor)
        _logger.info("Inputs generados: %s", payslip.input_line_ids.mapped(lambda l: (l.code, l.amount)))

        # ✅ Agregar entradas por asistencias como permisos sin goce, vacaciones, etc.
        #self._generar_worked_days_asistencia()
        # Dentro del método compute_sheet, al final:
        self._agregar_inputs_sabado_y_domingos()
        self._asignar_importe_asistencia()
        # Llama al método original para completar el cálculo de la nómina
        res = super().compute_sheet()
        # Registra el fin del cálculo personalizado de la nómina
        _logger.info(">>> [FIN] compute_sheet personalizado completado")
        return res

    # ==========ASISTENCIAS
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
            _logger.info("SALARIO MENSUAL:%s ",salario_mensual)

            salario_por_hora = salario_mensual / 30.0 / 8.0
            _logger.info("SALARIO HORA:%s ",salario_por_hora)

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

    def _generar_worked_days_asistencia(self):
        """
        Genera líneas de worked_days para:
        - Asistencia normal (WORK100) → solo horas ASISTENCIA
        - Permiso con goce (PERMISO_CG) → horas separadas, línea propia
        - Permiso sin goce (PERMISO_SG) → línea propia, sin pago
        """
        _logger.info(">>> Generando worked_days por asistencia y permisos con/sin goce")

        attendance_obj = self.env['hr.attendance']
        entry_type_model = self.env['hr.work.entry.type']
        tz_local = pytz.timezone('America/El_Salvador')

        for payslip in self:
            employee = payslip.employee_id
            contract = payslip.contract_id

            if not contract or contract.state != 'open':
                _logger.warning("Contrato no válido para %s", employee.name)
                continue

            _logger.info("Procesando nómina %s | Empleado %s | Contrato %s",
                         payslip.name, employee.name, contract.name)

            # Eliminar líneas previas WORK100, PERMISO_CG, PERMISO_SG
            codigos_a_borrar = ['WORK100', 'PERMISO_CG', 'PERMISO_SG']
            lines_to_remove = payslip.worked_days_line_ids.filtered(lambda l: l.code in codigos_a_borrar)
            if lines_to_remove:
                _logger.info("Eliminando líneas previas worked_days: %s", lines_to_remove.mapped('code'))
                lines_to_remove.unlink()

            salario_mensual = contract.wage * 2 or 0.0
            salario_por_hora = salario_mensual / 30.0 / 8.0
            _logger.info("Salario mensual: %.2f, por hora: %.4f", salario_mensual, salario_por_hora)

            # Buscar asistencias en rango fecha
            asistencias = attendance_obj.search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', payslip.date_from),
                ('check_out', '<=', payslip.date_to),
            ])
            _logger.info("Encontradas %d asistencias para %s", len(asistencias), employee.name)

            horas_asistencia = 0.0  # Solo 'ASISTENCIA'
            horas_permiso_cg = 0.0  # 'PERMISO_CG'
            horas_permiso_sg = 0.0  # 'PERMISO_SG'

            for asistencia in asistencias:

                tipo = asistencia.tipo_asistencia or 'N/A'
                if asistencia.check_in and asistencia.check_out:
                    check_in_local = asistencia.check_in.astimezone(tz_local)
                    check_out_local = asistencia.check_out.astimezone(tz_local)
                    horas = (check_out_local - check_in_local).total_seconds() / 3600.0
                else:
                    horas = 0.0

                if tipo == 'ASISTENCIA':
                    horas_asistencia += horas
                elif tipo == 'PERMISO_CG':
                    horas_permiso_cg += horas
                elif tipo == 'PERMISO_SG':
                    horas_permiso_sg += horas
                else:
                    _logger.warning("[%s] Tipo de asistencia no manejado: %s", employee.name, tipo)

            _logger.info("[%s] Horas ASISTENCIA=%.2f | PERMISO_CG=%.2f | PERMISO_SG=%.2f",
                         employee.name, horas_asistencia, horas_permiso_cg, horas_permiso_sg)

            # Crear línea WORK100 solo para horas de ASISTENCIA
            if horas_asistencia > 0:
                tipo_work = entry_type_model.search([('code', '=', 'WORK100')], limit=1)
                payslip.env['hr.payslip.worked_days'].create({
                    'name': 'Asistencia',
                    'code': 'WORK100',
                    'number_of_days': round(horas_asistencia / 8.0, 2),
                    'number_of_hours': round(horas_asistencia, 2),
                    'contract_id': contract.id,
                    'payslip_id': payslip.id,
                    'work_entry_type_id': tipo_work.id if tipo_work else False,
                    'amount': float_round(horas_asistencia * salario_por_hora, 2),
                })
                _logger.info("✅ WORK100 creada con %.2f horas y monto %.2f",
                             horas_asistencia, horas_asistencia * salario_por_hora)

            # Crear línea PERMISO_CG solo para horas permiso con goce
            if horas_permiso_cg > 0:
                tipo_permiso_cg = entry_type_model.search([('code', '=', 'PERMISO_CG')], limit=1)
                if not tipo_permiso_cg:
                    tipo_permiso_cg = entry_type_model.create({
                        'name': 'Permiso con goce',
                        'code': 'PERMISO_CG',
                        'sequence': 26,
                        'is_leave': True,
                        'is_unforeseen': True,
                    })
                payslip.env['hr.payslip.worked_days'].create({
                    'name': 'Permiso con goce',
                    'code': 'PERMISO_CG',
                    'number_of_days': round(horas_permiso_cg / 8.0, 2),
                    'number_of_hours': round(horas_permiso_cg, 2),
                    'contract_id': contract.id,
                    'payslip_id': payslip.id,
                    'work_entry_type_id': tipo_permiso_cg.id,
                    'amount': float_round(horas_permiso_cg * salario_por_hora, 2),
                })
                _logger.info("✅ PERMISO_CG creada con %.2f horas y monto %.2f",
                             horas_permiso_cg, horas_permiso_cg * salario_por_hora)

            # Crear línea PERMISO_SG solo informativa, sin pago
            if horas_permiso_sg > 0:
                tipo_permiso_sg = entry_type_model.search([('code', '=', 'PERMISO_SG')], limit=1)
                if not tipo_permiso_sg:
                    tipo_permiso_sg = entry_type_model.create({
                        'name': 'Permiso sin goce',
                        'code': 'PERMISO_SG',
                        'sequence': 25,
                        'is_leave': True,
                        'is_unforeseen': True,
                    })
                payslip.env['hr.payslip.worked_days'].create({
                    'name': 'Permiso sin goce',
                    'code': 'PERMISO_SG',
                    'number_of_days': round(horas_permiso_sg / 8.0, 2),
                    'number_of_hours': round(horas_permiso_sg, 2),
                    'contract_id': contract.id,
                    'payslip_id': payslip.id,
                    'work_entry_type_id': tipo_permiso_sg.id,
                    'amount': 0.0,
                })
                _logger.info("ℹ️ PERMISO_SG creada con %.2f horas y monto $0.00", horas_permiso_sg)

        _logger.info("<<< Finalizado generación worked_days por asistencia y permisos")

    # def _generar_inputs_asistencia(self):
    #     """
    #     Genera entradas personalizadas en la nómina en base a las asistencias del empleado,
    #     calculando los importes con base en horas efectivas y usando un monto por hora
    #     unificado (salario mensual / 240).
    #     """
    #     attendance_obj = self.env['hr.attendance']
    #     _logger.info(">>> Iniciando generación de inputs por asistencias")
    #
    #     for payslip in self:
    #         # Eliminar inputs de asistencia previos para evitar duplicados
    #         codes_asistencia = list(TIPOS_AUSENCIA.values())
    #         old_inputs = payslip.input_line_ids.filtered(lambda l: l.code in codes_asistencia)
    #         if old_inputs:
    #             _logger.info("Eliminando inputs de asistencia previos: %s", old_inputs.mapped('code'))
    #             old_inputs.unlink()
    #
    #         employee = payslip.employee_id
    #         contract = payslip.contract_id
    #
    #         _logger.info("Procesando nómina: %s | Empleado: %s | Contrato: %s",
    #                      payslip.name, employee.name, contract.display_name if contract else 'N/A')
    #
    #         if not contract or contract.state != 'open' or not contract.wage:
    #             _logger.info("→ Contrato inválido o cerrado para %s. Se omite.", employee.name)
    #             continue
    #
    #         salario_mensual = (contract.wage * 2) or 0.0
    #         monto_por_hora = salario_mensual / 30.0 / 8.0
    #         _logger.info("→ Salario mensual: %.2f | Monto por hora (unificado): %.4f", contract.wage, monto_por_hora)
    #
    #         for tipo_asistencia, input_code in TIPOS_AUSENCIA.items():
    #             asistencias = attendance_obj.search([
    #                 ('employee_id', '=', employee.id),
    #                 ('tipo_asistencia', '=', tipo_asistencia),
    #                 ('check_in', '>=', payslip.date_from),
    #                 ('check_in', '<=', payslip.date_to),
    #             ])
    #
    #             if not asistencias:
    #                 continue
    #
    #             # Calcular horas no pagadas
    #             horas_no_pagadas = 0.0
    #             for a in asistencias:
    #                 if not a.se_paga and a.check_in and a.check_out:
    #                     horas_no_pagadas = 8.0  # si es solo para permisos sin goce
    #                     #horas_no_pagadas += (a.check_out - a.check_in).total_seconds() / 3600.0
    #
    #             monto = 0.0
    #
    #             if tipo_asistencia == 'PERMISO_SG':
    #                 monto = -horas_no_pagadas * monto_por_hora
    #                 _logger.info("→ PERMISO_SG | Horas no pagadas: %.2f | Monto: %.2f", horas_no_pagadas, monto)
    #
    #                 if horas_no_pagadas > 0:
    #                     # Eliminar cualquier línea previa PERMISO_SG
    #                     payslip.worked_days_line_ids.filtered(lambda w: w.code == 'PERMISO_SG').unlink()
    #
    #                     # Buscar el tipo de entrada de trabajo (work entry type)
    #                     entry_type = self.env['hr.work.entry.type'].search([('code', '=', 'PERMISO_SG')], limit=1)
    #                     if not entry_type:
    #                         raise UserError(_("No se encontró el tipo de entrada de trabajo para PERMISO_SG"))
    #
    #                     # Crear la línea de días trabajados manualmente
    #                     self.env['hr.payslip.worked_days'].create({
    #                         'name': 'Permiso sin goce',
    #                         'code': 'PERMISO_SG',
    #                         'number_of_days': horas_no_pagadas / 8.0,
    #                         'number_of_hours': horas_no_pagadas,
    #                         'contract_id': contract.id,
    #                         'payslip_id': payslip.id,
    #                         'work_entry_type_id': entry_type.id,
    #                     })
    #
    #             elif tipo_asistencia == 'VACACIONES':
    #                 monto = -horas_no_pagadas * monto_por_hora * 0.30
    #                 _logger.info("→ VACACIONES | Horas no pagadas: %.2f | Monto: %.2f", horas_no_pagadas, monto)
    #
    #             elif tipo_asistencia == 'INCAPACIDAD':
    #                 monto = -horas_no_pagadas * monto_por_hora
    #                 _logger.info("→ INCAPACIDAD | Horas no pagadas: %.2f | Monto: %.2f", horas_no_pagadas, monto)
    #
    #             elif tipo_asistencia == 'FALTA_INJ':
    #                 monto = -horas_no_pagadas * monto_por_hora
    #                 incluye_domingo = any(a.check_in.weekday() == 6 for a in asistencias if not a.se_paga)
    #                 if incluye_domingo:
    #                     monto += -1 * (8 * monto_por_hora)
    #                     _logger.info("→ Incluye domingo. Se agrega descuento adicional.")
    #                 _logger.info("→ FALTA_INJ | Horas no pagadas: %.2f | Monto: %.2f", horas_no_pagadas, monto)
    #
    #             elif tipo_asistencia == 'MATERNIDAD':
    #                 monto = -horas_no_pagadas * monto_por_hora
    #                 _logger.info("→ MATERNIDAD | Horas no pagadas: %.2f | Monto: %.2f", horas_no_pagadas, monto)
    #
    #             elif tipo_asistencia in ['PATERNIDAD', 'MATRIMONIO', 'DISCIPLINARIA']:
    #                 _logger.info("→ Tipo %s no genera input automático.", tipo_asistencia)
    #                 continue
    #
    #             if monto != 0.0:
    #                 tipo_input = self.env['hr.payslip.input.type'].search([('code', '=', input_code)], limit=1)
    #                 if not tipo_input:
    #                     _logger.error("‼ No se encontró tipo de input para código: %s", input_code)
    #                     raise UserError(_("No se encontró tipo input para: %s") % input_code)
    #
    #                 payslip.input_line_ids.create({
    #                     'name': tipo_input.name,
    #                     'code': input_code,
    #                     'amount': float_round(monto, 2),
    #                     'payslip_id': payslip.id,
    #                     'input_type_id': tipo_input.id,
    #                 })
    #
    #                 _logger.info("→ Input generado | Empleado: %s | Tipo: %s | Monto: %.2f",
    #                              employee.name, tipo_asistencia, monto)
    #
    #     _logger.info("<<< Finalizada generación de inputs por asistencias")

    # def _calcular_y_generar_inputs_y_worked_days(self):
    #     for payslip in self:
    #         contract = payslip.contract_id
    #         employee = payslip.employee_id
    #
    #         if not contract or contract.state != 'open' or not contract.wage:
    #             _logger.info("Contrato inválido o cerrado para %s. Se omite cálculo.", employee.name)
    #             continue
    #
    #         # Aquí eliminamos inputs previos (como en tu compute_sheet)
    #         codes_to_remove = ['RENTA', 'AFP', 'ISSS', 'ISSS_EMP', 'AFP_EMP', 'INCAF'] + list(TIPOS_AUSENCIA.values())
    #         old_inputs = payslip.input_line_ids.filtered(lambda l: l.code in codes_to_remove)
    #         if old_inputs:
    #             old_inputs.unlink()
    #
    #         # Limpiar líneas worked_days previas
    #         if payslip.worked_days_line_ids:
    #             payslip.worked_days_line_ids.unlink()
    #
    #         # Generar inputs por ausencias (permiso sin goce, vacaciones, etc)
    #         payslip._generar_inputs_asistencia()
    #
    #         # Y generas líneas worked_days con los contratos vigentes y fechas
    #         contracts = [contract] if contract else employee.contract_ids.filtered(lambda c: c.state == 'open')
    #         worked_lines = payslip._get_worked_day_lines(contracts=contracts, date_from=payslip.date_from,
    #                                                      date_to=payslip.date_to)
    #
    #         for vals in worked_lines:
    #             vals.update({'payslip_id': payslip.id})
    #             self.env['hr.payslip.worked_days'].create(vals)
    #
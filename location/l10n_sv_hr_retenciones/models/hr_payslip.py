from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
from odoo.tools import float_round

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants

    _logger.info("SIT Modulo config_utils")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    constants = None

TIPOS_AUSENCIA = {
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

        # Dentro del método compute_sheet, al final:
        self._asignar_importe_asistencia()
        # Llama al método original para completar el cálculo de la nómina
        res = super().compute_sheet()
        # Registra el fin del cálculo personalizado de la nómina
        _logger.info(">>> [FIN] compute_sheet personalizado completado")
        return res

    # ==========ASISTENCIAS
    def _asignar_importe_asistencia(self):
        """
        Asigna el importe proporcional en la línea de worked_days con código 'WORK100',
        calculando en base al salario quincenal y 88 horas como jornada completa.
        """
        _logger.info(">>> Iniciando cálculo de importe por asistencia (WORK100) en %d nóminas", len(self))

        for payslip in self:
            contract = payslip.contract_id
            if not contract:
                _logger.warning("Nómina %s sin contrato. Se omite.", payslip.name)
                continue

            for worked_day in payslip.worked_days_line_ids:
                _logger.debug("Evaluando línea worked_day: Código=%s, Horas=%.2f, Días=%.2f",
                              worked_day.code, worked_day.number_of_hours, worked_day.number_of_days)

                if worked_day.code == 'WORK100':
                    salario_mensual = contract.wage or 0.0
                    horas_trabajadas = worked_day.number_of_hours or 0.0

                    salario_por_hora = salario_mensual / 30.0 / 8.0
                    importe = float_round(horas_trabajadas * salario_por_hora, precision_digits=2)
                    worked_day.amount = importe

                    _logger.info(
                        "Empleado: %s | Salario mensual: $%.2f | Valor/hora: $%.4f | Horas: %.2f | Importe: $%.2f",
                        payslip.employee_id.name,
                        salario_mensual,
                        salario_por_hora,
                        horas_trabajadas,
                        importe
                    )

        _logger.info(">>> Fin del cálculo de asistencia.")

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
    #         monto_por_hora = round(contract.wage / 240.0, 4)
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
    #                     horas_no_pagadas += (a.check_out - a.check_in).total_seconds() / 3600.0
    #
    #             monto = 0.0
    #
    #             if tipo_asistencia == 'PERMISO_SG':
    #                 monto = -horas_no_pagadas * monto_por_hora
    #                 _logger.info("→ PERMISO_SG | Horas no pagadas: %.2f | Monto: %.2f", horas_no_pagadas, monto)
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
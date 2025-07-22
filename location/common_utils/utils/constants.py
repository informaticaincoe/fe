TRANSMISION_NORMAL = 1
TRANSMISION_CONTINGENCIA = 2
TIPO_CONTIN_OTRO = 5
COD_DTE_FE = "01"
COD_DTE_CCF = "03"
COD_DTE_NC = "05"
COD_DTE_ND = "06"
COD_DTE_FEX = "11"
COD_DTE_FSE = "14"
COD_TIPO_DOCU_DUI = "13"
COD_TIPO_ITEM = "4"
COD_TIPO_DOC_GENERACION_DTE = 2
TIPO_VENTA_PROD_GRAV = "gravado"
TIPO_VENTA_PROD_EXENTO = "exento"
TIPO_VENTA_PROD_NO_SUJETO = "no_sujeto"
AMBIENTE_TEST = "00"

#Modulo de retenciones
DEDUCCION_EMPLEADO = "empleado"
RET_MENSUAL = "a"
RET_QUINCENAL = "b"
RET_SEMANAL = "c"
TIPO_DED_ISSS = "isss"
TIPO_DED_AFP = "afp"
DEDUCCION_EMPLEADOR = "patron"
DEDUCCION_INCAF = "incaf"
SERVICIOS_PROFESIONALES = "professional_services"

#Modulo de asignaciones salariales
ASIGNACION_COMISIONES = "comision"
ASIGNACION_VIATICOS = "viatico"
ASIGNACION_BONOS = "bono"
ASIGNACION_HORAS_EXTRA = "overtime"
HORAS_DIURNAS = "horas_diurnas"
HORAS_NOCTURNAS = "horas_nocturnas"
HORAS_DIURNAS_DESCANSO = "horas_diurnas_descanso"
HORAS_NOCTURNAS_DESCANSO = "horas_nocturnas_descanso"
HORAS_DIURNAS_ASUETO = "horas_diurnas_asueto"
HORAS_NOCTURNAS_ASUETO = "horas_nocturnas_asueto"
PERIODO = "periodo"
NOMBRE_PLANTILLA_ASIGNACIONES = "Plantilla de Asignaciones"
NOMBRE_PLANTILLA_ASISTENCIA = "Plantilla de Asistencia"

CUENTAS_ASIGNACIONES = {
    'cuenta_salarial_deducciones_credito': 'cuenta_salarial_deducciones',
    'cuenta_salarial_deducciones_debito': 'cuenta_salarial_debito',
}
CODIGOS_REGLAS_ASIGNACIONES = ['COMISION', 'VIATICO', 'BONO', 'OVERTIME']

# Conversión de schedule_pay → factor para convertir a salario mensual
SCHEDULE_PAY_CONVERSION = {
    'monthly': 1,
    'semi-monthly': 2,        # quincenal
    'bi-weekly': 52 / 12 / 2,   # 26 pagos/año → mensual ≈ 2.1666
    'weekly': 52 / 12,          # 4.3333 semanas por mes
    'daily': 30,              # 30 días promedio en un mes
    'bimonthly': 0.5,           # cada 2 meses
    'quarterly': 1 / 3,
    'semi-annually': 1 / 6,
    'annually': 1 / 12,
}



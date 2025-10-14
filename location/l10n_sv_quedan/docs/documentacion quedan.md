# l10n_sv_quedan — Quedán de Proveedor (Odoo 18)

**Quedán**: documento interno de **promesa/compromiso de pago** a proveedor que agrupa facturas, fija una **fecha programada** y permite emitir un **PDF** y enviarlo por correo.



## Funcionalidad

- Crear y gestionar Quedanes.
- Agregar **hasta 5** facturas de proveedor por Quedán.
- Estados del ciclo de vida:  
  - **Borrador** (`draft`)  
  - **Confirmado** (`confirmed`)  
  - **Vencido** (`overdue`) → si no todas las facturas están pagadas y ya pasó la fecha programada.  
  - **Pagado** (`paid`) → cuando todas las facturas del Quedán están pagadas.
- **Pagos relacionados**: se detectan por **conciliación** de apuntes contables; no se hereda ni acopla `account.payment`.
- Generación de **PDF** (QWeb) y **envío por correo** con plantilla.
- Soporte de **moneda** (`currency_id` y `widget="monetary"` en vistas).



## Requisitos

- Odoo **18.0**
- Módulos: `account`, `mail`
- Secuencia `account.quedan` (incluida en `data/account_quedan_sequence.xml`)

> En Odoo 18 las vistas usan expresiones en atributos (`invisible`, `readonly`, `required`).  
> `attrs`/`states` no se usan desde Odoo 17+.



## Estructura del módulo

![Quedán – vista formulario](l10n_sv_quedan/static/description/screenshot.png)


### Qué hace cada archivo

- **`model/account_quedan.py`**  
  Modelo `account.quedan`:
  - Campos: `name`, `company_id`, `currency_id`, `partner_id`, `fecha_programada`, `observaciones`, `factura_ids`, `state`, `monto_total`, `payments_ids`.
  - Compute:
    - `monto_total`: suma de `amount_total` de `factura_ids` (con `currency_field="currency_id"`).
    - `payments_ids`: pagos derivados de **conciliaciones** (no hay `quedan_id` en `account.payment`).
  - Acciones: `action_confirm`, `action_paid`, `action_reset`, `download_quedan`, `action_send_email`.
  - Sincronización de estado: `_check_facturas_pagadas()` (incluye **Vencido**).
  - Validaciones:
    - `@api.constrains('factura_ids')`: **máximo 5** facturas.
    - `@api.onchange('factura_ids')`: recorta visualmente al top-5 y muestra *warning*.
  - UX: Hook `read()` recalcula estado al abrir.

- **`views/account_quedan_views.xml`**  
  - **Tree**: columnas clave, `monto_total` con `widget="monetary"`, `state` (puede usarse widget propio `state_badge`).
  - **Form**: botones con `invisible` según estado; statusbar `draft,confirmed,overdue,paid`; `factura_ids` editable solo en `draft`.
  - **Action + Menu**: `view_mode="tree,form"` bajo **Cuentas por pagar**.

- **`report/report_quedan_documento.xml`**  
  `report.paperformat` A4, `ir.actions.report` (QWeb PDF) y plantilla con encabezado, datos del Quedán, tabla de facturas y total (`format_amount`).

- **`data/account_quedan_sequence.xml`**  
  Secuencia técnica `account.quedan` usada por `name`.

- **`data/mail_template_quedan.xml`**  
  Plantilla de correo para enviar el PDF generado (usada por `action_send_email`).

- **`security/ir.model.access.csv`**  
  Permisos de lectura/escritura/creación/borrado para grupos (ajusta a tus grupos de contabilidad).



## Estados y transiciones

| Estado     | Cuándo aplica                                                                   |
|------------|----------------------------------------------------------------------------------|
| Borrador   | Sin facturas o antes de confirmar                                               |
| Confirmado | Tiene facturas, **no** todas pagadas y la fecha programada **no** ha vencido    |
| Vencido    | Tiene facturas, **no** todas pagadas y `fecha_programada` **< hoy**             |
| Pagado     | **Todas** las facturas con `payment_state == 'paid'`                            |

> El cálculo usa `fields.Date.context_today(self)` para respetar zona horaria/compañía.



## Validaciones claves

- **Máximo 5 facturas** por Quedán (constrains en servidor + warning en onchange).
- **Confirmación**:
  - Requiere al menos **1** factura.
  - Rechaza si alguna factura ya está `paid`.



## Instalación

1. Copiar el módulo a la carpeta de addons.
2. Verificar dependencias (`account`, `mail`).
3. Actualizar módulo:
   ```bash
   odoo -d <db> -u l10n_sv_quedan

from odoo import api, fields, models


class SettlementTaxConfig(models.Model):
    _name = "settlement.tax.config"

    name = fields.Char(compute='_compute_name', string='Nombre')
    external_bank_config_id = fields.Many2one(
        'external.bank.config',
        string='Configuración del Banco Externo'
    )
    field_type = fields.Selection([
        ('txt', '.txt'), ('csv', '.csv'), ('xls', '.xls'), ('xlsx', '.xlsx')
    ], string='Tipo de Archivo')

    # 1: TXT NORMAL
    # 2: COINCIDENCIA EXACTA
    # 3: ENCONTRAR FILA POR NOMBRE DEL IMPUESTO Y UTILIZAR LAS COLUMNAS SIGUIENTES
    # 4: SUMA DE CAPOS EN BASE AL LIQUIDATION NUMBER
    search_type = fields.Selection([
        ('txt_sw', '.txt Caracter de comienzo de linea'), ('excel_rc', 'Excel, coincidencia exacta (fila, columna)'),
        ('excel_tax_name', 'Excel, nombre del impuesto'), ('sum_col_row', 'Excel, Suma de filas de una columna en base liquidación en tipo date u otro')
    ], string='Tipo de búsqueda')

    field_config_ids = fields.One2many(
        'settlement.tax',
        'settlement_tax_config_id',
        string='Campos de Configuración',
    )

    @api.depends('external_bank_config_id', 'field_type')
    def _compute_name(self):
        for record in self:
            record.name = f'{record.external_bank_config_id.name}-{record.field_type}'

from odoo import api, fields, models


class SettlementTaxLine(models.Model):
    _name = "settlement.tax.line"
    _rec_name = "display_name"

    display_name = fields.Char(compute='_compute_display_name', string='Nombre', store=True)
    settlement_tax_id = fields.Many2one(
        'settlement.tax', string='Impuesto', ondelete="cascade"
    )

    # Campos para txt
    starting_position = fields.Integer(string='Posición inicial en extracto (.txt)')
    long = fields.Integer(string='Longitud en el extracto (.txt)')
    decimals_amount = fields.Integer(string='Cantidad de decimales (.txt)')

    # Capos para excel
    row = fields.Integer(string='Fila')
    col = fields.Integer(string='Columna')
    tax_name = fields.Char(string='Nombre del Impuesto')
    positions_amount = fields.Integer(string='Cantidad de posiciones')
    direction = fields.Selection([
        ('up', 'Arriba'), ('down', 'Abajo'), ('left', 'Izquierda'), ('right', 'Derecha')
    ], string='Dirección de las posiciones')


    _sql_constraints = [
        (
            'starting_position_greater_than_0',
            'CHECK(starting_position > 0)',
            'La posición inicial debe ser mayor a 0.'
        ),
        (
            'long_positive',
            'CHECK(long > 0)',
            'La longitud debe ser mayor a 0.'
        ),
        (
            'decimals_amount_non_negative',
            'CHECK(decimals_amount >= 0)',
            'La cantidad de decimales debe ser mayor o igual a 0.'
        ),
    ]

    @api.depends('starting_position', 'long', 'decimals_amount')
    def _compute_display_name(self):
        for record in self:
            record.display_name = (f'Linea: 8 - Inicio: {record.starting_position} '
                                   f'- Longitud: {record.long} - Decimales: {record.decimals_amount}')
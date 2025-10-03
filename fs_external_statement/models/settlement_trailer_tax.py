from odoo import api, fields, models
from odoo.exceptions import ValidationError

class SettlementTrailer(models.Model):
    _name = "settlement.trailer.tax"

    # Campos base
    name = fields.Html(
        string='Nombre',
        compute='_compute_name',
        store=True
    )
    total = fields.Float(
        string='Monto total',
        digits=(16, 2),
        tracking=True,
        help="Monto total de la transacción"
    )
    processed = fields.Boolean(
        string='Processed',
        default=False,
        tracking=True,
        help="Indica si la transacción ha sido procesada"
    )

    # Compos Relaciones
    settlement_tax_id = fields.Many2one(
        'settlement.tax',
        string='Impuesto sobre la liquidación',
        #required=True,
        ondelete='cascade',
        index=True,
        tracking=True
    )
    parent_type = fields.Selection(
        related='settlement_tax_id.type',
        store=True
    )
    settlement_header_id = fields.Many2one(
        'settlement.header',
        string='Cabecera de Liquidación',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True
    )
    settlement_number = fields.Char(
        string='Número de Liquidación',
        index=True,
        help="Número de liquidación al que pertenece la transacción"
    )
    product = fields.Char(
        related='settlement_header_id.product',
        string='Código del Producto',
        store=True,
        help="Código de producto de la transacción"
    )
    journal_id = fields.Many2one(
        'account.journal',
        related='settlement_header_id.journal_id',
        string='Diario',
        store=True,
        help="Diario contable asociado a la transacción"
    )
    external_statement_payment_method_description = fields.Char(
        string='Método de Pago',
        related='settlement_header_id.external_statement_payment_method_description',
        store=True,
        help="Descripción del método de pago del extracto bancario externo"
    )

    # Campos computados
    base_settlement_tax_id = fields.Many2one(
        'settlement.tax', compute='_compute_base_settlement_tax_id', store=True
    )

    @api.constrains('settlement_tax_id', 'settlement_header_id')
    def _check_unique_tax_per_statement(self):
        for record in self:
            others = self.search([
                ('id', '!=', record.id),
                ('settlement_tax_id', '=', record.settlement_tax_id.id),
                ('settlement_header_id', '=', record.settlement_header_id.id),
            ])
            if others:
                raise ValidationError("El impuesto ya existe en esta cabecera de liquidación.")

    @api.depends('settlement_tax_id')
    def _compute_name(self):
        for record in self:
            if record.settlement_tax_id.type == 'tax':
                record.name = f"<p style='margin-left:30px'>{record.settlement_tax_id.name}</p>"
            elif record.settlement_tax_id.type == 'net':
                record.name = f'<b>{record.settlement_tax_id.name}</b>'

    @api.depends('settlement_tax_id', 'settlement_tax_id.parent_id')
    def _compute_base_settlement_tax_id(self):
        for record in self:
            parent_settlement_tax_id = record.settlement_tax_id.parent_id
            if parent_settlement_tax_id:
                record.base_settlement_tax_id = parent_settlement_tax_id
            else:
                record.base_settlement_tax_id = record.settlement_tax_id
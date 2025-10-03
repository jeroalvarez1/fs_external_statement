from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class TradeHeader(models.Model):
    _name = "trade.header"
    _description = "Cabecera de Comercio"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # Campos Base
    name = fields.Char(
        string='Nombre',
        required=True,
        tracking=True
    )
    commerce_number = fields.Char(
        string='Numero de comercio',
        required=True,
        tracking=True
    )
    file_external_statement = fields.Binary(
        string='Archivo',
        required=True
    )
    filename_external_statement = fields.Char(
        string='Nombre original del archivo',
        required=True
    )
    filename_external_statement_view = fields.Char(
        string='Nombre del archivo',
        compute='_compute_display_filename',
        store=True
    )
    state = fields.Selection(
        [('draft', 'Borrador'), ('partial', 'En proceso'), ('processed', 'Realizado')],
        string='Estado', default='draft', tracking=True, index=True, compute='_compute_state', store=True
    )
    # Relaciones
    settlement_header_ids = fields.One2many(
        'settlement.header',
        'trade_header_id',
        string='Cabeceras de Liquidaciones',
        ondelete='restrict',
        copy=False
    )
    bank_statement_ids = fields.One2many(
        'account.bank.statement',
        'trade_header_id',
        string='Extractos Bancarios'
    )

    # Campos calculados
    settlements_count = fields.Integer(
        compute='_compute_settlements_count',
        string='Cantidad de Cabeceras de Liquidaciones'
    )

    # Metodos Base
    def unlink(self):
        """
        Sobreescribe el metodo 'unlink' para no dejar borrar la "Cabecera de Comercio" actual si
        el estado es distinto de 'Borrador' o si cuenta con 'Extractos Bancarios relacionados.'
        """
        if self.state != 'draft':
            raise UserError(
                'No se puede borrar una "Cabecera de Comercio" si el estado es distinto de "Borrador"'
            )
        if len(self.bank_statement_ids) > 0:
            raise UserError(
                'No se puede borrar una "Cabecera de Comercio" si tienen '
                '"Extractos Bancarios" relacionados. Primero borre los extractos'
            )
        return super(TradeHeader, self).unlink()


    def set_draft(self):
        """
        Establece como Borrador la 'Cabecera de comercio', y para lograr el cometido marca los detalles de las
        transacciónes en False, lo cual propaga el cambio de estado de las 'Cabecera de Liquidaciones' y
        de la 'Cabecera de comercio actual'
        """
        self.ensure_one()
        if len(self.bank_statement_ids) > 0:
            raise UserError(
                'No se puede pasar a "Borrador" una "Cabecera de Comercio" '
                'si tienen "Extractos Bancarios" relacionados. Primero borre los extractos'
            )
        if self.state != 'draft':
            self.settlement_header_ids.mapped('transaction_detail_ids').write({
                'processed': False
            })

    # Metodos Depends
    @api.depends('settlement_header_ids')
    def _compute_settlements_count(self):
        """Calcula el número de 'Cabecera de Liquidaciones' relacionados"""
        for record in self:
            record.settlements_count = len(record.settlement_header_ids)

    @api.depends('name', 'create_date')
    def _compute_display_filename(self):
        """Genera un nombre de archivo para mostrar en la vista"""
        for record in self:
            if record.create_date:
                date_str = fields.Datetime.from_string(record.create_date).strftime('%Y%m%d')
                record.filename_external_statement_view = f"{record.name}_{date_str}_{record.filename_external_statement or ''}"

    @api.depends('settlement_header_ids', 'settlement_header_ids.state')
    def _compute_state(self):
        """Calcula el estado basado en las 'Cabecera de Liquidaciones' hijas"""
        for record in self:
            if not record.settlement_header_ids:
                record.state = 'draft'
            elif all(settlement.state == 'processed' for settlement in record.settlement_header_ids):
                record.state = 'processed'
            elif any(settlement.state == 'processed' for settlement in record.settlement_header_ids):
                record.state = 'partial'
            else:
                record.state = 'draft'

    # Metodos Actions
    def action_view_related_bank_statement(self):
        """Acción para ver los 'Extractos Bancarios' relacionados"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Extractos Bancarios',
            'res_model': 'account.bank.statement',
            'view_mode': 'tree,form',
            'target': 'current',
            'domain': [('trade_header_id', '=', self.id)],
        }

    def action_view_settlements(self):
        """Acción para ver las 'Cabecera de Liquidaciones' relacionadas"""
        self.ensure_one()
        return {
            'name': 'Cabeceras de Liquidaciones',
            'view_mode': 'tree,form',
            'res_model': 'settlement.header',
            'type': 'ir.actions.act_window',
            'domain': [('trade_header_id', '=', self.id)],
            'context': {'default_trade_header_id': self.id}
        }

    def _get_transaction_detail_domain(self):
        """
        Obtiene el dominio basico para obtener las 'transaction.detail'
        """
        if not id:
            raise UserError(
                'El parametro "id" es requerido en la función "_get_transaction_detail_domain"'
            )
        return [('settlement_header_id.trade_header_id', '=', self.id)]

    def _generate_bank_statement_validations(self):
        """
        Validaciones generales de la acción 'action_generate_bank_statement'
        """
        self.ensure_one()
        transaction_count = self.env['transaction.detail'].search_count(
            self._get_transaction_detail_domain()
        )
        if transaction_count == 0:
            raise ValidationError(
                f"No se encontraron transacciones para generar el extracto bancario "
                f"en el Trade Header {self.name} (ID: {self.id})"
            )

    def action_generate_bank_statement(self):
        """
        Genera extractos bancarios a partir de los 'Detalles de Transacción' relacionado a la
        Cabecera de Comercio actual. Crea un extracto por cada diario encontrado en las transacciones.
        También crea los Trailer de Liquidación (Impuestos) en el extracto bancario
        """
        self._generate_bank_statement_validations()

        statement_ids = []
        settlement_numbers = self.env['transaction.detail'].read_group(
            domain=self._get_transaction_detail_domain(),
            fields=['settlement_number'],
            groupby=['settlement_number'],
            lazy=False
        )
        _logger.info(f'settlement_numbers -> {settlement_numbers}')
        for settlement in settlement_numbers:
            settlement_number = settlement.get('settlement_number')
            transaction_detail_domain = self._get_transaction_detail_domain() + [('settlement_number', '=', settlement_number)]
            transaction_detail_ids = self.env['transaction.detail'].search(transaction_detail_domain)
            if not transaction_detail_ids:
                raise UserError(
                    f"No se encontraron transacciones para generar el extracto bancario "
                    f"en el Trade Header {self.name} (ID: {self.id}) "
                    f"con el número de liquidación {settlement_number}"
                )
            journal_id = transaction_detail_ids[0].journal_id
            bank_statement_id: int = self.env['account.bank.statement'].create_bank_statement_by_trade_header(
                trade_header_id=self.id, trade_header_name=self.name, settlement_number=settlement_number, journal_id=journal_id.id,
                journal_name=journal_id.name, transaction_detail_ids=transaction_detail_ids
            )
            statement_ids.append(bank_statement_id)
            for transaction_detail_id in transaction_detail_ids:
                self.env['account.bank.statement.line'].create_bank_statement_line_by_trade_header(
                    transaction_id=transaction_detail_id.id,
                    transaction_operation_date=transaction_detail_id.operation_date,
                    transaction_cover_terminal_posnet=transaction_detail_id.cover_terminal_posnet,
                    transaction_summary_lot_posnet=transaction_detail_id.summary_lot_posnet,
                    transaction_card_number=transaction_detail_id.card_number,
                    transaction_coupon_posnet=transaction_detail_id.coupon_posnet,
                    transaction_total=transaction_detail_id.total,
                    bank_statement_id=bank_statement_id
                )
                transaction_detail_id.write({'processed': True})

            grouped_trailer_taxes = self.env['settlement.trailer.tax'].read_group(
                domain=transaction_detail_domain,
                fields=['settlement_tax_id', 'total:sum'],
                groupby=['settlement_tax_id']
            )
            for grouped_trailer_tax in grouped_trailer_taxes:
                if grouped_trailer_tax['total'] != 0:
                    self.env['account.bank.settlement.trailer.tax'].create({
                        'settlement_tax_id': grouped_trailer_tax['settlement_tax_id'][0],
                        'total': grouped_trailer_tax['total'],
                        'statement_id': bank_statement_id
                    })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Extractos Bancarios',
            'res_model': 'account.bank.statement',
            'view_mode': 'tree,form',
            'target': 'current',
            'domain': [('id', 'in', statement_ids)],
            'context': {
                'default_trade_header_id': self.id,
            },
        }
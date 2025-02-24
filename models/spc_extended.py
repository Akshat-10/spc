from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta



class StatisticalProcessControl(models.Model):
    _inherit = 'statistical.process.control'

    def _generate_measurement_values(self):
        """
        Ensure measurement values exist for all groups and parameters **without deleting existing values**.
        """
        for record in self:
            existing_values = self.env['spc.measurement.value'].search([
                ('spc_id', '=', record.id)
            ])

            existing_pairs = {(val.parameter_id.id, val.group_id.id) for val in existing_values}

            new_values = []
            for group in record.measurement_group_ids:
                for parameter in record.parameter_ids:
                    if (parameter.id, group.id) not in existing_pairs:
                        new_values.append({
                            'parameter_id': parameter.id,
                            'group_id': group.id,
                            'spc_id': record.id,
                        })

            if new_values:
                self.env['spc.measurement.value'].create(new_values)

    @api.model
    def create(self, vals):
        """
        Override create method to generate measurement values after record creation.
        """
        record = super(StatisticalProcessControl, self).create(vals)
        record._generate_measurement_values()
        return record

    def write(self, vals):
        """
        Override write method to generate measurement values **only for new groups/parameters**.
        """
        result = super(StatisticalProcessControl, self).write(vals)
        if 'measurement_group_ids' in vals or 'parameter_ids' in vals:
            self._generate_measurement_values()
        return result
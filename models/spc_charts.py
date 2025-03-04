from odoo import models, fields, api, _
import matplotlib
matplotlib.use('Agg')  # Use a non-interactive backend for efficiency
import matplotlib.pyplot as plt
import io
import base64
import numpy as np
from odoo.exceptions import UserError


class SpcIntervalFrequencyDisplay(models.TransientModel):
    _name = 'spc.interval.frequency.display'
    _description = 'SPC Interval and Frequency Display'

    spc_id = fields.Many2one('statistical.process.control', string='SPC')
    interval_id = fields.Many2one('spc.interval', string='Interval', ondelete='cascade')
    frequency_id = fields.Many2one('spc.frequency', string='Frequency', ondelete='cascade')
    interval1 = fields.Float(string='Interval Start', digits=(16, 4))
    interval2 = fields.Float(string='Interval End', digits=(16, 4))
    frequency = fields.Integer(string='Frequency')

class StatisticalProcessControl(models.Model):
    _inherit = 'statistical.process.control'

    x_chart_image = fields.Binary(string="X-Chart Image")
    r_chart_image = fields.Binary(string="R-Chart Image")
    
    
    interval_frequency_display_ids = fields.One2many(
        'spc.interval.frequency.display', 'spc_id',
        string='Interval and Frequency Display'
    )
    
    interval_frequency_chart_image = fields.Binary(string="Interval Frequency Chart")
            
    
    # @api.depends('interval_ids', 'interval_ids.interval1', 'interval_ids.interval2', 
    #          'frequency_ids', 'frequency_ids.frequency')
    # def _compute_interval_frequency_chart(self):
    #     for record in self:
    #         record.action_update_interval_frequency_display()
    #         record.action_generate_interval_frequency_chart()
            
            

    def generate_interval_frequency_chart(self):
        """Generate a bar chart with interval1 on x-axis and two bars (interval2 and frequency) per interval1."""
        # Fetch and sort interval data
        intervals = self.interval_frequency_display_ids.sorted(key=lambda r: r.interval1)
        if not intervals:
            raise UserError(_("No data available to generate the chart. Please update the interval and frequency display first."))

        # Extract values for plotting
        interval1_list = [r.interval1 for r in intervals]
        interval2_list = [r.interval2 for r in intervals]
        frequency_list = [r.frequency for r in intervals]

        # Set up the plot
        N = len(intervals)
        ind = np.arange(N)  # X-axis positions for each group
        width = 0.35  # Width of each bar

        # Create a fresh figure and axes to avoid any issues
        fig = plt.figure(figsize=(10, 6))
        ax = fig.add_subplot(111)  # Create a single subplot

        # Plot bars for interval2 and frequency - explicitly convert NumPy arrays to lists
        ind_positions1 = (ind - width/2).tolist()
        ind_positions2 = (ind + width/2).tolist()
        rects1 = ax.bar(ind_positions1, interval2_list, width, label='Interval', color='lightblue')
        rects2 = ax.bar(ind_positions2, frequency_list, width, label='Frequency', color='lightpink')

        # Customize axes
        ax.set_xlabel('Interval')
        ax.set_ylabel('Frequency')
        ax.set_title('Interval End and Frequency per Interval Start')
        ax.set_xticks(ind)
        ax.set_xticklabels([f'{i:.4f}' for i in interval1_list], rotation=45, ha='right')
        ax.legend()

        # Add grid for readability
        ax.grid(True, linestyle='--', alpha=0.7)

        # Add value labels on top of bars with full precision for interval2
        for rect in rects1:
            height = rect.get_height()
            ax.text(rect.get_x() + rect.get_width()/2., height, f'{height:.4f}',
                    ha='center', va='bottom', fontsize=8)
        for rect in rects2:
            height = rect.get_height()
            ax.text(rect.get_x() + rect.get_width()/2., height, f'{int(height)}',
                    ha='center', va='bottom', fontsize=8)

        # Adjust y-axis limits dynamically
        max_y = max(max(interval2_list, default=0), max(frequency_list, default=0))
        ax.set_ylim(0, max_y * 1.2)  # 20% buffer above the maximum value

        # Save the chart to a binary buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        self.interval_frequency_chart_image = base64.b64encode(buf.read())
        plt.close(fig)  # Free up memory
        
        
    def action_generate_interval_frequency_chart(self):
        self.ensure_one()
        self.generate_interval_frequency_chart()
        return True
        
        
    def action_update_interval_frequency_display(self):
        """Populate interval_frequency_display_ids with data from interval_ids and frequency_ids, including empty lines."""
        self.ensure_one()  # Ensure we're working with a single record

        # Fetch all intervals and frequencies, sorted by sequence
        intervals = self.interval_ids.sorted(key=lambda x: x.sequence)
        frequencies = self.frequency_ids.sorted(key=lambda x: x.sequence)

        # Determine the maximum number of lines based on intervals or frequencies
        max_lines = max(len(intervals), len(frequencies))

        # Clear existing lines to recreate them
        self.interval_frequency_display_ids.unlink()

        # Process each line up to the maximum number
        for i in range(max_lines):
            # Get interval and frequency for the current index, or None if missing
            interval = intervals[i] if i < len(intervals) else None
            frequency = frequencies[i] if i < len(frequencies) else None

            # Set default values for missing data
            interval1 = interval.interval1 if interval and interval.interval1 else 0.0
            interval2 = interval.interval2 if interval and interval.interval2 else 0.0
            freq_value = frequency.frequency if frequency and frequency.frequency else 0

            # Create a new line with the data (or defaults for empty values)
            self.env['spc.interval.frequency.display'].create({
                'spc_id': self.id,
                'interval1': interval1,
                'interval2': interval2,
                'frequency': freq_value,
            })

        return True
            
            
    def action_generate_charts(self):
        """Generate charts when the button is clicked."""
        self.generate_charts()

    def generate_charts(self):
        """Generate X-Chart and R-Chart with all group numbers visible on the x-axis."""
        groups = self.measurement_group_ids  # Use all available groups
        if not groups:
            return

        # Extract actual group numbers from measurement_group_ids
        group_numbers = [group.group_no for group in groups]

        # Fetch actual control limit and statistic values from the model
        ucl_x = self.ucl_x if self.ucl_x else 0.0
        lcl_x = self.lcl_x if self.lcl_x else 0.0
        avg_of_avgs = self.avg_of_avgs if self.avg_of_avgs else 0.0

        ucl_r = self.ucl_r if self.ucl_r else 0.0
        lcl_r = self.lcl_r if self.lcl_r else 0.0
        avg_range = self.avg_range if self.avg_range else 0.0

        # Get actual range and average values for each group
        range_values = []
        avg_values = []

        for group in groups:
            range_stat = self.group_stat_ids.filtered(lambda s: s.group_id.id == group.id and s.stat_type == 'range')
            avg_stat = self.group_stat_ids.filtered(lambda s: s.group_id.id == group.id and s.stat_type == 'avg')
            range_values.append(range_stat.value if range_stat else 0.0)
            avg_values.append(avg_stat.value if avg_stat else 0.0)

        # Ensure we have enough data points
        if not range_values or not avg_values:
            return

        # Create X-Chart (for averages)
        plt.figure(figsize=(10, 6))

        # Plot four lines with different colors using group_numbers
        plt.plot(group_numbers, [ucl_x] * len(groups), label='UCL (X)', marker='o', linestyle='--', color='red', linewidth=1.5)
        plt.plot(group_numbers, [lcl_x] * len(groups), label='LCL (X)', marker='o', linestyle='--', color='blue', linewidth=1.5)
        plt.plot(group_numbers, [avg_of_avgs] * len(groups), label='X-Bar', marker='o', linestyle='-', color='green', linewidth=1.5)
        plt.plot(group_numbers, avg_values, label='Averages', marker='o', color='purple', linewidth=1.5)

        # Add value labels near markers for X-Chart
        first_group = group_numbers[0]
        offset = 0.1  # Small offset to the right of the marker
        # Labels for constants (only at first marker since they are the same)
        plt.text(first_group + 0.1, ucl_x, f'({ucl_x:.4f})', color='red', fontsize=8, ha='left', va='bottom', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
        plt.text(first_group + 0.1, lcl_x, f'({lcl_x:.4f})', color='blue', fontsize=8, ha='left', va='top', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
        plt.text(first_group + 0.1, avg_of_avgs, f'({avg_of_avgs:.4f})', color='green', fontsize=8, ha='left', va='center', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'), rotation=15)
        if all(v == avg_values[0] for v in avg_values):
            plt.text(first_group + 0.1, avg_values[0], f'({avg_values[0]:.4f})', color='purple', fontsize=8, ha='left', va='bottom', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
        else:
            for i, val in enumerate(avg_values):
                plt.text(group_numbers[i] + 0.1, val, f'({val:.4f})', color='purple', fontsize=8, ha='left', va='bottom', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
        # Set x-ticks to show all group numbers 
        plt.xticks(group_numbers)

        # # Dynamically calculate Y-axis limits with a wider buffer for X-Chart
        # all_x_values = [ucl_x, lcl_x, avg_of_avgs] + avg_values
        # data_min = min(all_x_values) if all_x_values else 0.0
        # data_max = max(all_x_values) if all_x_values else 0.0

        # # Add a buffer to ensure a wide range (e.g., 20% of the range or a minimum of 4000 units, whichever is larger)
        # range_buffer = max(abs(data_max - data_min) * 0.2, 4000)
        # y_min = data_min - range_buffer if data_min < 0 else -range_buffer
        # y_max = data_max + range_buffer if data_max > 0 else range_buffer
        
        # plt.ylim(y_min, y_max)
        
        
        # Dynamically calculate Y-axis limits for X-Chart
        all_x_values = [ucl_x, lcl_x, avg_of_avgs] + avg_values  # Combine all relevant values
        if all_x_values:  # Check if there’s data
            data_min = min(all_x_values)
            data_max = max(all_x_values)
            data_range = data_max - data_min if data_max > data_min else 1  # Avoid division by zero
            padding = data_range * 0.1  # 10% of the range as padding
            y_min = data_min - padding
            y_max = data_max + padding
        else:
            y_min, y_max = -1, 1  # Fallback if no data

        plt.ylim(y_min, y_max)

        plt.xlabel('Sample')
        plt.ylabel('Value')
        plt.title('X-Chart')
        # plt.legend()
        plt.legend(loc='upper right', framealpha=0.7)
        plt.grid(True)

        # Save X-Chart as PNG
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        self.x_chart_image = base64.b64encode(buf.read())
        plt.close()  # Free up memory

        # Create R-Chart (for ranges)
        plt.figure(figsize=(10, 6))

        # Plot four lines with different colors using group_numbers
        plt.plot(group_numbers, [ucl_r] * len(groups), label='UCL (R)', marker='o', linestyle='--', color='red', linewidth=1.5)
        plt.plot(group_numbers, [lcl_r] * len(groups), label='LCL (R)', marker='o', linestyle='--', color='blue', linewidth=1.5)
        plt.plot(group_numbers, [avg_range] * len(groups), label='R-Bar', marker='o', linestyle='-', color='green', linewidth=1.5)
        plt.plot(group_numbers, range_values, label='Ranges', marker='o', color='purple', linewidth=1.5)

        # Add value labels near markers for R-Chart
        # Labels for constants (only at first marker since they are the same)
        plt.text(first_group + 0.1, ucl_r, f'({ucl_r:.4f})', color='red', fontsize=8, ha='left', va='bottom', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
        plt.text(first_group + 0.1, lcl_r, f'({lcl_r:.4f})', color='blue', fontsize=8, ha='left', va='top', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
        plt.text(first_group + offset, avg_range, f'({avg_range:.4f})', color='green', fontsize=8, ha='left', va='center', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'), rotation=15)
        if all(v == range_values[0] for v in range_values):
            plt.text(first_group + 0.1, range_values[0], f'({range_values[0]:.4f})', color='purple', fontsize=8, ha='left', va='bottom', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
        else:
            for i, val in enumerate(range_values):
                plt.text(group_numbers[i] + 0.1, val, f'({val:.4f})', color='purple', fontsize=8, ha='left', va='bottom', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

        # Set x-ticks to show all group numbers
        plt.xticks(group_numbers)

        # Dynamically calculate Y-axis limits with a wider buffer for R-Chart
        # all_r_values = [ucl_r, lcl_r, avg_range] + range_values
        # data_min_r = min(all_r_values) if all_r_values else 0.0
        # data_max_r = max(all_r_values) if all_r_values else 0.0

        # # Add a buffer to ensure a wide range (e.g., 20% of the range or a minimum of 4000 units, whichever is larger)
        # range_buffer_r = max(abs(data_max_r - data_min_r) * 0.2, 4000)
        # y_min_r = data_min_r - range_buffer_r if data_min_r < 0 else -range_buffer_r
        # y_max_r = data_max_r + range_buffer_r if data_max_r > 0 else range_buffer_r
        
        # plt.ylim(y_min_r, y_max_r)

        # Dynamically calculate Y-axis limits for R-Chart
        all_r_values = [ucl_r, lcl_r, avg_range] + range_values
        if all_r_values:
            data_min_r = min(all_r_values)
            data_max_r = max(all_r_values)
            data_range_r = data_max_r - data_min_r if data_max_r > data_min_r else 1  # Avoid division by zero
            padding_r = data_range_r * 0.1  # 10% padding
            y_min_r = data_min_r - padding_r
            y_max_r = data_max_r + padding_r
            # Force negative lower limit even if data is all positive
            if y_min_r > 0:
                y_min_r = -padding_r
        else:
            y_min_r, y_max_r = -1, 1  # Fallback
        plt.ylim(y_min_r, y_max_r)
        

        plt.xlabel('Sample')
        plt.ylabel('Value')
        plt.title('R-Chart')
        # plt.legend()
        plt.legend(loc='upper right', framealpha=0.7)
        plt.grid(True)

        # Save R-Chart as PNG
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        self.r_chart_image = base64.b64encode(buf.read())
        plt.close()  # Free up memory
        
    def write(self, vals):
        """Override write to update display lines and charts when interval_ids or frequency_ids change."""
        res = super(StatisticalProcessControl, self).write(vals)
        if 'interval_ids' in vals or 'frequency_ids' in vals:
            for record in self:
                record.action_update_interval_frequency_display()
                record.action_generate_interval_frequency_chart()
        return res
    

class SpcMeasurementValue(models.Model):
    _inherit = 'spc.measurement.value'


    def write(self, vals):
        """Trigger statistics calculation when an existing value is updated."""
        result = super(SpcMeasurementValue, self).write(vals)
        if 'value' in vals:  # Only trigger if 'value' field is modified
            for record in self:
                if record.spc_id:
                    record.spc_id.action_calculate_statistics()
                    record.spc_id.action_generate_charts()
        return result

    @api.onchange('value')
    def _onchange_value_trigger_statistics(self):
        """Triggers statistics calculation when the value field is changed"""
        if self.spc_id:
            self.spc_id.action_calculate_statistics()
            self.spc_id.action_generate_charts()
            
            

# class SpcInterval(models.Model):
#     _inherit = 'spc.interval'


#     def write(self, vals):
#         """Override write to trigger chart regeneration on update."""
#         res = super(SpcInterval, self).write(vals)
#         for record in self:
#             if record.spc_id:  # Check if the record is linked to a parent SPC
#                 record.spc_id.action_update_interval_frequency_display()
#                 record.spc_id.action_generate_interval_frequency_chart()
#         return res

#     def create(self, vals):
#         """Override create to trigger chart regeneration on creation."""
#         res = super(SpcInterval, self).create(vals)
#         for record in res:
#             if record.spc_id:
#                 record.spc_id.action_update_interval_frequency_display()
#                 record.spc_id.action_generate_interval_frequency_chart()
#         return res

#     def unlink(self):
#         """Override unlink to trigger chart regeneration on deletion."""
#         spc_ids = self.mapped('spc_id')  # Collect parent SPC records before deletion
#         res = super(SpcInterval, self).unlink()
#         for spc in spc_ids:
#             spc.action_update_interval_frequency_display()
#             spc.action_generate_interval_frequency_chart()
#         return res
    
class SpcFrequency(models.Model):
    _inherit = 'spc.frequency'


    # def write(self, vals):
    #     """Override write to trigger chart regeneration on update."""
    #     res = super(SpcFrequency, self).write(vals)
    #     for record in self:
    #         if record.spc_id:  # Check if the record is linked to a parent SPC
    #             record.spc_id.action_update_interval_frequency_display()
    #             record.spc_id.action_generate_interval_frequency_chart()
    #     return res

    # def create(self, vals):
    #     """Override create to trigger chart regeneration on creation."""
    #     res = super(SpcFrequency, self).create(vals)
    #     for record in res:
    #         if record.spc_id:
    #             record.spc_id.action_update_interval_frequency_display()
    #             record.spc_id.action_generate_interval_frequency_chart()
    #     return res

    
    @api.depends('frequency', 'sequence', 'spc_id')
    def _compute_current_frequency(self):
        super(SpcFrequency, self)._compute_current_frequency()
        spc_ids = self.mapped('spc_id')
        for spc in spc_ids:
            frequencies = self.env['spc.frequency'].search([
                ('spc_id', '=', spc.id)
            ], order='sequence')
            cumulative = 0
            for freq in frequencies:
                cumulative += freq.frequency or 0
                freq.current_frequency = cumulative
                
    def unlink(self):
        """Override unlink without triggering redundant updates."""
        # Still compute current_frequency if needed, but skip display update
        spc_ids = self.mapped('spc_id')
        res = super(SpcFrequency, self).unlink()
        for spc in spc_ids:
            spc.frequency_ids._compute_current_frequency()
        return res
    
    # def unlink(self):
    #     """Override unlink to trigger chart regeneration on deletion."""
    #     spc_ids = self.mapped('spc_id')  # Collect parent SPC records before deletion
    #     res = super(SpcFrequency, self).unlink()
    #     for spc in spc_ids:
    #         spc.action_update_interval_frequency_display()
    #         spc.action_generate_interval_frequency_chart()
    #         spc.frequency_ids._compute_current_frequency()
    #     return res
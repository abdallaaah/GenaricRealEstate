from odoo import api, models, Command

class Eoi(models.Model):
    _inherit = 'eoi.eoi'

    @api.depends('user_id', 'sales_ids', 'split_deal')
    def compute_person_hierarchy(self):
        """
        Compute commission hierarchy for EOI based on user_id and sales_ids
        Similar to CRM Lead hierarchy
        """
        # Job positions list (3 levels: Sales Person, Sales Manager, Director)
        job_positions = ['Sales Person', 'Sales Manager', 'Sales Sector Manager', 'Director']
        job_position_order = {pos: index for index, pos in enumerate(job_positions)}
        print(f"job_position_order:{job_position_order}")

        for rec in self:
            # Skip if no user assigned
            if not rec.user_id:
                rec.commission_ids = [Command.clear()]
                continue

            # Get team for the main user
            team_member = self.env['crm.team.member'].search([('user_id', '=', rec.user_id.id)], limit=1)

            if not team_member or not team_member.crm_team_id:
                # If user has no team, skip commission calculation
                rec.commission_ids = [Command.clear()]
                continue

            team_id = team_member.crm_team_id

            # Clear existing commission lines
            rec.commission_ids = [Command.clear()]
            unique_lines = {}  # Changed to dict to store user_id: job_position

            # Build team hierarchy for main user (3 levels)
            team_users = [
                rec.user_id,  # Sales Person
                team_id.sales_manager_id,  # Sales Manager (team leader)
                team_id.operation_id, #Sales Sector Manager
                team_id.director_id  # Director
            ]

            # Add main user's team hierarchy
            for i in range(len(team_users)):
                if team_users[i]:  # Only add if user exists
                    user_id = team_users[i].id
                    # Keep the highest position if user appears multiple times
                    if user_id not in unique_lines or job_position_order[job_positions[i]] < job_position_order[
                        unique_lines[user_id]]:
                        unique_lines[user_id] = job_positions[i]

            # If split deal, add hierarchies for additional sales people
            if rec.split_deal and rec.sales_ids:
                for person in rec.sales_ids:
                    # Get team for each additional sales person
                    person_team_member = self.env['crm.team.member'].search(
                        [('user_id', '=', person.id)], limit=1
                    )

                    if person_team_member and person_team_member.crm_team_id:
                        person_team_id = person_team_member.crm_team_id

                        # Build hierarchy for this person
                        person_team_users = [
                            person,  # Sales Person
                            person.sales_manager_id,  # Sales Manager (team leader)
                            person.operation_id,  # Sales Sector Manager
                            person_team_id.director_id  # Director
                        ]

                        # Add to unique lines
                        for i in range(len(person_team_users)):
                            if person_team_users[i]:  # Only add if user exists
                                user_id = person_team_users[i].id
                                # Keep the highest position if user appears multiple times
                                if user_id not in unique_lines or job_position_order[job_positions[i]] < \
                                        job_position_order[unique_lines[user_id]]:
                                    unique_lines[user_id] = job_positions[i]

            # Sort lines by job position hierarchy
            sorted_lines = sorted(unique_lines.items(), key=lambda x: job_position_order[x[1]])

            # Create commission lines
            lines = [Command.create({
                'eoi_id': rec.id,
                'employee_id': user_id,
                'jop_position': job_position,
                'commission': 100.0  # Default commission percentage
            }) for user_id, job_position in sorted_lines]

            rec.commission_ids = lines

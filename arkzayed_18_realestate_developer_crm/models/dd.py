def compute_person_hierarchy(self):
        team_users = [self.user_id, team_id.sales_manager_id, team_id.user_id, team_id.operation_id, team_id.director_id]
        for record in self:
            record.commission_ids = [Command.unlink(line.id) for line in self.commission_ids]
            lines = [Command.create({
                'opportunity_id': record.id,
                'employee_id': team_users[i].id,
                'jop_position': job_positions[i]
                }) for i in range(5)]
            self.commission_ids = lines
        if self.split_deal:
            if self.sales_ids:
                job_positions = ['Sales Person', 'Sales Manager', 'Team Leader', 'Operation Manager', 'Director']
                sales_count = int(len(self.sales_ids))
                print('coooooo', sales_count)
                for person in self.sales_ids:
                    print('ppppppppp', person._origin.id)
                    team_id = self.env['crm.team.member'].search([('user_id', '=', person._origin.id)]).crm_team_id
                    print('tttttttt',team_id)
                    team_users = [person, team_id.sales_manager_id, team_id.user_id, team_id.operation_id,
                                  team_id.director_id]
                    for record in self:
                        # record.commission_ids = [Command.unlink(line.id) for line in self.commission_ids]
                        lines = [Command.create({
                            'opportunity_id': record.id,
                            'employee_id': team_users[i].id,
                            'jop_position': job_positions[i]
                        }) for i in range(5)]
                        print(lines)
                        self.commission_ids = lines


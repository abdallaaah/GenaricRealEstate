from . import models


def post_init_hook(env):
    # broker.sales.hierarchy's view is generated from the job.level chain, but its
    # init() runs before data/job_level_data.xml loads on a fresh install. Rebuild it
    # here, once the chain exists.
    env['broker.sales.hierarchy']._rebuild()

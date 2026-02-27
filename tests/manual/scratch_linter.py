from theus.linter import POPLinter
import ast

code = '''
from theus import process
from typing import Annotated
from theus.context import Mutable, BaseDomainContext

class BadContext(BaseDomainContext):
    log_events: Annotated[list, Mutable] # POP-E07
    meta_config: Annotated[dict, Mutable] # POP-E07

@process
def mutate_func(ctx):
    ctx.domain.meta_config.update({"a": 1}) # POP-E07
    ctx.domain.data_user.append(1) # POP-E05
'''
tree = ast.parse(code)
linter = POPLinter('dummy.py')
linter.visit(tree)
codes = [v.check_id for v in linter.violations]
print('violations:', codes)

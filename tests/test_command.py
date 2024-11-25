'''
Test the `command` decorator.
'''
from pathlib import Path

def test_command_decorator(cmd_args):
    def t_func(*, _info):
        pass
    cmd = cmd_args()(t_func)
    cmd()
    
def test_command_decorator_with_args(cmd_args):
    def t_func(path: Path, *, flag=False, _info):
        assert isinstance(path, Path)
        assert flag is True
    cmd = cmd_args(flags={'flag'})(t_func)
    cmd('foo.txt', '--flag')
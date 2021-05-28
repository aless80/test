# run this file as:
# pytest --pdb pytests.py      # then in the debugger:  print(out.stdout)
# pytest -s pytests.py         #to capture stout
# pytest -q pytests.py         #-q quiet vs -v verbose
# pytest -v pytests.py::test_split_file    #only one test

# when assers fail, +/- are left/right
import pytest
import os
import sys


def test_stub():
    assert 1 == 1
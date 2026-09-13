from pkg import largest, add

def test_add():
    assert add(2, 3) == 5

def test_largest():
    assert largest([3, 9, 4]) == 9
    assert largest([-1, -7]) == -1

from __future__ import unicode_literals

from hiku.edn import loads
from hiku.result import Result
from hiku.writers.simple import dumps


def check_writes(data, output):
    first = loads(dumps(data))
    second = loads(output)
    assert first == second


def test_simple():
    result = Result()
    result.root['f1'] = 1
    a = result.root.setdefault('a', {})
    a['f2'] = 2
    b = result.index.setdefault('b', {})
    b[1] = {'f3': 'bar1'}
    b[2] = {'f3': 'bar2'}
    b[3] = {'f3': 'bar3'}
    result.root['l1'] = result.ref('b', 1)
    result.root['l2'] = [result.ref('b', 2), result.ref('b', 3)]
    check_writes(
        result,
        """
        {
          "f1" 1
          "a" {"f2" 2}
          "b" {1 {"f3" "bar1"}
               2 {"f3" "bar2"}
               3 {"f3" "bar3"}}
          "l1" #graph/ref ["b" 1]
          "l2" [#graph/ref ["b" 2]
                #graph/ref ["b" 3]]
        }
        """,
    )

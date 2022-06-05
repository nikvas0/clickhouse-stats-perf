import subprocess
import json
import random
import time
import os
import time

#SET allow_experimental_stats_for_prewhere_optimization = 1;

SEED = 42
ROWS = 2**26
RUNS = 1
CH_DATABASE = 'test'
CH_BINARY_PATH = '/home/nikita/ClickHouse/build_release/programs/clickhouse'

TABLE_BASE = 't_'
TESTS = ['none', 'one_tdigest', 'tdigest', 'one_tdigest_granule', 'tdigest_granule', 'one_string', 'string', 'all']

random.seed(SEED)


class ClickHouse:
    def __init__(self, binary_path_):
        self.bin_path = binary_path_

    def run(self, query, answer=True, silent=False):
        cmd = [self.bin_path, 'client', '-q', query, '-f', 'JSON']
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = map(lambda x: x.decode('ascii'), proc.communicate())
        if not silent:
            print('Q: ' + query)
            print('CH: ' + out)
            print('CH: ' + err)
        if answer:
            return json.loads(out)


ch = ClickHouse(CH_BINARY_PATH)


def getMeta(create_query, insert_query, clean_query, count):
    ch.run(clean_query, answer=False)
    result = []
    for _ in range(count):
        ch.run(create_query, answer=False)
        start = time.time()
        ch.run(insert_query, answer=False, silent=True)
        end = time.time()
        result.append({'elapsed': (end - start) })
        ch.run(clean_query, answer=False)
    return result

def getAggregates(create_query, insert_query, clean_query, count):
    meta = getMeta(create_query, insert_query, clean_query, count)
    elapsed = min(map(lambda x: x['elapsed'], meta))
    return {
        'elapsed': elapsed
    }

def runTestOnce(create_query, insert_query, clean_query):
    return getAggregates(create_query, insert_query, clean_query, RUNS)

def testInsert():
    def create(table, stat):
        return '''
CREATE TABLE {}.{}
(
    ind UInt64,
    u1 UInt64,
    u2 UInt64,
    u3 UInt64,
    u4 UInt64,
    s1 String,
    s2 String,
    s3 String,
    s4 String
    {}
)
ENGINE=MergeTree() ORDER BY ind
'''.format(CH_DATABASE, table, stat)

    def insert(table):
        return '''
INSERT INTO {}.{} SELECT
    number AS ind,
    intHash64(number) AS u1,
    intHash64(number * 2313423) AS u2,
    intHash64(number * 5243523) AS u3,
    intHash64(number * 5235222) AS u4,
    toString(intHash64(number)) AS s1,
    toString(intHash64(number * 2313423)) AS s2,
    toString(intHash64(number * 5243523)) AS s3,
    toString(intHash64(number * 5235222)) AS s4
FROM system.numbers LIMIT {}
'''.format(CH_DATABASE, table, ROWS)

    def drop(table):
        return 'DROP TABLE IF EXISTS {}.{}'.format(CH_DATABASE, table)

    mp = {
        'none': '',
        'one_tdigest': ',STATISTIC num_stat (u1) TYPE tdigest ',
        'tdigest': ',STATISTIC num_stat (u1, u2, u3, u4) TYPE tdigest ',
        'one_tdigest_granule': ',STATISTIC num_stat (u1) TYPE granule_tdigest ',
        'tdigest_granule': ',STATISTIC num_stat (u1, u2, u3, u4) TYPE granule_tdigest ',
        'one_string' : ',STATISTIC str_stat (s1) TYPE granule_string_hash ',
        'string' : ',STATISTIC str_stat (s1, s2, s3, s4) TYPE granule_string_hash ',
        'all': ',STATISTIC num_stat1 (u1, u2, u3, u4) TYPE granule_tdigest, STATISTIC str_stat (s1, s2, s3, s4) TYPE granule_string_hash',
    }

    result = dict()
    for test in TESTS:
        create_query = create('t_' + test, mp[test])
        insert_query = insert('t_' + test)
        drop_query = drop('t_' + test)
        result[test] = runTestOnce(create_query, insert_query, drop_query)

    return result

def printTable(total):
    print('\t', end='')
    for test in TESTS:
        print(test, end='\t')
    print()
    for token in ['test_insert']:
        print(token, ":")
        print('\t', end='')
        for test in TESTS:
            print(total[token][test]['elapsed'], end='\t')
        print()

def main():
    total = dict()
    total['test_insert'] = testInsert()

    printTable(total)
    print()
    print(total)

main()

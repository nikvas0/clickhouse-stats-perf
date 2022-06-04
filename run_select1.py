import subprocess
import json
import random
import time
import os

#SET allow_experimental_stats_for_prewhere_optimization = 1;

SEED = 42
RUNS = 5
GRANULE = 8192
ROWS = GRANULE * 8192

CH_DATABASE = 'test'
CH_BINARY_PATH = '/home/nikita/ClickHouse/build_release/programs/clickhouse'

TABLE_BASE = 't_'
TESTS = ['none', 'tdigest_and_string', 'tdigest_granule_and_string']

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


def getMeta(query, count):
    result = []
    for _ in range(count):
        cur = ch.run(query)
        result.append(cur['statistics'])
    return result

def getAggregates(query, count):
    meta = getMeta(query, count)
    relapsed = min(map(lambda x: x['elapsed'], meta))
    rrows = meta[0]['rows_read']
    rbytes = meta[0]['bytes_read']

    for query in meta:
        if rrows != query['rows_read']:
            print('ERROR rows: {}!={}'.format(rrows, query['rows_read']))
        if rbytes != query['bytes_read']:
            print('ERROR bytes: {}!={}'.format(rbytes, query['bytes_read']))

    return {
        'elapsed': relapsed,
        'rows': rrows,
        'bytes': rbytes,
    }

def getStatisticsInfo():
    return ch.run('select * from system.statistics')['data']

# stat: none, tdigest_and_string, tdigest_granule_and_string
def fillTable(table, stat):
    def getStat():
        if stat == 'none':
            return ''
        elif stat == 'tdigest_and_string':
            return ', STATISTIC num_stat (u1, u2, u4, u8, urand, i4) TYPE tdigest, STATISTIC str_stat (s8, s16, s64) TYPE granule_string_hash'
        elif stat == 'tdigest_granule_and_string':
            return ', STATISTIC num_stat (u1, u2, u4, u8, urand, i4) TYPE granule_tdigest, STATISTIC str_stat (s8, s16, s64) TYPE granule_string_hash'

    ch.run('DROP TABLE IF EXISTS {}.{}'.format(CH_DATABASE, table), answer=False)
    ch.run('''
CREATE TABLE {}.{}
(
    ind UInt64,
    u1 UInt64 CODEC(NONE),
    u2 UInt64 CODEC(NONE),
    u4 UInt64 CODEC(NONE),
    u8 UInt64 CODEC(NONE),
    urand UInt64 CODEC(NONE),
    i4 Int32 CODEC(NONE),
    s8 String CODEC(NONE),
    s16 String CODEC(NONE),
    s64 String CODEC(NONE),
    heavy String CODEC(NONE)
    {}
)
ENGINE=MergeTree() ORDER BY ind
SETTINGS index_granularity = {};
'''.format(CH_DATABASE, table, getStat(), GRANULE), answer=False)


    ch.run('''
INSERT INTO {database}.{table} SELECT
    number AS ind,
    number % ({granule} * 1) AS u1,
    number % ({granule} * 2) AS u2,
    number % ({granule} * 4) AS u4,
    number % ({granule} * 8) AS u8,
    intHash64(number) AS urand,
    number % ({granule} * 4) AS i4,'''.format(database=CH_DATABASE, table=table, granule=GRANULE) +
    "format('clickhouse {}', toString(number % (" + str(GRANULE) + " * 8))) AS s8," +
    "format('clickhouse {}', toString(number % (" + str(GRANULE) + " * 16))) AS s16," +
    "format('{}', toString(number % (" + str(GRANULE) + " * 64))) AS s64," +
    "'clickhouseclickhouseclickhouseclickhouseclickhouse' AS heavy" +
" FROM system.numbers".format(granule=GRANULE) +
' LIMIT {rows};'.format(rows=ROWS), answer=False)

    ch.run('OPTIMIZE TABLE {}.{} FINAL'.format(CH_DATABASE, table), answer=False)
    ch.run('SYSTEM RELOAD STATISTICS {}.{}'.format(CH_DATABASE, table), answer=False)
    print(ch.run('SHOW CREATE TABLE {}.{}'.format(CH_DATABASE, table))['data'][0]['statement'])
    print(ch.run('SELECT count() FROM {}.{}'.format(CH_DATABASE, table)))

def dropTable(table):
    ch.run('DROP TABLE IF EXISTS {}.{}'.format(CH_DATABASE, table), answer=False)

def runTestOnce(query):
    return getAggregates(query, RUNS)

def runTest(query_template):
    res = dict()
    for test in TESTS:
        res[test] = runTestOnce(query_template.format(database=CH_DATABASE, table=TABLE_BASE+test))
    return res

def runQuerySet(queries):
    res = []
    for query in queries:
        res.append({'results': runTest(query), 'query': query})
    return res

def compareTest():
    q = [
        "SELECT count() FROM {database}.{table} WHERE 100 < u2 AND u2 < 200 AND 100 < u8 AND u8 < 200 AND heavy == 'heavy'", # test u1 vs u8
        "SELECT count() FROM {database}.{table} WHERE 100 < u2 AND u2 < 200 AND 100 < u8 AND u8 < 1000 AND heavy == 'heavy'", # test u1 vs u8
        "SELECT count() FROM {database}.{table} WHERE u2 < 100 AND i4 < 100 AND heavy == 'heavy'", # test u2 vs i4
        "SELECT count() FROM {database}.{table} WHERE u8 < 100 AND i4 < 100 AND heavy == 'heavy'", # test u8 vs i4
        "SELECT count() FROM {database}.{table} WHERE u1 = 100 AND i4 = 100 AND heavy == 'heavy'", # test equal: u1 vs i4
        "SELECT count() FROM {database}.{table} WHERE u8 = 100 AND i4 = 100 AND heavy == 'heavy'", # test equal: u8 vs i4
        "SELECT count() FROM {database}.{table} WHERE u1 = 100 AND u8 = 100 AND heavy == 'heavy'", # test equal: u1 vs u8
    ]
    return runQuerySet(q)

def stringTest():
    q = [
        "SELECT count() FROM {database}.{table} WHERE s8 = 'clickhouse 42' AND s16 = 'clickhouse 42' AND heavy == 'heavy'", # strings basic
        # "SELECT count() FROM {database}.{table} WHERE s8 = 'unknown' AND s16 = 'clickhouse 42' AND heavy == 'heavy'", # strings not found
        "SELECT count() FROM {database}.{table} WHERE u1 = 42 AND s64 = 'clickhouse 42' AND heavy == 'heavy'", # better string
    ]
    return runQuerySet(q)

def granuleTest():
    q = [
        "SELECT count() FROM {database}.{table} WHERE u1 < 100 AND u2 < 1000 AND heavy == 'heavy'", # granule will be better
        "SELECT count() FROM {database}.{table} WHERE u1 < 8100 AND u2 < 16200 AND u4 < 32400 AND urand = 11490350930367293593 AND heavy = 'heavy'", # row will be better
    ]
    return runQuerySet(q)

def printTable(total):
    print('\t', end='')
    for test in TESTS:
        print(test, end='\t')
    print()
    for token in ['test_compare', 'test_string', 'test_granule']:
        print(token, ":")
        for ts in total[token]:
            print(ts['query'], end='\t')
            for test in TESTS:
                print(ts['results'][test]['elapsed'], end='\t')
            print()

def main():
    for test in TESTS:
        fillTable(TABLE_BASE + test, test)
    total = dict()
    total['test_compare'] = compareTest()
    total['test_string'] = stringTest()
    total['test_granule'] = granuleTest()
    total['stats'] = getStatisticsInfo()

    printTable(total)

    print(total)

    for test in TESTS:
        dropTable(TABLE_BASE + test)

main()

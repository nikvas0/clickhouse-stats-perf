import subprocess
import json
import random
import time
import os

#SET allow_experimental_stats_for_prewhere_optimization = 1;

SEED = 42
RUNS = 5
ROWS = 100 #100 * 1000 * 1000
GRANULE = 8192

CH_DATABASE = 'test'
CH_BINARY_PATH = '/home/nikita/ClickHouse/build/programs/clickhouse'

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


def dropPageCache():
    os.system('echo 1 > /proc/sys/vm/drop_caches')

def getMeta(query, count):
    result = []
    for _ in range(count):
        dropPageCache()
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
            return ', STATISTIC num_stat (u1, u2, u3, u4, i1) TYPE tdigest, STATISTIC str_stat (s1, s2, s3) TYPE granule_string_hash'
        elif stat == 'tdigest_granule_and_string':
            return ', STATISTIC num_stat (u1, u2, u3, u4, i1) TYPE granule_tdigest, STATISTIC str_stat (s1, s2, s3) TYPE granule_string_hash'

    ch.run('DROP TABLE IF EXISTS {}.{}'.format(CH_DATABASE, table), answer=False)
    ch.run('''
CREATE TABLE {}.{}
(
    ind UInt64,
    u1 UInt64 CODEC(NONE),
    u2 UInt64 CODEC(NONE),
    u3 UInt64 CODEC(NONE),
    u4 UInt64 CODEC(NONE),
    i1 Int32 CODEC(NONE),
    s1 String CODEC(NONE),
    s2 String CODEC(NONE),
    s3 String CODEC(NONE),
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
    number % ({granule} * 4) AS i4,'''.format(database=CH_DATABASE, table=table, granule=GRANULE) +
    "format('clickhouse {}', toString(number % (8192 * 8))) AS s8," +
    "format('clickhouse {}', toString(number % (8192 * 16))) AS s16," +
    "format('{}', toString(number % (8192 * 64))) AS s64," +
    "'clickhouseclickhouseclickhouseclickhouseclickhouse' AS heavy" +
" FROM system.numbers".format(granule=GRANULE) +
' LIMIT {rows};'.format(rows=ROWS), answer=False)

    ch.run('SYSTEM RELOAD STATISTICS {}.{}'.format(CH_DATABASE, table), answer=False)
    print(ch.run('SHOW CREATE TABLE {}.{}'.format(CH_DATABASE, table))['data'][0]['statement'])
    print(ch.run('SELECT count() FROM {}.{}'.format(CH_DATABASE, table)))

def runTest(query):
    return getAggregates(query, RUNS)

def main():
    for test in TESTS:
        fillTable(TABLE_BASE + test, test)
    print(getStatisticsInfo())

main()
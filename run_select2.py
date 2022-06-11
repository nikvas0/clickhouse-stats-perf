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

CH_DATABASE = 'default'
CH_BINARY_PATH = '/home/nikita/ClickHouse/build_release/programs/clickhouse'

TABLE_BASE = 'hits_100m'
STATS_SUFF = '_st'
NONE_SUFF = '_none'

TESTS = [STATS_SUFF, NONE_SUFF]

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

def runTestOnce(query):
    return getAggregates(query, RUNS)

def runTest(query_template):
    res = dict()
    for test in TESTS:
        print(ch.run('EXPLAIN SYNTAX ' + query_template.format(database=CH_DATABASE, table=TABLE_BASE+test)))
        res[test] = runTestOnce(query_template.format(database=CH_DATABASE, table=TABLE_BASE+test))
    return res

def runQuerySet(queries):
    res = []
    for query in queries:
        res.append({'results': runTest(query), 'query': query})
    return res

def compareTest():
    q = [
        "SELECT sum(length(URL)), sum(length(URLDomain)) FROM {database}.{table} WHERE URLDomain = 'pogoda' AND URL LIKE '%pogoda%'", # test same
        "SELECT count() FROM {database}.{table} WHERE Income = 2 AND Age = 31 AND WatchID = 4894690465724379622", # test selectivity better
        "SELECT count() FROM {database}.{table} WHERE Income = 3 AND UserAgent = 110", # test selectivity better
        "SELECT count() FROM {database}.{table} WHERE Income = 2 AND UserAgent = 5", # test selectivity worse
    ]
    return runQuerySet(q)


def printTable(total, val):
    print('\t', end='')
    for test in TESTS:
        print(test, end='\t')
    print()
    for token in ['test_compare']:
        print(token, ":")
        for ts in total[token]:
            print(ts['query'], end='\t')
            for test in TESTS:
                print(ts['results'][test][val], end='\t')
            print()

def main():
    dropPageCache()
    ch.run('SYSTEM RELOAD STATISTICS {}.{}'.format(CH_DATABASE, TABLE_BASE + STATS_SUFF), answer=False)

    total = dict()
    total['test_compare'] = compareTest()
    total['stats'] = getStatisticsInfo()

    print()
    print("elapsed")
    printTable(total, 'elapsed')
    print()
    print('bytes')
    printTable(total, 'bytes')
    print()
    print('rows')
    printTable(total, 'rows')

    print(total)

main()
